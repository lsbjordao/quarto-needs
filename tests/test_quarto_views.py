from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def copy_fixture_project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    shutil.copytree(ROOT / "tests" / "fixtures" / name, project)
    shutil.copytree(ROOT / "_extensions", project / "_extensions")
    return project


def build_c4_fixture_project(tmp_path: Path) -> Path:
    """Scan C4 source before Quarto consumes the generated projections."""
    project = copy_fixture_project(tmp_path, "c4")
    subprocess.run(
        [".venv/bin/quarto-needs", "--root", str(project), "scan"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return project


def render_views(tmp_path: Path) -> str:
    project = copy_fixture_project(tmp_path, "views")
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert not (project / "diagram.html").exists(), "need-flow leaked its temporary renderer output"
    return (project / "_site" / "index.html").read_text(encoding="utf-8")


def render_view_pages(tmp_path: Path) -> tuple[str, str]:
    """Render the fixture once and return the index and the nested detail page."""
    project = copy_fixture_project(tmp_path, "views")
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    site = project / "_site"
    return (
        (site / "index.html").read_text(encoding="utf-8"),
        (site / "nested" / "details.html").read_text(encoding="utf-8"),
    )


def docx_text(path: Path) -> str:
    """Strip DOCX markup so assertions read the words a reader actually sees."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    # Adjacent runs leave padding once their tags are stripped, so collapse
    # whitespace and assertions can read the phrase a reader actually sees.
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def pdf_text(path: Path) -> str:
    return subprocess.run(
        ["pdftotext", str(path), "-"], check=True, text=True, capture_output=True
    ).stdout


def render_views_to(tmp_path: Path, output_format: str) -> Path:
    project = copy_fixture_project(tmp_path / output_format, "views")
    subprocess.run(
        ["quarto", "render", str(project), "--to", output_format],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return project / "_site" / f"index.{output_format}"


def rendered_dom(tmp_path: Path) -> str:
    project = copy_fixture_project(tmp_path / "browser", "views")
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    result = subprocess.run(
        ["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--dump-dom", (project / "_site" / "index.html").as_uri()],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def browser_interaction_result(tmp_path: Path) -> dict[str, object]:
    """Exercise the generated controls in Chromium, then return their DOM result."""
    project = copy_fixture_project(tmp_path / "interaction", "views")
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html_path = project / "_site" / "index.html"
    driver = """
<script>
window.addEventListener("load", () => {
  const table = document.getElementById("secondary-table");
  const container = table.closest("[data-need-table]");
  const input = container.querySelector(".need-table-search");
  const rowIds = () => Array.from(table.tBodies[0].rows)
    .filter((row) => !row.hidden)
    .map((row) => row.cells[0].textContent.trim());
  const allIds = Array.from(document.querySelectorAll("[id]"), (element) => element.id);
  const result = {
    hasSearch: Boolean(input),
    idsAreUnique: new Set(allIds).size === allIds.length
  };
  if (input) {
    input.focus();
    input.value = "REQ-DRAFT";
    input.dispatchEvent(new InputEvent("input", {
      bubbles: true, data: "REQ-DRAFT", inputType: "insertText"
    }));
    result.typedSearch = rowIds();
    input.value = "";
    input.dispatchEvent(new InputEvent("input", {
      bubbles: true, data: "", inputType: "deleteContentBackward"
    }));
    const sort = table.querySelector("thead th button");
    if (sort) {
      sort.click();
      result.ascending = rowIds();
      sort.click();
      result.descending = rowIds();
    }
  }
  const output = document.createElement("output");
  output.id = "need-browser-result";
  output.textContent = JSON.stringify(result);
  document.body.appendChild(output);
});
</script>
"""
    html_path.write_text(
        html_path.read_text(encoding="utf-8").replace("</body>", driver + "</body>"),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "google-chrome",
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--dump-dom",
            html_path.as_uri(),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    match = re.search(
        r'<output id="need-browser-result">(?P<payload>[^<]+)</output>',
        result.stdout,
    )
    assert match, "Chromium did not complete the need-table interactions"
    return json.loads(match.group("payload"))


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_filtered_table_list_and_count_render(tmp_path: Path):
    """Removing view registration or exact-match filters breaks the rendered catalog."""
    html = render_views(tmp_path)

    assert "REQ-APPROVED" in html
    approved_table = html.split('id="approved-table"', 1)[1].split("</table>", 1)[0]
    assert "REQ-DRAFT" not in approved_table
    assert 'class="need-badge need-status need-status-approved"' in html
    assert "need-priority-high" in html
    assert "need-table-search" not in html
    assert 'data-need-count="1"' in html
    assert "needs.js" in html
    assert html.count('id="approved-table"') == 1
    assert html.count('id="approved-table-2"') == 1
    assert html.count('id="secondary-table"') == 1
    secondary_table = html.split('id="secondary-table"', 1)[1].split("</table>", 1)[0]
    assert secondary_table.index("REQ-DRAFT") < secondary_table.index("REQ-UNPRIORITIZED")


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_references_resolve_to_the_page_that_declares_the_need(tmp_path: Path):
    """Cross-page references target the declaring page; same-page ones stay anchors."""
    html = render_views(tmp_path)

    assert 'href="nested/details.html#TC-LOGIN"' in html
    assert "TC-LOGIN — Administrator login test" in html
    assert "need-ref-missing" not in html
    approved_table = html.split('id="approved-table"', 1)[1].split("</table>", 1)[0]
    assert 'href="#REQ-APPROVED"' in approved_table
    assert 'href="nested/details.html#TC-LOGIN"' in approved_table


@pytest.mark.skipif(
    shutil.which("quarto") is None or shutil.which("google-chrome") is None,
    reason="Quarto or Chrome is not installed",
)
def test_need_table_search_and_sort_work_in_chromium(tmp_path: Path):
    """Search and both sort directions work through real Chromium DOM events."""
    result = browser_interaction_result(tmp_path)

    assert result["hasSearch"] is True
    assert result["idsAreUnique"] is True
    assert result["typedSearch"] == ["REQ-DRAFT"]
    assert result["ascending"] == [
        "REQ-APPROVED",
        "REQ-DRAFT",
        "REQ-UNPRIORITIZED",
    ]
    assert result["descending"] == [
        "REQ-UNPRIORITIZED",
        "REQ-DRAFT",
        "REQ-APPROVED",
    ]


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_matrix_and_flow_render_relation_links(tmp_path: Path):
    """The flow is a rendered Mermaid diagram, never an unprocessed code block."""
    html = render_views(tmp_path)

    matrix = html.split('id="verification-matrix"', 1)[1].split("</table>", 1)[0]
    assert "REQ-APPROVED" in matrix
    assert "TC-LOGIN" in matrix
    assert "verified-by" in html
    assert re.search(r'<div class="need-flow-scroll">\s*<svg[^>]*class="[^"]*need-flow', html)
    assert '<pre class="mermaid' not in html
    assert "flowchart TD" not in html


def extract_inline_need_flow_svgs(html: str) -> list[str]:
    """Return the raw <svg>...</svg> markup of every inline need-flow diagram."""
    svgs = []
    for match in re.finditer(r'<svg\b[^>]*\bclass="[^"]*need-flow[^"]*"', html):
        end = html.find("</svg>", match.start())
        svgs.append(html[match.start() : end + len("</svg>")])
    return svgs


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_flow_svg_is_well_formed_and_keeps_full_view_box(tmp_path: Path):
    """HTML embeds the diagram as an inline SVG whose width/height match the viewBox.

    Quarto's mermaid-to-PNG pipeline screenshots through headless Chrome with
    the default ~800px viewport, and diagrams wider than that get cut at the
    right and bottom edges. The inline SVG keeps its intrinsic dimensions so
    the whole diagram is always present, and carries namespaced ids so two
    diagrams on one page cannot collide. Labels are rendered as plain SVG
    text (htmlLabels:false) because Mermaid mismeasures wrapped
    <foreignObject> labels, which would leave node text invisible once
    inlined. Attribute names are matched
    case-insensitively because Quarto's HTML post-processing lowercases them
    (the browser parser restores SVG casing per the HTML spec).
    """
    html = render_views(tmp_path)

    diagrams = extract_inline_need_flow_svgs(html)
    assert diagrams, "expected the need-flow diagram to be inlined as SVG"

    root_ids = []
    for diagram in diagrams:
        root_tag = diagram[: diagram.find(">")]
        view_box = re.search(r'\bviewbox\s*=\s*"([^"]+)"', root_tag, re.IGNORECASE)
        assert view_box, "inline diagram must declare a viewBox"
        parts = view_box.group(1).split()
        assert len(parts) == 4
        width = re.search(r'\bwidth\s*=\s*"' + re.escape(parts[2]) + '"', root_tag, re.IGNORECASE)
        height = re.search(r'\bheight\s*=\s*"' + re.escape(parts[3]) + '"', root_tag, re.IGNORECASE)
        assert width and height, "inline diagram width/height must match the viewBox"
        assert re.search(r'\brole\s*=\s*"img"', root_tag, re.IGNORECASE)
        # Node labels must be plain SVG <text> (htmlLabels:false). Mermaid
        # mismeasures wrapped <foreignObject> labels, and inlined clipped
        # foreignObject text is exactly the invisible-label bug.
        assert re.search(r"<text[\s>]", diagram), "node labels must render as SVG text"
        id_attr = re.search(r'\bid\s*=\s*"([^"]+)"', root_tag, re.IGNORECASE)
        assert id_attr, "inline diagram must carry a namespaced root id"
        root_ids.append(id_attr.group(1))
    assert len(root_ids) == len(set(root_ids)), "inline diagram ids must be unique"


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_flow_png_is_embedded_in_docx(tmp_path: Path):
    """DOCX output must embed the processed diagram instead of Mermaid source."""
    document = render_views_to(tmp_path, "docx")

    with zipfile.ZipFile(document) as archive:
        names = archive.namelist()
        xml = archive.read("word/document.xml").decode("utf-8")

    assert any(name.startswith("word/media/") and name.endswith(".png") for name in names)
    assert "flowchart TD" not in xml


@pytest.mark.skipif(
    shutil.which("quarto") is None
    or shutil.which("lualatex") is None
    or shutil.which("pdftotext") is None,
    reason="Quarto, LuaLaTeX, or pdftotext is not installed",
)
def test_flow_png_renders_in_pdf_without_source_code(tmp_path: Path):
    """PDF output must contain the diagram without printing the Mermaid program."""
    document = render_views_to(tmp_path, "pdf")
    extracted = subprocess.run(
        ["pdftotext", str(document), "-"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout

    assert document.stat().st_size > 0
    assert "flowchart TD" not in extracted


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_cards_render_catalog_labeled_outgoing_and_incoming_relations(tmp_path: Path) -> None:
    """Cards carry both directions with catalog labels and source-aware links."""
    index_html, details_html = render_view_pages(tmp_path)

    assert 'id="REQ-APPROVED"' in index_html
    assert "Need relations" in index_html
    assert "Verified by" in index_html
    assert 'href="nested/details.html#TC-LOGIN"' in index_html
    assert 'id="TC-LOGIN"' in details_html
    assert "Need backlinks" in details_html
    assert "Verifies" in details_html
    assert 'href="../index.html#REQ-APPROVED"' in details_html
    assert "No backlinks for REQ-DRAFT." in index_html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_backlinks_reports_unknown_id_without_empty_success_state(tmp_path: Path) -> None:
    """An unknown ID warns loudly instead of rendering as an empty result."""
    index_html, _ = render_view_pages(tmp_path)

    assert "Unknown need ID: UNKNOWN-NEED" in index_html
    assert 'class="need-view-warning"' in index_html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_relations_are_static_content_in_docx(tmp_path: Path) -> None:
    """DOCX readers get the relation text without any JavaScript."""
    text = docx_text(render_views_to(tmp_path, "docx"))

    assert "Need relations" in text
    assert "Verified by" in text
    assert "TC-LOGIN" in text
    assert "Need backlinks" in text
    assert "REQ-APPROVED" in text


@pytest.mark.skipif(
    shutil.which("quarto") is None
    or shutil.which("lualatex") is None
    or shutil.which("pdftotext") is None,
    reason="Quarto, LuaLaTeX, or pdftotext is not installed",
)
def test_relations_are_static_content_in_pdf(tmp_path: Path) -> None:
    """PDF readers get the same relation text as every other format."""
    text = pdf_text(render_views_to(tmp_path, "pdf"))

    assert "Need relations" in text
    assert "Verified by" in text
    assert "TC-LOGIN" in text
    assert "Need backlinks" in text
    assert "REQ-APPROVED" in text


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_dashboard_renders_precomputed_scopes_with_denominators(tmp_path: Path):
    html = render_views(tmp_path)

    assert "Quality dashboard" in html
    assert "Whole catalog (2 requirements)" in html
    assert "Approved requirements (1 requirements)" in html
    assert "Verification successful" in html
    assert "50.0% (1 of 2)" in html
    # Gap entries link back to the underlying objects.
    gaps = html.split("Implementation-effective gaps", 1)[1][:2000]
    assert 'href="#REQ-APPROVED"' in gaps
    assert 'href="#REQ-DRAFT"' in gaps
    assert "Dashboard report unavailable." not in html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_dashboard_renders_distributions_and_finding_counts(tmp_path: Path):
    """Projected breakdowns and finding severities must reach the reader."""
    html = render_views(tmp_path)

    catalog = html.split("need-dashboard-catalog", 1)[1].split("need-dashboard-approved", 1)[0]
    assert "Needs by type" in catalog
    assert "Needs by status" in catalog
    assert "Needs by priority" in catalog
    assert "functional-requirement" in catalog
    # The catalog holds one approved and one draft requirement.
    assert re.search(r"<td>approved</td>\s*<td>1</td>", catalog)
    assert re.search(r"<td>draft</td>\s*<td>1</td>", catalog)

    assert "Findings by severity" in html
    findings = html.split("Findings by severity", 1)[1][:1500]
    for severity in ("error", "warning", "info", "total"):
        assert f"<td>{severity}</td>" in findings


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_named_query_filters_intersect_and_unknown_names_warn(tmp_path: Path):
    html = render_views(tmp_path)

    query_table = html.split('id="query-table"', 1)[1].split("</table>", 1)[0]
    assert "REQ-APPROVED" in query_table
    assert "REQ-DRAFT" not in query_table

    counts = re.findall(r'data-need-count="(\d+)"', html)
    assert "1" in counts  # named query alone
    assert "0" in counts  # named query intersected with status=draft

    assert "Unknown query: nope" in html
    assert 'class="need-view-warning"' in html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_named_query_restricts_matrix_axes(tmp_path: Path):
    """A named query narrows the matrix pool, not just its error checking."""
    html = render_views(tmp_path)

    unfiltered = html.split('id="verification-matrix"', 1)[1].split("</table>", 1)[0]
    assert "REQ-DRAFT" in unfiltered

    restricted = html.split('id="query-matrix"', 1)[1].split("</table>", 1)[0]
    assert "REQ-APPROVED" in restricted
    assert "TC-LOGIN" in restricted
    assert "REQ-DRAFT" not in restricted
    assert "REQ-UNPRIORITIZED" not in restricted


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_dashboard_is_static_content_in_docx(tmp_path: Path):
    document = render_views_to(tmp_path, "docx")
    text = docx_text(document)
    assert "Quality dashboard" in text
    assert "Whole catalog" in text
    assert "Verification successful" in text
    assert "50.0% (1 of 2)" in text
    assert "Needs by type" in text
    assert "Findings by severity" in text


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext is not installed")
def test_dashboard_is_static_content_in_pdf(tmp_path: Path):
    document = render_views_to(tmp_path / "pdf", "pdf")
    text = pdf_text(document)
    assert "Quality dashboard" in text
    assert "Verification successful" in text


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_inspector_renders_a_labelled_static_region(tmp_path: Path):
    """The inspector is a labelled region of ordinary blocks — no JS, no dialog."""
    html = render_views(tmp_path)

    # Quarto may hoist the wrapper into the heading's own <section>, so assert
    # the accessibility contract rather than the element it lands on.
    region = None
    for candidate in re.finditer(r"<(?:div|section)\s([^>]*)>", html):
        classes = re.search(r'class="([^"]*)"', candidate.group(1))
        if classes and "need-inspector" in classes.group(1).split():
            region = candidate.group(1)
            break
    assert region, "the inspector must render as an identified region"
    assert 'role="region"' in region
    labelled = re.search(r'aria-labelledby="([^"]+)"', region)
    assert labelled, "the region must be labelled by its own heading"
    label = re.search(
        rf'id="{re.escape(labelled.group(1))}"[^>]*>(.*?)</span>', html, re.S
    )
    assert label, "the label target must be the heading text"
    assert "Inspector: REQ-APPROVED" in label.group(1)

    assert "Inspector: REQ-APPROVED" in html
    assert "Declared in index.qmd:7" in html
    assert "Attributes" in html
    assert "REQ002" in html
    assert "Requirement has no rationale" in html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_inspector_reports_unknown_ids(tmp_path: Path):
    """An unknown ID warns with the shared message instead of rendering blank."""
    html = render_views(tmp_path)

    assert "Unknown need ID: UNKNOWN-ID" in html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_inspector_is_static_content_in_docx(tmp_path: Path):
    """DOCX readers get the inspector's labels, provenance, and findings."""
    text = docx_text(render_views_to(tmp_path, "docx"))

    assert "Inspector: REQ-APPROVED" in text
    assert "Declared in index.qmd:7" in text
    assert "Attributes" in text
    assert "Requirement has no rationale" in text


@pytest.mark.skipif(
    shutil.which("quarto") is None
    or shutil.which("lualatex") is None
    or shutil.which("pdftotext") is None,
    reason="Quarto, LuaLaTeX, or pdftotext is not installed",
)
def test_inspector_is_static_content_in_pdf(tmp_path: Path):
    """PDF readers get the same inspector content as every other format."""
    text = pdf_text(render_views_to(tmp_path, "pdf"))

    assert "Inspector: REQ-APPROVED" in text
    assert "Requirement has no rationale" in text


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_c4_renders_a_context_diagram(tmp_path: Path):
    """The CLI writes C4 JSON which need-c4 renders as an inline SVG."""
    project = build_c4_fixture_project(tmp_path)
    assert (
        project / ".quarto-needs" / "graphs" / "c4-context-SYS-1.json"
    ).is_file()
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "_site" / "index.html").read_text(encoding="utf-8")

    assert "need-c4-figure" in html
    assert "<svg" in html.lower()
    assert "C4Context" not in html
    assert "Fixture system" in html
    assert "Fixture actor" in html


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_c4_warns_on_an_unknown_root(tmp_path: Path):
    """An unknown root warns loudly instead of failing the whole render."""
    project = build_c4_fixture_project(tmp_path)
    assert (project / ".quarto-needs" / "needs.json").is_file()
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "_site" / "missing.html").read_text(encoding="utf-8")

    assert "C4 view not found" in html
    assert 'class="need-view-warning"' in html


def build_overlays_fixture_project(tmp_path: Path, *, with_baseline: bool = True) -> Path:
    """Copy the overlay fixture, optionally stripping its comparison baseline,
    then run the CLI scan so the build artifacts exist before Quarto renders."""
    project = copy_fixture_project(tmp_path, "overlays")
    if not with_baseline:
        shutil.rmtree(project / "baselines")
        config = project / ".quarto-needs.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                '[graph]\nbaseline = "baselines/quarto-needs.json"\n', ""
            ),
            encoding="utf-8",
        )
    subprocess.run(
        [".venv/bin/quarto-needs", "--root", str(project), "scan"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return project


def test_need_graph_embeds_the_overlay_artifact_when_a_baseline_exists(tmp_path: Path) -> None:
    project = build_overlays_fixture_project(tmp_path)
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "_site" / "index.html").read_text(encoding="utf-8")
    assert "data-need-graph-overlays" in html
    assert "need-graph-overlays-v1" in html
    # Real published annotations from the stale baseline, not an empty shell:
    assert '"REQ-1": "modified"' in html
    assert '"classification": "direct"' in html


def test_need_graph_omits_the_overlay_artifact_without_a_baseline(tmp_path: Path) -> None:
    project = build_overlays_fixture_project(tmp_path, with_baseline=False)
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "_site" / "index.html").read_text(encoding="utf-8")
    assert "data-need-graph-overlays" not in html


def test_need_graph_static_table_lists_node_attributes_not_just_edges(tmp_path: Path) -> None:
    """The static table is the primary operable representation for
    keyboard/screen-reader readers, independent of whether the canvas's own
    JS ever loads. It must show a node's own type/status, not just edges, or
    that audience has no non-visual way to know either at all."""
    project = build_overlays_fixture_project(tmp_path, with_baseline=False)
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "_site" / "index.html").read_text(encoding="utf-8")
    # Quarto's Bootstrap HTML writer appends its own classes after ours
    # (e.g. `class="need-graph-table caption-top table"`), so this checks
    # the class is present, not an exact attribute string.
    assert html.count("need-graph-table") == 2
    assert "functional-requirement" in html
    assert "test-case" in html
    assert "approved" in html
    assert "passed" in html
