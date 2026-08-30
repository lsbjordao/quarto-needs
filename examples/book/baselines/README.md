# Aegis baselines

The live Aegis showcase uses domain-local identifiers such as `STK-*`, `SYS-*`, `FUN-*`, `NFR-*`, `ADR-*`, `COMP-*`, `IF-*`, `TC-*`, `EVD-*`, and `RISK-*`.

`quarto-needs.json` is intentionally a **historical baseline** captured before that namespace simplification, when every identifier redundantly carried the `IAM-*` prefix. It is retained only as a change-intelligence fixture so `diff` and `impact` can demonstrate a real namespace migration.

The historical baseline is not the identifier convention recommended by the current example and must not be used as a template for new authored objects. Prefixes remain configurable per project through `.quarto-needs.toml`.
