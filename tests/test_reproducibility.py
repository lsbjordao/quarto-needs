from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reproducibility', ROOT / 'tools/reproducibility.py')
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'authored'
    root.mkdir()
    for name, content in {
        'z.qmd': '::: {.need #R type=functional-requirement status=approved implemented-by=C verified-by=T}\n## Requisito ágil\n:::\n',
        'a.qmd': '::: {.need #C type=component status=implemented}\n## Componente\n:::\n',
        'á.qmd': '::: {.need #T type=test-case status=passed evidenced-by=E}\n## Teste\n:::\n::: {.need #E type=evidence status=verified}\n## Evidência\n:::\n',
    }.items():
        (root / name).write_text(content, encoding='utf-8')
    return root


REQUIRE_COLLATION = 'QUARTO_NEEDS_REQUIRE_COLLATION'


@pytest.fixture
def collation_locale():
    """The one prerequisite the default test suite is allowed to lack.

    Slim images, devcontainers and most CI containers ship no generated
    locale, so seven unrelated red tests would greet every contributor. The
    requirement belongs to the gate, not to `pytest -q`: CI sets
    QUARTO_NEEDS_REQUIRE_COLLATION=1 and keeps failing exactly as before.

    Deliberately narrow. It catches only CollationLocaleUnavailable, raised
    at one place for one reason; every other harness failure still fails,
    because a skip is even easier to overlook than a vacuous pass.
    """
    try:
        return harness.collating_locale()
    except harness.CollationLocaleUnavailable as unavailable:
        if os.environ.get(REQUIRE_COLLATION) == '1':
            raise
        pytest.skip(f'{unavailable} Or set {REQUIRE_COLLATION}=1 to fail instead of skipping.')


@pytest.mark.requirement("NFR-010")
@pytest.mark.quarto_need_test_case("TC-034")
def test_subprocess_perturbations_preserve_artifacts(collation_locale, project, tmp_path):
    runs = harness.run_matrix(project, tmp_path / 'runs')
    assert len(runs) >= 7
    payload = json.loads((runs[0] / 'fingerprints.json').read_bytes())
    assert set(payload) == {'configurationFingerprint', 'semanticGraphFingerprint', 'representationFingerprint'}
    assert all(len(value) == 64 for value in payload.values())


@pytest.mark.parametrize('leak', ['hash', 'timezone', 'locale', 'cwd', 'discovery'])
def test_harness_detects_injected_leak(collation_locale, project, tmp_path, leak):
    with pytest.raises(AssertionError, match='injected-leak'):
        harness.run_matrix(project, tmp_path / 'runs', inject_leak=leak)


def _every_field_is_justified(fields: dict[str, str]) -> bool:
    return all(reason.strip() for reason in fields.values())


def test_volatile_allowlist_requires_review_of_fields_and_justifications():
    # This reviewed digest binds the complete field -> justification mapping.
    # Adding an exclusion requires a reason and an explicit review of this lock.
    # VOLATILE_FIELDS is empty -- the best possible result -- and `all()` over
    # nothing is True, so the justification check is exercised against a
    # known-bad entry first. Otherwise it would read as a check while verifying
    # nothing, and would first run for real on the day it is needed.
    assert not _every_field_is_justified({'generatedAt': '  '})
    assert _every_field_is_justified(harness.VOLATILE_FIELDS)
    document = json.dumps(harness.VOLATILE_FIELDS, sort_keys=True, separators=(',', ':'))
    assert hashlib.sha256(document.encode()).hexdigest() == '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'


def test_comparator_rejects_missing_artifacts(tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir()
    right.mkdir()
    (left / 'lost.json').write_bytes(b'{}')
    with pytest.raises(AssertionError, match='artifact paths'):
        harness.compare_artifacts(left, right)


def test_source_discovery_is_ordered_before_consumption(project, monkeypatch):
    from quarto_needs.source_index import _sources, build_source_index

    original = Path.rglob
    before = build_source_index(project)
    monkeypatch.setattr(Path, 'rglob', lambda path, pattern: iter(reversed(sorted(original(path, pattern)))))
    # The public index already sorts at its boundary; discovery itself should
    # also be deterministic for future consumers of this mapping.
    assert build_source_index(project) == before
    assert list(_sources(project, None)) == ['a.qmd', 'z.qmd', 'á.qmd']


def test_collating_locale_is_verified_rather_than_assumed(collation_locale):
    import locale as locale_module

    # The chosen locale must actually reorder text relative to C.
    assert collation_locale in harness.LOCALE_CANDIDATES
    previous = locale_module.setlocale(locale_module.LC_ALL)
    try:
        locale_module.setlocale(locale_module.LC_ALL, 'C')
        under_c = sorted(harness.COLLATION_SAMPLE, key=locale_module.strxfrm)
        locale_module.setlocale(locale_module.LC_ALL, collation_locale)
        assert sorted(harness.COLLATION_SAMPLE, key=locale_module.strxfrm) != under_c
    finally:
        locale_module.setlocale(locale_module.LC_ALL, previous)


def test_collating_locale_refuses_a_silent_c_fallback(monkeypatch):
    # Runs on every machine, including one with no locale at all: the refusal
    # to fall back to C is the contract, and it must never be what gets skipped.
    monkeypatch.setattr(harness, 'LOCALE_CANDIDATES', ('xx_XX.INVALID',))
    with pytest.raises(harness.CollationLocaleUnavailable, match='collates differently from C'):
        harness.collating_locale()
