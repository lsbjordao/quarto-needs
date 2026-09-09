"""Render the real case study and capture reproducible README views with Playwright.

Run with a tooling environment containing playwright; Chrome must be installed.
No image is synthesized and no engineering data is modified for the capture.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", default=shutil.which("google-chrome") or shutil.which("chromium"))
    parser.add_argument("--reuse-render", action="store_true", help="Reuse an unchanged, already rendered case study while adjusting captures")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error("Playwright is required. Install it in a separate tooling environment: pip install playwright")
    if not args.browser:
        parser.error("Chrome/Chromium is required; pass its executable with --browser")
    root = Path(__file__).resolve().parents[1]
    project = root / "examples" / "quarto-needs"
    if not args.reuse_render:
        subprocess.run(["quarto", "render", str(project), "--to", "html"], cwd=root, check=True)
    demo = root / "build" / "readme-demo"
    demo.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "_extensions" / "quarto-needs", demo / "_extensions" / "lsbjordao" / "quarto-needs", dirs_exist_ok=True)
    shutil.copyfile(root / "notes" / "examples" / "readme.qmd", demo / "index.qmd")
    (demo / "_quarto.yml").write_text("project:\n  type: default\nfilters:\n  - quarto-needs\n", encoding="utf-8")
    subprocess.run(["quarto", "render", "index.qmd", "--to", "html"], cwd=demo, check=True)
    output = root / "notes" / "assets" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    captures = [
        ("dashboard", "examples/quarto-needs/_book/verification.html", "#verification-dashboard", 370, None),
        ("matrix", "examples/quarto-needs/_book/traceability.html", "#verification-matrix", 400, 900),
        ("card", "examples/quarto-needs/_book/requirements.html", "#FUN-005", None, None),
        ("minimal", "build/readme-demo/index.html", "main", None, None),
    ]
    manifest = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.browser, headless=True)
            page = browser.new_page(viewport={"width": 2400, "height": 1600}, device_scale_factor=1, color_scheme="light")
            for name, document, selector, height, width in captures:
                page.goto(f"http://127.0.0.1:{server.server_port}/{document}", wait_until="domcontentloaded")
                page.evaluate("document.fonts.ready")
                if name == "minimal":
                    assert page.locator(".need-card").count() == 2, "The example did not render its cards"
                    assert page.locator(".need-view-warning").count() == 0, "The example emitted a view warning"
                    assert page.locator(".need-matrix tbody tr").count() == 1, "The example did not render its matrix row"
                toggle = page.locator('.qn-margin-sidebar-toggle[aria-expanded="true"]')
                if toggle.count():
                    toggle.click()
                target = page.locator(selector)
                target.evaluate("element => element.scrollIntoView({block: 'start', inline: 'start'})")
                page.evaluate("window.scrollBy(0, -120)")
                box = target.bounding_box()
                assert box, f"Missing rendered view: {selector}"
                # A bounded, unmodified viewport crop keeps the dense case-study
                # views readable in the README; full views remain linked online.
                if height is None:
                    target.screenshot(path=str(output / f"{name}.png"), animations="disabled")
                else:
                    page.screenshot(path=str(output / f"{name}.png"), animations="disabled", clip={
                        "x": max(0, box["x"]), "y": max(0, box["y"]),
                        "width": min(width or box["width"], box["width"], 2400 - max(0, box["x"])),
                        "height": min(height, box["height"], 1600 - max(0, box["y"])),
                    })
                manifest.append({"image": f"{name}.png", "page": document, "selector": selector, "cropHeight": height, "cropWidth": width})
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    graph = (project / ".quarto-needs" / "needs.json").read_bytes()
    provenance = {"schemaVersion": "1", "sourceGraphSha256": hashlib.sha256(graph).hexdigest(), "captures": manifest}
    (output / "captures.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
