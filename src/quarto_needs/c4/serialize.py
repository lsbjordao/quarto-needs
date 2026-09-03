"""The formal, versioned renderer boundary.

`quarto-needs-c4-view-v1` is the contract that separates "Quarto-Needs
understands architecture" from "some library draws architecture". Everything
downstream -- every renderer, every golden test, every parity check -- is
defined against this document and never against an `AnalysisSnapshot`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence

from .model import C4View
from .validation import C4Diagnostic

C4_VIEW_SCHEMA_VERSION = "quarto-needs-c4-view-v1"


def c4_view_fingerprint(view: C4View) -> str:
    """A sha256 over the view's semantic content.

    Diagnostics are excluded: they are derived from the view, so including
    them would let a validation change move an identity that nothing
    semantic touched. Renderer options are excluded by construction -- they
    are not part of a `C4View` at all.
    """
    payload = json.dumps(
        view.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def c4_view_document(
    view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()
) -> dict[str, object]:
    return {
        "schemaVersion": C4_VIEW_SCHEMA_VERSION,
        "fingerprint": c4_view_fingerprint(view),
        "view": {"id": view.id, "level": view.level, "scopeId": view.scope_id},
        "elements": [element.to_dict() for element in view.elements],
        "relationships": [item.to_dict() for item in view.relationships],
        "diagnostics": [item.to_dict() for item in diagnostics],
    }


def render_c4_view(view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()) -> str:
    """The artifact text, matching `graph_projection.render_projection`'s shape."""
    document = c4_view_document(view, diagnostics=diagnostics)
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
