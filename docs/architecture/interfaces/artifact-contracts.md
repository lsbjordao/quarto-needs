# Interface: artifact contracts

Stable, versioned, machine-readable contracts other tools depend on. Each is a JSON Schema under `schemas/`.

| Schema | Contract |
|---|---|
| `needs.schema.json` | The canonical engineering snapshot representation (`needs.json`) |
| `graph-public-v1.schema.json` | The bounded public graph projection consumed by static/interactive graph renderers |
| `baseline-v1.schema.json` | A captured, reproducible engineering state |
| `diff-v1.schema.json` | Structured field/relation/relocation/addition/removal changes between two states |
| `impact-v1.schema.json` | Explicit, auditable impact-traversal paths between two states |
| `evidence-envelope-v1.schema.json` | Provenance-bearing attestations wrapping check/test results |
| `evidence-checks-v1.schema.json` / `evidence-pytest-v1.schema.json` | Provider-neutral and pytest-specific check-result shapes |

## Rules for this interface

- A schema version bump is required for any breaking change; consumers pin to a schema version, not to "whatever the tool currently emits."
- The public graph projection (`graph-public-v1`) is deliberately narrower than the internal snapshot — see `RISK-002` and `graph_projection.py`'s allowlisted `PublicNode` fields. Internal-only fields (absolute paths, arbitrary attributes) never reach this schema.
- `vendor/` schemas are third-party (ReqIF, etc.) and are not owned by this project; they are used for validation of exported/imported interchange formats, not extended.
