from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from quarto_needs.config import ConfigurationError, Gates, load_config
from quarto_needs.metrics import CoverageMeasure, ScopeMetrics
from quarto_needs.quality import GATE_PERCENT_ATTRIBUTES, build_quality_report, evaluate_gates


@pytest.mark.parametrize('attribute,strength', GATE_PERCENT_ATTRIBUTES.items())
def test_empty_percentage_is_not_measured(attribute, strength):
    gates = replace(Gates(scope='catalog'), **{attribute: 100.0})
    scope = ScopeMetrics('catalog', 0, {}, {strength: CoverageMeasure(0, 0)}, {})
    gate = evaluate_gates(scopes={'catalog': scope}, findings=(), gates=gates)[1]
    assert not gate.passed
    assert gate.to_dict()['measurementStatus'] == 'empty'
    assert gate.actual is None
    assert CoverageMeasure(0, 0).percent == 100.0


@pytest.mark.parametrize('attribute,strength', GATE_PERCENT_ATTRIBUTES.items())
def test_missing_percentage_measurement_never_passes(attribute, strength):
    gates = replace(Gates(scope='catalog'), **{attribute: 0.0})
    for scopes in ({}, {'catalog': ScopeMetrics('catalog', 1, {}, {}, {})}):
        gate = evaluate_gates(scopes=scopes, findings=(), gates=gates)[1]
        assert not gate.passed
        assert gate.to_dict()['measurementStatus'] == 'unavailable'


@pytest.mark.requirement("FUN-021")
@pytest.mark.quarto_need_test_case("TC-033")
def test_unknown_scope_names_valid_scopes(tmp_path):
    (tmp_path / '.quarto-needs.toml').write_text(
        '[gates]\nscope = "aproved-requirements"\nmin-evidence = 100\n'
        '[queries.release]\nwhere = {status = "approved"}\n', encoding='utf-8')
    with pytest.raises(ConfigurationError) as error:
        load_config(tmp_path)
    for name in ('aproved-requirements', 'approved-requirements', 'catalog', 'release'):
        assert name in str(error.value)


@pytest.mark.parametrize('allow', [False, True])
def test_empty_scope_policy_is_explicit_in_report(tmp_path, capsys, allow):
    from quarto_needs.cli import _print_quality_text

    (tmp_path / '.quarto-needs.toml').write_text(
        'profile = "strict"\n[gates]\nmin-evidence = 100\n'
        f'allow-empty-scopes = {str(allow).lower()}\n', encoding='utf-8')
    report = build_quality_report(tmp_path)
    gate = report.gates[1]
    assert gate.passed is allow
    assert gate.to_dict()['measurementStatus'] == 'empty'
    assert report.exit_code() == (0 if allow else 1)
    _print_quality_text(report)
    output = capsys.readouterr().out
    assert '[PASS] min-evidence' not in output
    assert ('[WAIVED]' if allow else '[UNMEASURED]') in output
    assert 'matched no objects' in output


def test_missing_findings_cannot_pass_count_gates():
    gates = Gates(require_risk_mitigation=True)
    results = evaluate_gates(scopes={}, findings=None, gates=gates)
    assert all(not gate.passed for gate in results)
    assert all(gate.to_dict()['measurementStatus'] == 'unavailable' for gate in results)


@pytest.mark.parametrize('allow', [False, True])
def test_risk_gate_requires_a_measured_population(tmp_path, allow):
    (tmp_path / '.quarto-needs.toml').write_text(
        '[rules.REQ013]\nenabled = true\n[gates]\nrequire-risk-mitigation = true\n'
        f'allow-empty-scopes = {str(allow).lower()}\n', encoding='utf-8')
    gate = build_quality_report(tmp_path).gates[1]
    assert gate.passed is allow
    assert gate.to_dict()['measurementStatus'] == 'empty'


def test_structural_failure_never_produces_pass(tmp_path):
    (tmp_path / 'page.qmd').write_text(
        '::: {.need #X type=requirement}\n## X\n:::\n' * 2, encoding='utf-8')
    report = build_quality_report(tmp_path)
    assert report.structural_errors
    assert report.exit_code() == 1
    assert [(g.name, g.passed) for g in report.gates] == [('structural-analysis', False)]


def test_quality_schema_accepts_old_and_new_consumers(tmp_path):
    import json
    from jsonschema import Draft202012Validator

    schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/quality-v1.schema.json').read_text())
    validator = Draft202012Validator(schema)
    payload = build_quality_report(tmp_path).to_dict()
    validator.validate(payload)
    payload['gates'][0].pop('measurementStatus')
    payload['gates'][0]['futureField'] = 'ignored'
    validator.validate(payload)
    payload['gates'][0]['measurementStatus'] = 'pretend-pass'
    assert list(validator.iter_errors(payload))


@pytest.mark.parametrize('enabled', ['', '[rules.REQ013]\nenabled = false\n'])
def test_risk_rule_dependency_cannot_be_waived(tmp_path, enabled):
    (tmp_path / '.quarto-needs.toml').write_text(
        '[gates]\nrequire-risk-mitigation = true\nallow-empty-scopes = true\n' + enabled,
        encoding='utf-8')
    with pytest.raises(ConfigurationError, match='REQ013'):
        load_config(tmp_path)


def test_empty_waiver_does_not_waive_missing_measurement():
    gates = Gates(min_evidence=100, allow_empty_scopes=True)
    gate = evaluate_gates(scopes={}, findings=(), gates=gates)[1]
    assert not gate.passed
    assert gate.measurement_status == 'unavailable'


def test_findings_iterator_is_measured_once():
    from quarto_needs.diagnostics import Finding

    gate = evaluate_gates(scopes={}, findings=iter([Finding('REQ013', 'error', 'risk')]),
                          gates=Gates(require_risk_mitigation=True), risk_population=1)[1]
    assert not gate.passed
    assert gate.actual == 1


def test_empty_waiver_is_boolean_and_changes_configuration_fingerprint(tmp_path):
    path = tmp_path / '.quarto-needs.toml'
    path.write_text('[gates]\nallow-empty-scopes = "true"\n', encoding='utf-8')
    with pytest.raises(ConfigurationError, match='boolean'):
        load_config(tmp_path)
    path.write_text('[gates]\nallow-empty-scopes = false\n', encoding='utf-8')
    default = load_config(tmp_path)
    path.write_text('[gates]\nallow-empty-scopes = true\n', encoding='utf-8')
    allowed = load_config(tmp_path)
    assert default.canonical_document() != allowed.canonical_document()


def test_waived_gates_are_visible_in_junit_and_markdown(tmp_path):
    import xml.etree.ElementTree as ET
    from quarto_needs.analysis import analyze_project
    from quarto_needs.exporters import junit_export, markdown_export

    (tmp_path / '.quarto-needs.toml').write_text(
        '[gates]\nmin-evidence = 100\nallow-empty-scopes = true\n', encoding='utf-8')
    report = build_quality_report(tmp_path)
    suites = ET.fromstring(junit_export.render(report))
    assert suites.attrib['skipped'] == '1'
    assert suites.find('testsuite').attrib['skipped'] == '1'
    assert suites.find('.//skipped') is not None
    config = load_config(tmp_path)
    snapshot = analyze_project(tmp_path, config=config).snapshot
    text = markdown_export.render(snapshot, config)
    assert '[WAIVED] min-evidence' in text
    assert 'All gates passed.' not in text


@pytest.mark.parametrize('priority,passed,status', [('medium', False, 'empty'), ('high', True, 'measured')])
def test_risk_population_matches_rule_eligibility(tmp_path, priority, passed, status):
    (tmp_path / '.quarto-needs.toml').write_text(
        '[rules.REQ013]\nenabled = true\n[gates]\nrequire-risk-mitigation = true\n', encoding='utf-8')
    (tmp_path / 'risk.qmd').write_text(
        f'::: {{.need #R type=risk priority={priority}}}\n## Risk\n:::\n'
        '::: {.need #C type=component mitigates=R}\n## Control\n:::\n', encoding='utf-8')
    gate = build_quality_report(tmp_path).gates[1]
    assert gate.passed is passed
    assert gate.measurement_status == status
