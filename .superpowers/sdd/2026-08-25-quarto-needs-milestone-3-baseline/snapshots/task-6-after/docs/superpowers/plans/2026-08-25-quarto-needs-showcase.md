# Quarto-Needs IAM Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build reusable graph-backed Quarto shortcodes and a 60-plus-object IAM requirements showcase.

**Architecture:** The existing Python pre-render pipeline remains canonical and writes `needs.json`. A focused Lua view adapter loads that graph, applies safe exact-match filters, and returns Pandoc-native tables/lists plus Mermaid code blocks; HTML-only JavaScript progressively enhances generated tables. The example consumes the public shortcode surface and doubles as an integration fixture.

**Tech Stack:** Python 3.10+, pytest, Quarto/Pandoc Lua, Mermaid, CSS, vanilla JavaScript

**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-showcase-design.md`

## Global Constraints

- Do not add runtime dependencies.
- Do not evaluate author-provided Python or Lua expressions.
- Keep requirements semantics in `src/quarto_needs`; Lua is a read-only presentation adapter.
- Preserve `{{< need ID title=true >}}` compatibility.
- Render usable static output in HTML, PDF, and DOCX; interactivity is progressive HTML enhancement.
- `_extensions/quarto-needs` is canonical; the example copy must match it.
- The workspace currently has no `.git`, so verification replaces commit steps.

---

### Task 1: Stable view payload and extension synchronization

**Files:**
- Modify: `src/quarto_needs/export.py`
- Modify: `tools/quarto_needs_pre_render.py`
- Create: `tests/test_export.py`
- Create: `tests/test_extension_sync.py`

**Interfaces:**
- Consumes: `EngineeringObject.to_dict()`, `coverage()`, and repository `_extensions/quarto-needs` assets.
- Produces: stable JSON fields and `sync_extension(project_root: Path) -> None`.

- [ ] **Step 1: Write failing export and synchronization tests**

```python
def test_export_keeps_attributes_relations_and_backlinks(tmp_path: Path):
    req = EngineeringObject(
        "REQ-1", "functional-requirement", "Login", status="approved",
        attributes={"priority": "high", "tags": "security;login"},
        relations=[Relation("verified-by", "REQ-1", "TC-1")],
    )
    tc = EngineeringObject("TC-1", "test-case", "Login test", status="passed")
    output = tmp_path / "needs.json"
    export_graph(output, [req, tc], [])
    payload = json.loads(output.read_text())
    assert payload["objects"][0]["attributes"]["priority"] == "high"
    assert payload["relations"][0]["target"] == "TC-1"
    assert payload["backlinks"]["TC-1"] == [{"source": "REQ-1", "type": "verified-by"}]

def test_example_extension_matches_canonical_extension():
    for name in ("_extension.yml", "needs.lua", "shortcodes.lua", "needs.css"):
        assert (ROOT / "_extensions/quarto-needs" / name).read_bytes() == (
            ROOT / "examples/book/_extensions/quarto-needs" / name
        ).read_bytes()
```

- [ ] **Step 2: Run the focused tests and verify the new asset assertion fails**

Run: `.venv/bin/python -m pytest tests/test_export.py tests/test_extension_sync.py -q`

Expected: export assertions pass against the canonical JSON; synchronization fails because sync behavior does not exist yet.

- [ ] **Step 3: Add `sync_extension()` and call it before `build()`**

```python
def sync_extension(project_root: Path) -> None:
    source = REPO_ROOT / "_extensions" / "quarto-needs"
    target = project_root / "_extensions" / "quarto-needs"
    target.mkdir(parents=True, exist_ok=True)
    for asset in source.iterdir():
        if asset.is_file() and asset.name != "generated-index.lua":
            shutil.copy2(asset, target / asset.name)
```

- [ ] **Step 4: Run the focused tests**

Run: `.venv/bin/python -m pytest tests/test_export.py tests/test_extension_sync.py -q`

Expected: PASS after the initial example sync has run. Assets added by later tasks are picked up automatically.

### Task 2: Shared Lua graph loading, filtering, and rendering helpers

**Files:**
- Create: `_extensions/quarto-needs/views.lua`
- Modify: `_extensions/quarto-needs/_extension.yml`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Create: `tests/fixtures/views/index.qmd`
- Create: `tests/fixtures/views/_quarto.yml`
- Create: `tests/test_quarto_views.py`

**Interfaces:**
- Consumes: `.quarto-needs/needs.json` schema version 1.
- Produces: `views.load()`, `views.filter(objects, kwargs)`, `views.sort(objects, kwargs)`, `views.badge(kind, value)`, and `views.warning(message)`.

- [ ] **Step 1: Write a Quarto integration test with a skip guard**

```python
@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_filtered_table_list_and_count_render(tmp_path: Path):
    project = copy_fixture_project(tmp_path, "views")
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html = (project / "_site/index.html").read_text(encoding="utf-8")
    assert "REQ-APPROVED" in html
    assert "REQ-DRAFT" not in table_fragment(html, "approved-table")
    assert 'class="need-badge need-status need-status-approved"' in html
    assert 'data-need-count="1"' in html
```

- [ ] **Step 2: Run the integration test and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py::test_filtered_table_list_and_count_render -q`

Expected: FAIL because the new shortcodes are not registered.

- [ ] **Step 3: Implement safe data loading and exact-match filtering**

```lua
function M.filter(objects, kwargs)
  local result = {}
  for _, object in ipairs(objects) do
    if matches(object, "id", option_values(kwargs, "ids"))
      and matches(object, "type", option_values(kwargs, "types", "type"))
      and matches(object, "status", option_values(kwargs, "status"))
      and matches(attribute(object, "priority"), nil, option_values(kwargs, "priority"))
      and matches_tags(attribute(object, "tags"), option_values(kwargs, "tags")) then
      table.insert(result, object)
    end
  end
  return result
end
```

- [ ] **Step 4: Register `need-table`, `need-list`, and `need-count` using the shared helpers**

```lua
return {
  need = render_need_reference,
  ["need-table"] = render_need_table,
  ["need-list"] = render_need_list,
  ["need-count"] = render_need_count,
  ["need-matrix"] = render_need_matrix,
  ["need-flow"] = render_need_flow,
}
```

- [ ] **Step 5: Run the integration test**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py::test_filtered_table_list_and_count_render -q`

Expected: PASS.

### Task 3: Semantic badges and progressive table enhancement

**Files:**
- Modify: `_extensions/quarto-needs/needs.lua`
- Modify: `_extensions/quarto-needs/needs.css`
- Create: `_extensions/quarto-needs/needs.js`
- Modify: `tests/test_quarto_views.py`

**Interfaces:**
- Consumes: raw `type`, `status`, and `priority` values from need Div attributes and generated table spans.
- Produces: normalized `need-status-*`/`need-priority-*` classes and search/sort behavior for `.need-table`.

- [ ] **Step 1: Extend the render test with badge and search assertions**

```python
assert "need-priority-high" in html
assert "need-status-disapproved" in html
assert 'class="need-table-search"' in html
assert "needs.js" in html
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`

Expected: FAIL on missing semantic classes and JavaScript dependency.

- [ ] **Step 3: Render separate status and priority badges in `needs.lua`**

```lua
local function badge(kind, raw)
  local class = "need-" .. kind .. "-" .. slug(raw)
  return pandoc.Span({pandoc.Str(raw)}, pandoc.Attr("", {"need-badge", "need-" .. kind, class}))
end
```

- [ ] **Step 4: Add accessible color tokens and print fallbacks**

```css
.need-status-approved, .need-status-passed { color:#166534; background:#dcfce7; border-color:#86efac; }
.need-status-disapproved, .need-status-rejected, .need-status-failed { color:#991b1b; background:#fee2e2; border-color:#fca5a5; }
.need-priority-high { color:#9a3412; background:#ffedd5; border-color:#fdba74; }
@media print { .need-badge { background:transparent !important; border:1px solid currentColor; } }
```

- [ ] **Step 5: Add vanilla-JavaScript search and sortable headers**

```javascript
document.querySelectorAll("[data-need-table]").forEach((container) => {
  const table = container.querySelector("table");
  const input = container.querySelector(".need-table-search");
  input?.addEventListener("input", () => filterRows(table, input.value));
  table?.querySelectorAll("thead th").forEach((header, index) => {
    header.addEventListener("click", () => sortRows(table, index));
  });
});
```

- [ ] **Step 6: Run the focused test**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`

Expected: PASS.

### Task 4: Traceability matrix and Mermaid flow views

**Files:**
- Modify: `_extensions/quarto-needs/views.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Modify: `tests/test_quarto_views.py`

**Interfaces:**
- Consumes: filtered objects plus canonical `relations`.
- Produces: a linked Pandoc matrix table and a Mermaid `CodeBlock` for selected graph edges.

- [ ] **Step 1: Add failing matrix and flow assertions**

```python
assert 'id="verification-matrix"' in html
assert "REQ-APPROVED" in matrix_fragment(html)
assert "TC-LOGIN" in matrix_fragment(html)
assert "verified-by" in html
assert "REQ_APPROVED" in html or "REQ-APPROVED" in html
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`

Expected: FAIL because matrix and flow rendering are not implemented.

- [ ] **Step 3: Implement relation indexing and matrix cells**

```lua
local function relation_index(relations, relation_type)
  local index = {}
  for _, relation in ipairs(relations) do
    if relation.type == relation_type then
      index[relation.source .. "\0" .. relation.target] = true
    end
  end
  return index
end
```

- [ ] **Step 4: Implement bounded Mermaid graph generation**

```lua
local lines = {"flowchart " .. direction}
for _, object in ipairs(selected_objects) do
  table.insert(lines, node_id(object.id) .. '["' .. escape_mermaid(object.id .. "<br/>" .. object.title) .. '"]')
end
for _, relation in ipairs(selected_relations) do
  table.insert(lines, node_id(relation.source) .. " -->|" .. escape_mermaid(relation.type) .. "| " .. node_id(relation.target))
end
return pandoc.CodeBlock(table.concat(lines, "\n"), pandoc.Attr("", {"mermaid"}))
```

- [ ] **Step 5: Run the focused test**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`

Expected: PASS with rendered matrix and Mermaid SVG/HTML.

### Task 5: Expand the Aegis IAM example to at least 60 objects

**Files:**
- Modify: `examples/book/_quarto.yml`
- Modify: `examples/book/index.qmd`
- Create: `examples/book/context/stakeholders.qmd`
- Create: `examples/book/requirements/system.qmd`
- Create: `examples/book/requirements/functional.qmd`
- Create: `examples/book/requirements/non-functional.qmd`
- Create: `examples/book/architecture/components.qmd`
- Create: `examples/book/risks/security.qmd`
- Create: `examples/book/verification/test-cases.qmd`
- Create: `examples/book/verification/evidence.qmd`
- Modify: `examples/book/traceability.qmd`
- Create: `examples/book/matrices.qmd`
- Create: `examples/book/diagrams.qmd`
- Create: `examples/book/shortcodes.qmd`
- Create: `tests/test_example_project.py`

**Interfaces:**
- Consumes: `.need` authoring syntax and the five shortcode APIs.
- Produces: at least 60 valid objects with complete approved-requirement verification and implementation links.

- [ ] **Step 1: Write the failing structural example test**

```python
def test_aegis_example_is_large_and_traceable():
    objects = parse_project(ROOT / "examples/book")
    findings = validate(objects)
    counts = Counter(obj.type for obj in objects)
    assert len(objects) >= 60
    assert counts["stakeholder-need"] >= 5
    assert counts["system-requirement"] >= 8
    assert counts["functional-requirement"] >= 15
    assert counts["non-functional-requirement"] >= 10
    assert counts["test-case"] >= 15
    assert not [finding for finding in findings if finding.severity == "error"]
    approved = [obj for obj in objects if obj.status == "approved" and obj.type.endswith("requirement")]
    assert all(any(rel.type in {"verified-by", "validated-by"} for rel in obj.relations) for obj in approved)
```

- [ ] **Step 2: Run the structural test and verify it fails at four objects**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q`

Expected: FAIL because the current example contains four objects.

- [ ] **Step 3: Author stakeholder, requirement, risk, architecture, test, and evidence catalogs**

Use IDs with stable prefixes: `IAM-STK`, `IAM-SYS`, `IAM-FUN`, `IAM-NFR`, `IAM-RISK`, `IAM-COMP`, `IAM-IF`, `IAM-TC`, and `IAM-EVD`. Each approved requirement includes a rationale, `implemented-by`, and `verified-by`; each target is declared exactly once.

- [ ] **Step 4: Add dashboards, tables, matrices, and diagrams to the book navigation**

```yaml
book:
  chapters:
    - index.qmd
    - context/stakeholders.qmd
    - part: Requirements
      chapters:
        - requirements/system.qmd
        - requirements/functional.qmd
        - requirements/non-functional.qmd
    - architecture/components.qmd
    - risks/security.qmd
    - verification/test-cases.qmd
    - verification/evidence.qmd
    - traceability.qmd
    - matrices.qmd
    - diagrams.qmd
    - shortcodes.qmd
```

- [ ] **Step 5: Run structural validation**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q`

Expected: PASS.

### Task 6: Documentation, synchronization, and full verification

**Files:**
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `Makefile`
- Synchronize: `examples/book/_extensions/quarto-needs/*`
- Modify: `tests/test_quarto_views.py`

**Interfaces:**
- Consumes: completed extension and example.
- Produces: documented authoring/query API and repeatable validation commands.

- [ ] **Step 1: Document every shortcode with one executable example and filter semantics**

Add a `Generated views` section to `README.md` covering `need-table`, `need-list`, `need-count`, `need-matrix`, and `need-flow`, plus the status/priority badge vocabulary.

- [ ] **Step 2: Synchronize extension assets through the pre-render helper**

Run: `cd examples/book && ../../.venv/bin/python ../../tools/quarto_needs_pre_render.py`

Expected: canonical extension assets are copied and `Quarto-Needs: 60+ objects` is printed.

- [ ] **Step 3: Run the complete Python test suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Validate the example graph**

Run: `.venv/bin/quarto-needs --root examples/book check`

Expected: zero errors; warnings are permitted only for deliberately draft/in-review requirements and are explained in the example.

- [ ] **Step 5: Render the example book from a clean output directory**

Run: `source .venv/bin/activate && quarto render examples/book`

Expected: exit code 0 and generated HTML for every chapter.

- [ ] **Step 6: Smoke-test the rendered site**

Run: `rg -n "need-status-approved|need-priority-high|need-table|verification-matrix|mermaid" examples/book/_book`

Expected: matches in generated HTML/CSS/JavaScript, with no missing-reference marker for declared IDs.
