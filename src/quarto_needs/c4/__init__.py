"""The C4 architecture projection: semantics, validation, and renderer adapters.

This package is the single home of C4 meaning in Quarto-Needs. Renderers live
under `c4.renderers` and consume only the IR defined in `c4.model` -- they
never see an `AnalysisSnapshot` and never re-derive architecture semantics
of their own (Spec 1, 9).
"""
from __future__ import annotations
