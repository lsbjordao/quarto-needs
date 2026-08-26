# Task 1: Clear the inherited Milestone 1 debts

> Extracted from `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime dependency. `referencing` enters the `test` optional dependency group only; it already ships as a `jsonschema` dependency.
- One analysis per command invocation. `baseline create`, `diff`, and `impact` each call `analyze_project` exactly once, matching the Milestone 1 guarantee locked by `tests/test_cli.py`.
- Preserve every existing signature and documented behavior: `parse_qmd`, `parse_project`, `RequirementsGraph.build`, `validate`, `coverage`, `export_graph`, `export_lua_index`, `cli.build`, `build_v1_payload`, `write_build_outputs`, `report_from_snapshot`, `build_quality_report`, and every existing CLI command and shortcode.
- Preserve schema v1 exactly. Fingerprints and baselines are new, separately named and versioned schemas. Nothing in this milestone changes `needs.json` bytes for a project whose configuration and reference date are unchanged.
- Fingerprints exclude line numbers, `href` values, generated metrics, and every other derived value.
- Exit codes are stable: `0` success, `1` validation or policy failure, `2` invalid usage or configuration, `3` operational I/O or serialization failure.
- Generated artifacts are deterministic for a fixed configuration and a fixed reference date, and are written atomically through `export._write_atomic_text`.
- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
- Milestone 3 adds no Quarto shortcode and no `extensions.quartoNeeds` projection for diff or impact. `need-graph` and the interactive graph remain Milestone 5A.

## Task 1

Clear the inherited Milestone 1 debts

The three schema validators this milestone adds must not be built on a
deprecated API, so the migration comes first. The two test probes are
recorded as open debt in the Milestone 1 ledger and are cheap to close
while the same files are open.

**Files:**
- Modify: `tests/test_v1_contract.py:50-62`
- Modify: `tests/test_relations.py`
- Modify: `tests/test_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `tests/test_v1_contract.py::envelope_validator() -> Draft202012Validator` built on `referencing`, reused by Tasks 4, 8, and 10.

- [ ] **Step 1: Add `referencing` to the test extra**

In `pyproject.toml`, add `"referencing"` to the `test` optional dependency list alongside `pytest` and `jsonschema`. Do not add it to runtime dependencies.

- [ ] **Step 2: Run the contract tests and record the deprecation warnings**

Run: `.venv/bin/python -m pytest tests/test_v1_contract.py -q`

Expected: PASS with exactly 2 `jsonschema.RefResolver` `DeprecationWarning` entries. Record the count; Step 4 asserts it reaches zero.

- [ ] **Step 3: Rewrite `envelope_validator` on `referencing`**

Replace the `RefResolver` import and helper in `tests/test_v1_contract.py`:

```python
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def envelope_validator() -> Draft202012Validator:
    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(
        "https://quarto-needs.dev/schema/needs.schema.json",
        Resource.from_contents(
            load_json(SCHEMAS / "needs.schema.json"),
            default_specification=Draft202012Validator.META_SCHEMA,
        ),
    )
    return Draft202012Validator(schema, registry=registry)
```

- [ ] **Step 4: Run the contract tests and verify the warnings are gone**

Run: `.venv/bin/python -m pytest tests/test_v1_contract.py -q -W error::DeprecationWarning`

Expected: PASS with no deprecation warning. Promoting the warning to an error proves the migration rather than merely hiding it.

- [ ] **Step 5: Write the failing `authored_name` boundary test**

The v1 writer must never leak the additive `Relation.authored_name` field. Add to `tests/test_relations.py`:

```python
def test_engineering_object_to_dict_omits_authored_name() -> None:
    """authored_name is additive internal state and must stay out of v1 output."""
    from quarto_needs.model import EngineeringObject, Relation

    obj = EngineeringObject(id="REQ-1", type="functional-requirement", title="T", status="draft")
    obj.relations.append(Relation("derives-from", "REQ-1", "STK-1", {}))
    obj.relations[0].authored_name = "derived-from"

    payload = obj.to_dict()

    assert payload["relations"][0]["type"] == "derives-from"
    assert "authored_name" not in payload["relations"][0]
```

- [ ] **Step 6: Run it**

Run: `.venv/bin/python -m pytest tests/test_relations.py::test_engineering_object_to_dict_omits_authored_name -v`

Expected: PASS. This is a characterization test — the behavior is already correct and this pins it. If it fails, the constructor signature drifted; read `src/quarto_needs/model.py` and adapt the construction, not the assertion.

- [ ] **Step 7: Write the deferred CLI probes**

Add to `tests/test_cli.py`:

```python
@pytest.mark.parametrize("arguments", [["check"], ["coverage"], ["export"], ["trace", "DUP-1"]])
def test_invalid_input_still_runs_exactly_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    """A structurally invalid project must not be re-analyzed while reporting."""
    write_duplicate_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), *arguments])
    assert calls == 1


def test_trace_orders_ids_case_insensitively_and_survives_cycles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Traversal must terminate on a cycle and sort deterministically."""
    (tmp_path / "cycle.qmd").write_text(
        "::: {.need #req-b type=need status=draft}\n"
        "references: REQ-A\n"
        "\n## B\nB body.\n:::\n"
        "\n"
        "::: {.need #REQ-A type=need status=draft}\n"
        "references: req-b\n"
        "\n## A\nA body.\n:::\n",
        encoding="utf-8",
    )

    assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0

    output = capsys.readouterr().out
    assert "req-b" in output
```

- [ ] **Step 8: Run the probes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "invalid_input_still_runs or survives_cycles"`

Expected: PASS. If the cycle test hangs, traversal lacks a visited set — that is a real defect; fix `cli` traversal to track visited IDs before continuing.

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS with **zero** warnings. The two permitted `RefResolver` warnings that every previous milestone carried are now gone.

- [ ] **Step 10: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add pyproject.toml tests/test_v1_contract.py tests/test_relations.py tests/test_cli.py
  git commit -m "chore: clear milestone one test debts"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```
