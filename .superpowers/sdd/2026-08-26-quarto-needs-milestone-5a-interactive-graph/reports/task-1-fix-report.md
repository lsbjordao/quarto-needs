# Task 1 Fix Round Report — Freeze the public projection and its privacy contract

Branch: `milestone-3-baseline-diff-impact`. No commits made, no push, no branch changes.

All four in-scope files were untracked (`git status` shows `??`) before this round — the
previous implementer never committed them. This fix round edited all four:

- `tests/fixtures/graph/adversarial.qmd`
- `tests/test_graph_projection.py`
- `src/quarto_needs/graph_projection.py`
- `schemas/graph-public-v1.schema.json`

## Findings and what was changed

### 1. CRITICAL — rationale canary tested nothing

Root cause confirmed by tracing `parser.py`: `_collect_metadata` stops consuming metadata
lines the moment it hits a heading. The old fixture put `### Rationale` *after* the `##
Publishable title` heading, so the "Rationale" text was folded into `record.body`, and
`record.rationale` was always `''`. The canary search passed vacuously — it was never
searching a populated field.

**Fix**: replaced the `### Rationale` subsection with a metadata line placed *before* the
heading, inside the block:

```
::: {.need #ADV-1 type=functional-requirement status=approved priority=high tags="public-tag" secret-attribute="LEAKCANARYATTR7f3a"}
rationale: LEAKCANARYRATIONALE4e77 explains why and is equally private.

## Publishable title

LEAKCANARYBODY91cd is body prose and must never reach the browser.
:::
```

Verified by direct inspection (`analyze_project` in a temp dir):
`record.rationale == 'LEAKCANARYRATIONALE4e77 explains why and is equally private.'`,
`record.body == 'LEAKCANARYBODY91cd is body prose and must never reach the browser.'`,
`record.title == 'Publishable title'`, `record.attributes['secret-attribute'] ==
'LEAKCANARYATTR7f3a'`. All four canaries land where intended; title/body/attribute canaries
are unaffected.

Status: **fixed**, and the mutation experiment (below) proves the canary is now load-bearing —
without this fix, publishing `record.rationale` would not have failed the suite; with it, three
tests fail.

### 2. IMPORTANT — edge path had zero coverage

The fixture declared no relations. Added `verifies="ADV-1"` to `ADV-2`'s opening attribute
line, producing a real relation (`ADV-2 verifies -> ADV-1`, `v1_name="verifies"`,
`direct_label="Verifies"`) that flows through `PublicEdge`, `_label_for`, and the endpoint
filter in `build_projection`.

Added assertions to `test_publishable_content_is_present`:
```python
edge = next(item for item in payload["edges"] if item["source"] == "ADV-2" and item["target"] == "ADV-1")
assert edge["relation"] == "verifies"
assert edge["label"] == "Verifies"
```

Note on "put a canary in a relation attribute" (from the review): the `.qmd` parser has no
syntax for relation-level attributes — `parser.py` always constructs `RelationToken(key,
target, {}, location)` with a hardcoded empty attributes dict for relations declared in
`.qmd` files. `relation.attributes` is therefore always `{}` on this path, so a literal
"canary in a relation attribute" is not achievable through the fixture. The actual leak
surface M3 demonstrates is `relation.provenance` (source file + line), which the fixture
*does* populate realistically (`LocationRecord(file='adversarial.qmd', line=9, ...)`). I
added `test_no_source_location_reaches_the_projection`, asserting the literal source
filename `"adversarial.qmd"` never appears in the serialized output — this is what actually
catches M3 (and, redundantly with the href assertion, M5). Flagging this substitution
explicitly rather than silently declaring the literal instruction satisfied.

Status: **fixed** (edge path now exercised; label-leak path covered via provenance canary
check + positive label assertion instead of a relation-attribute canary, which the parser
cannot support today).

### 3. IMPORTANT — href path had zero coverage in either direction

Added a positive assertion in `test_publishable_content_is_present`:
```python
assert node["href"] == "#ADV-1"
```
This fails under M4 (href dropped → `KeyError`) and under M5 (href leaks the real path →
value mismatch). Also added `"href"` to the schema's node `required` list, so M4 is
independently caught by `test_projection_validates_against_its_schema`.

Status: **fixed**.

### 4. IMPORTANT — `view.limits` and `impact` copied wholesale

- Added `PublicImpactEntry` (frozen dataclass: `id`, `origin`, `distance`, `path`, optional
  `classification`), matching the schema's `impact` item shape. `GraphProjection.impact` is
  now typed `tuple[PublicImpactEntry, ...]`, and `to_dict()` calls `item.to_dict()` — which
  only ever emits its five declared fields. Feeding a raw dict into `impact` now fails loudly
  (`AttributeError: 'dict' object has no attribute 'to_dict'`) instead of being copied
  wholesale, which is what a fails-closed boundary should do with a malformed input.
- `view.limits` is now built from the two known keys at both places it previously did a
  wholesale copy: in `build_projection` (`limits={key: int(source_limits.get(key,
  DEFAULT_LIMITS[key])) for key in PUBLIC_LIMIT_FIELDS}`) and in `to_dict()`
  (`"limits": {key: self.limits[key] for key in PUBLIC_LIMIT_FIELDS}`). An extra key in a
  caller-supplied `limits` mapping (e.g. `{"nodes": 5, "edges": 9, "secret": "..."}`) is now
  dropped at construction and would be dropped again at render even if it slipped past that.

Added two tests: `test_limits_are_built_from_known_keys_not_copied_wholesale` (builds a
projection with an extra `"secret"` key in `limits`, asserts it never reaches output) and
`test_impact_entries_are_built_from_named_fields` / `test_impact_cannot_smuggle_undeclared_keys_via_a_raw_mapping`.

Status: **fixed**. Note: `build_projection` still has no parameter to populate `impact` —
that's correct and untouched, per your instruction that impact-mode population belongs to a
later task. Only the *type* of the field and the serialization discipline changed.

### 5. IMPORTANT — `test_only_allowlisted_fields_are_emitted` was vacuous and root-blind

Rewrote it to:
- assert `payload["nodes"]` and `payload["edges"]` are non-empty before the subset checks run
  (so the checks aren't vacuously true on an empty list — edges was empty before finding #2's
  fixture change, which is exactly what let M2/M3 slip through undetected)
- check `set(payload) <= {"schemaVersion", "view", "nodes", "edges", "impact"}`
- check `set(payload["view"]) <= {"id", "mode", "limits", "layout", "seed"}`
- check `set(payload["view"]["limits"]) <= {"nodes", "edges"}`

Status: **fixed**.

### 6. IMPORTANT — `test_render_is_byte_stable` didn't pin the canonical form

Kept the original two-calls-in-one-process equality check, and added assertions on the
literal serialized form:
```python
assert first.startswith('{\n  "edges"')   # sort_keys=True, alphabetical top-level order
assert first.count("\n") > 4               # indent=2 present, not collapsed to one line
assert first.endswith("\n")
```
Also added `test_render_is_byte_stable_across_processes`, which renders the same fixture in
a fresh `sys.executable -c ...` subprocess and diffs the output byte-for-byte against the
in-process render, addressing the review's point that same-process comparison can't observe
cross-process variance.

Status: **fixed**. (The M7 mutation is caught by the same-process format-pinning assertion;
the cross-process test passed both before and after the fix since M7's bad formatting is
deterministic across processes too — it's a defense-in-depth addition, not what actually
catches M7. Flagging this so the mechanism is clear rather than overstated.)

### MINOR — unused imports

- `Sequence` removed from `graph_projection.py`'s import line (was unused).
- `pytest` in `tests/test_graph_projection.py` is now genuinely used
  (`pytest.raises(AttributeError)` in `test_impact_cannot_smuggle_undeclared_keys_via_a_raw_mapping`),
  so it was kept rather than removed — using it was the more useful fix than deleting the
  import, once that test existed.

Status: **fixed**.

## The two decisions you asked me not to touch

Both left alone:
- `render_projection` still does not validate against the schema at runtime. No `jsonschema`
  import added to `graph_projection.py`. Confirmed with `grep -n jsonschema
  src/quarto_needs/graph_projection.py` → no matches.
- `build_projection` still has no field-request / view-policy parameter. `impact` remains
  populated only via direct `GraphProjection` construction (as Task 2 will presumably do),
  not via `build_projection`.

## Mutation experiments

Baseline checksum of the fixed `src/quarto_needs/graph_projection.py`, taken once after all
fixes were in place and the strengthened suite passed clean, used to verify restoration after
every mutation:

```
1cf32ce177ef39e03777a2a41732227b4d12edb574a6dd8710466a1d8882addf  src/quarto_needs/graph_projection.py
```

For each mutation: apply → run `tests/test_graph_projection.py` → observe failure → restore
from the saved original → `diff` (clean) → `sha256sum -c` (SUCCESS).

### M2 — edges never emitted

Mutation: `edges = ()` in place of the edge-building comprehension in `build_projection`.

Result: **2 failed, 9 passed**
```
FAILED tests/test_graph_projection.py::test_only_allowlisted_fields_are_emitted
  AssertionError: fixture produced no edges; the allowlist check below would be vacuous
FAILED tests/test_graph_projection.py::test_publishable_content_is_present
  StopIteration  (no ADV-2->ADV-1 edge found)
```
Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

### M3 — `_label_for` leaks provenance

Mutation: `_label_for` body replaced with
`return str(dict(relation.attributes)) + str(relation.provenance)`.

Result: **2 failed, 9 passed**
```
FAILED tests/test_graph_projection.py::test_no_source_location_reaches_the_projection
  AssertionError: a source file name reached the public projection
  'adversarial.qmd' is contained here: ...LocationRecord(file='adversarial.qmd', line=9, anchor='ADV-2'),)...
FAILED tests/test_graph_projection.py::test_publishable_content_is_present
  AssertionError: assert "{}(LocationR...or='ADV-2'),)" == 'Verifies'
```
Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

### M4 — href dropped entirely

Mutation: removed the `"href": self.href` line from `PublicNode.to_dict()`.

Result: **2 failed, 9 passed**
```
FAILED tests/test_graph_projection.py::test_projection_validates_against_its_schema
  jsonschema.exceptions.ValidationError: 'href' is a required property
FAILED tests/test_graph_projection.py::test_publishable_content_is_present
  KeyError: 'href'
```
Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

### M5 — href leaks `record.locations[0].file`

Mutation: `_public_href` returns `record.locations[0].file + "#" + record.id`.

Result: **2 failed, 9 passed**
```
FAILED tests/test_graph_projection.py::test_no_source_location_reaches_the_projection
  AssertionError: a source file name reached the public projection
  "href": "adversarial.qmd#ADV-1", ...
FAILED tests/test_graph_projection.py::test_publishable_content_is_present
  AssertionError: assert 'adversarial.qmd#ADV-1' == '#ADV-1'
```
Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

### M7 — canonical form dropped (`sort_keys`, `indent`)

Mutation: `render_projection` returns
`json.dumps(projection.to_dict(), ensure_ascii=False) + "\n"`.

Result: **1 failed, 10 passed**
```
FAILED tests/test_graph_projection.py::test_render_is_byte_stable
  AssertionError: top-level keys are not sorted
  assert False = '...startswith('{\n  "edges"')
  (actual: '{"schemaVersion": "graph-public-v1", "view": {...
```
Note: `test_render_is_byte_stable_across_processes` still passed under this mutation — M7's
bad formatting is deterministic across processes, so cross-process comparison alone would not
have caught it. It is the explicit format-pinning assertions in
`test_render_is_byte_stable` that catch it.
Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

### Rationale leak

Mutation: added `rationale: str = ""` field to `PublicNode`, populated it from
`record.rationale` in `build_projection`, and added `"rationale": self.rationale` to
`PublicNode.to_dict()` — i.e. exactly the kind of change the review warned a future
implementer might make without thinking about publication policy.

Result: **3 failed, 8 passed**
```
FAILED tests/test_graph_projection.py::test_no_denied_value_reaches_the_projection
  AssertionError: LEAKCANARYRATIONALE4e77 reached the public projection
FAILED tests/test_graph_projection.py::test_projection_validates_against_its_schema
  jsonschema.exceptions.ValidationError: Additional properties are not allowed ('rationale' was unexpected)
FAILED tests/test_graph_projection.py::test_only_allowlisted_fields_are_emitted
  AssertionError: unexpected keys: {..., 'rationale'}
```
This is the direct rebuttal of the review's central finding: before the fixture fix, this
same mutation would have left `test_no_denied_value_reaches_the_projection` passing, because
`record.rationale` was always `''`. It now fails first, and by name, on the canary itself.

Restoration: `diff` clean, `sha256sum -c` → SUCCESS.

## Test results

Targeted suite after all fixes (final state, no mutations applied):
```
$ .venv/bin/python -m pytest tests/test_graph_projection.py -q
...........
11 passed in 0.28s
```

Full suite:
```
$ .venv/bin/python -m pytest -q
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 76%]
..................................................................       [100%]
282 passed in 232.85s (0:03:52)
```
No failures, no new warnings observed in the tail output. Nothing outside the four in-scope
files was touched — `src/quarto_needs/exporters/`, `tests/test_export_*.py`, and
`schemas/vendor/` were not read or modified.

## Files changed

- `/home/lsbjordao/Repos/quarto-needs/tests/fixtures/graph/adversarial.qmd`
- `/home/lsbjordao/Repos/quarto-needs/tests/test_graph_projection.py`
- `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/graph_projection.py`
- `/home/lsbjordao/Repos/quarto-needs/schemas/graph-public-v1.schema.json`

No other files touched. No commit made (task brief's checkpoint step was not run, since this
is a fix round on top of already-untracked files and no commit was requested by name in this
round's instructions beyond the standard report).

## Findings not fixed

None. All six review findings (rationale canary, edge coverage, href coverage, limits/impact
wholesale copy, vacuous allowlist test, non-pinned canonical form) plus the two MINOR unused
imports were addressed and each corresponding mutation was demonstrated to fail before being
restored.

One deviation from the letter of the review worth restating: "put a canary in a relation
attribute" (finding #2) was not literally achievable — the `.qmd` parser hardcodes relation
attributes to `{}` for every relation declared via `.qmd` syntax (`parser.py`, the
`RelationToken(key, target, {}, relation_location)` call). The equivalent and actually
effective coverage was added against `relation.provenance` instead, which is the real field
M3's mutation reads from. If relation-level attributes are meant to be author-settable
through `.qmd` syntax at some point, that is a parser capability gap outside this task's file
scope, not a projection-module gap.
