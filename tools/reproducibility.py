"""Subprocess perturbation harness. Compare artifacts as bytes, never normalize.

All exclusions live here. There are currently none: SOURCE_DATE_EPOCH pins
reference dates and ReqIF timestamps, and these artifacts carry neither wall
clock generation times nor Git revisions. Absolute paths are bugs, not allowed
volatility. tests/test_reproducibility.py locks this reviewed mapping.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import locale
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VOLATILE_FIELDS: dict[str, str] = {}
FINGERPRINT_KEYS = (
    'configurationFingerprint', 'semanticGraphFingerprint', 'representationFingerprint',
)
REFERENCE_EPOCH = '1788912000'  # 2026-09-09 00:00:00 UTC, before model evidence expiry.
COLLATION_SAMPLE = ('z', 'á')
LOCALE_CANDIDATES = (
    ('Portuguese_Brazil.1252', 'English_United States.1252', 'German_Germany.1252')
    if sys.platform == 'win32' else
    ('pt_BR.UTF-8', 'pt_BR.utf8', 'en_US.UTF-8', 'en_US.utf8', 'de_DE.UTF-8', 'de_DE.utf8')
)


def collating_locale() -> str:
    """An installed locale that really collates differently from C.

    Never falls back to C silently: a run that cannot vary collation is not a
    run that proved collation independence, so an exhausted candidate list is
    a loud failure naming what was tried.
    """
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, 'C')
        baseline = sorted(COLLATION_SAMPLE, key=locale.strxfrm)
        for name in LOCALE_CANDIDATES:
            try:
                locale.setlocale(locale.LC_ALL, name)
            except locale.Error:
                continue
            if sorted(COLLATION_SAMPLE, key=locale.strxfrm) != baseline:
                return name
        raise AssertionError(
            'no installed locale collates differently from C (tried '
            f"{', '.join(LOCALE_CANDIDATES)}). Generate one, for example "
            'locale-gen pt_BR.UTF-8, so the collation axis is actually exercised.'
        )
    finally:
        locale.setlocale(locale.LC_ALL, previous)


def _write_json(path: Path, value) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'))


def artifact_bytes(directory: Path) -> dict[str, bytes]:
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in sorted(directory.rglob('*')) if path.is_file()}


def compare_artifacts(before: Path, after: Path) -> None:
    left, right = artifact_bytes(before), artifact_bytes(after)
    if left.keys() != right.keys():
        raise AssertionError(f'artifact paths differ: {sorted(left.keys() ^ right.keys())}')
    for name in left:
        if left[name] != right[name]:
            raise AssertionError(f'{name}: bytes differ between {before} and {after}; '
                                 f'sha256 {hashlib.sha256(left[name]).hexdigest()} != '
                                 f'{hashlib.sha256(right[name]).hexdigest()}')
    # Values are a separately checked contract, in addition to byte equality.
    a = json.loads(left['fingerprints.json'])
    b = json.loads(right['fingerprints.json'])
    if set(a) != set(FINGERPRINT_KEYS) or a != b:
        raise AssertionError(f'fingerprint values differ: {a} != {b}')


def _environment(*, hashseed='0', timezone='UTC', language='C') -> dict[str, str]:
    # Retain only process/platform necessities. Do not inherit hidden analysis knobs.
    env = {key: os.environ[key] for key in (
        'PATH', 'SYSTEMROOT', 'WINDIR', 'HOME', 'USERPROFILE', 'TMP', 'TEMP', 'TMPDIR',
    ) if key in os.environ}
    env.update(PYTHONPATH=str(ROOT / 'src'), PYTHONHASHSEED=hashseed,
               TZ=timezone, LC_ALL=language, LANG=language, PYTHONUTF8='1',
               SOURCE_DATE_EPOCH=REFERENCE_EPOCH)
    return env


def _copy_project(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(
        '.git', '.quarto-needs', '.quarto', '_extensions', '_book', '_site', '__pycache__',
    ))


def run_matrix(source: Path, output: Path, *, inject_leak: str | None = None) -> list[Path]:
    """Run each independent variation in a newly initialized interpreter."""
    source, output = source.resolve(), output.resolve()
    language = collating_locale()
    variants = (
        ('reference', {}, 'outside-absolute', 'sorted'),
        ('hash', {'hashseed': '12345'}, 'outside-absolute', 'sorted'),
        ('timezone', {'timezone': 'America/Sao_Paulo'}, 'outside-absolute', 'sorted'),
        ('locale', {'language': language}, 'outside-absolute', 'sorted'),
        ('inside-relative', {}, 'inside-relative', 'sorted'),
        ('outside-relative', {}, 'outside-relative', 'sorted'),
        ('discovery', {}, 'outside-absolute', 'shuffled'),
    )
    results, probes = [], {}
    for name, overrides, root_form, order in variants:
        run = output / name
        project, artifacts = run / 'project', run / 'artifacts'
        _copy_project(source, project)
        artifacts.mkdir()
        if root_form == 'inside-relative':
            cwd, root_arg = project, '.'
        elif root_form == 'outside-relative':
            cwd, root_arg = run, 'project'
        else:
            cwd, root_arg = run, str(project)
        command = [sys.executable, str(Path(__file__).resolve()), 'worker',
                   '--root', root_arg, '--output', str(artifacts), '--order', order,
                   '--locale', overrides.get('language', 'C')]
        if inject_leak:
            command.extend(['--inject-leak', inject_leak])
        completed = subprocess.run(command, cwd=cwd, env=_environment(**overrides),
                                   capture_output=True, text=True, encoding='utf-8', timeout=180)
        if completed.returncode:
            raise AssertionError(f'{name} worker failed ({completed.returncode}):\n'
                                 f'{completed.stdout}\n{completed.stderr}')
        probes[name] = json.loads((run / 'probe.json').read_bytes())
        results.append(artifacts)
        if len(results) > 1:
            compare_artifacts(results[0], artifacts)
    assert probes['reference']['hash'] != probes['hash']['hash'], 'hash seed did not change'
    assert probes['reference']['collation'] != probes['locale']['collation'], 'locale fell back to C'
    assert probes['reference']['localHour'] != probes['timezone']['localHour'], 'TZ had no effect'
    assert probes['discovery']['reordered'], 'no real discovery order perturbation occurred'
    assert probes['inside-relative']['rootArgument'] == '.'
    assert probes['outside-relative']['rootArgument'] == 'project'
    _write_json(output / 'probes.json', probes)
    return results


def _worker(args) -> None:
    # A failed locale activation is an error, never a fallback or skip. The name is
    # passed explicitly because Windows' setlocale(LC_ALL, '') consults the system
    # locale rather than LC_ALL, which would make this axis silently inert there.
    selected_locale = locale.setlocale(locale.LC_ALL, args.locale)
    if hasattr(time, 'tzset'):
        time.tzset()
    elif sys.platform == 'win32':
        # Windows' CRT accepts POSIX TZ, not an IANA name. Apply the equivalent
        # offset for the pinned September 2026 instant (Brazil has no DST).
        import ctypes
        crt = ctypes.CDLL('ucrtbase')
        crt._putenv_s.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        crt._putenv_s(b'TZ', b'BRT3' if os.environ['TZ'] == 'America/Sao_Paulo' else b'UTC0')
        crt._tzset()
    artifacts = Path(args.output).resolve()
    project = Path(args.root)
    from quarto_needs.cli_entry import main as cli_main
    from quarto_needs.analysis import analyze_project
    from quarto_needs.baseline import build_baseline, render_baseline
    from quarto_needs.config import load_config
    from quarto_needs.parser import _is_localized_qmd
    from quarto_needs.source_index import build_source_index

    original_rglob = Path.rglob
    discovery = []

    def perturbed_rglob(path, pattern, *positional, **kwargs):
        paths = sorted(original_rglob(path, pattern, *positional, **kwargs))
        if pattern == '*.qmd':
            before = list(paths)
            if args.order == 'shuffled':
                random.Random(12345).shuffle(paths)
                if len(paths) > 1 and paths == before:
                    paths.reverse()
            discovery.append((before != paths, [p.name for p in paths]))
        return iter(paths)

    Path.rglob = perturbed_rglob
    try:
        def cli(*arguments):
            log = io.StringIO()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                code = cli_main(['--root', args.root, *arguments])
            if code != 0:
                raise AssertionError(f'CLI {arguments} exited {code}: {log.getvalue()}')

        cli('scan')
        shutil.copyfile(project / '.quarto-needs/needs.json', artifacts / 'needs.json')
        indexes = list((project / '_extensions').rglob('generated-index.lua'))
        assert len(indexes) == 1, f'expected one Lua index, got {indexes}'
        shutil.copyfile(indexes[0], artifacts / 'generated-index.lua')
        cli('baseline', 'create', '--output', str(artifacts / 'baseline.json'))
        for fmt in ('json', 'csv', 'markdown', 'sarif', 'junit', 'reqif', 'jsonld'):
            cli('export', '--format', fmt, '--output', str(artifacts / f'export-{fmt}'))

        # Also exercise the scanner's explicit file-list entry point, in a
        # genuinely shuffled order, and compare its baseline to CLI discovery.
        root = project.resolve()
        files = [p for p in root.rglob('*.qmd')
                 if not any(part.startswith(('.', '_')) for part in p.relative_to(root).parts[:-1])
                 and not _is_localized_qmd(p)]
        config = load_config(project)
        snapshot = analyze_project(project, files=files, config=config).snapshot
        assert snapshot is not None
        baseline = build_baseline(snapshot, config)
        explicit = render_baseline(baseline).encode('utf-8')
        assert explicit == (artifacts / 'baseline.json').read_bytes(), 'explicit file list changed baseline'
        _write_json(artifacts / 'fingerprints.json', {key: baseline[key] for key in FINGERPRINT_KEYS})
        _write_json(artifacts / 'source-index.json', {
            key: [dict(file=span.file, line=span.line, start=span.start, end=span.end,
                       kind=span.kind, presentationOnly=span.presentation_only) for span in spans]
            for key, spans in build_source_index(project).items()
        })
        probe = dict(hash=hash('quarto-needs-reproducibility'), locale=selected_locale,
                     collation=sorted(COLLATION_SAMPLE, key=locale.strxfrm),
                     localHour=time.localtime(int(REFERENCE_EPOCH)).tm_hour,
                     cwd=str(Path.cwd()), rootArgument=args.root,
                     reordered=any(changed for changed, _ in discovery),
                     discovery=discovery[0][1])
        _write_json(artifacts.parent / 'probe.json', probe)
        if args.inject_leak:
            # Deliberately faulty writer: demonstrate a real environment/order
            # leak reaching persisted bytes. Never runs in production code.
            value = {'hash': probe['hash'], 'timezone': probe['localHour'],
                     'locale': probe['collation'], 'cwd': probe['cwd'],
                     'discovery': probe['discovery']}[args.inject_leak]
            _write_json(artifacts / 'injected-leak.json', value)
    finally:
        Path.rglob = original_rglob


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    matrix = sub.add_parser('matrix')
    matrix.add_argument('--root', type=Path, default=ROOT / 'examples/quarto-needs')
    matrix.add_argument('--output', type=Path, required=True)
    worker = sub.add_parser('worker')
    worker.add_argument('--root', required=True)
    worker.add_argument('--output', required=True)
    worker.add_argument('--order', choices=('sorted', 'shuffled'), required=True)
    worker.add_argument('--locale', required=True)
    worker.add_argument('--inject-leak', choices=('hash', 'timezone', 'locale', 'cwd', 'discovery'))
    compare = sub.add_parser('compare')
    compare.add_argument('directories', type=Path, nargs='+')
    args = parser.parse_args(argv)
    if args.command == 'worker':
        _worker(args)
    elif args.command == 'matrix':
        runs = run_matrix(args.root, args.output)
        probes = json.loads((args.output / 'probes.json').read_bytes())
        print(f'{len(runs)} subprocess variations: identical artifacts and fingerprints')
        # Name the locale that was actually activated, so a run's evidence shows
        # which collation rule the comparison was made under.
        print(f"collation locale exercised: {probes['locale']['locale']}")
    else:
        if len(args.directories) < 2:
            parser.error('compare requires at least two artifact directories')
        for directory in args.directories[1:]:
            compare_artifacts(args.directories[0], directory)
        print(f'{len(args.directories)} runtimes: identical artifacts and fingerprints')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
