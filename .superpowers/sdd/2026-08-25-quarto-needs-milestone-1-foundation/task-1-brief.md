### Task 1: Freeze the schema-v1 compatibility contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Create: `schemas/needs-envelope-v1.schema.json`
- Create: `tests/fixtures/v1/aegis-needs-v1.json`
- Create: `tests/test_v1_contract.py`

**Interfaces:**
- Consumes: the currently generated `examples/book/.quarto-needs/needs.json` before any production refactor.
- Produces: a frozen representative v1 payload, a Draft 2020-12 envelope schema, and `legacy_projection(payload)` for semantic compatibility comparisons.

- [ ] **Step 1: Capture the current Aegis payload before changing production code**

Run:

```bash
mkdir -p tests/fixtures/v1
cp examples/book/.quarto-needs/needs.json tests/fixtures/v1/aegis-needs-v1.json
```

Expected: the fixture contains the current Aegis objects, nested relations, top-level relations, coverage, validation, backlinks, and schema version. This is a mechanical byte-for-byte fixture capture; do not regenerate it after the refactor.

- [ ] **Step 2: Declare test dependencies once and use the extra everywhere**

Add this exact group to `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
  "pytest>=8",
  "jsonschema>=4.23",
]
```

Change setup/install commands to `python -m pip install -e ".[test]"` in `Makefile` and `.github/workflows/ci.yml`. Do not add either package to `[project.dependencies]`.

- [ ] **Step 3: Add the complete v1 envelope schema**

Create `schemas/needs-envelope-v1.schema.json` with these required top-level fields and definitions:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/needs-envelope-v1.schema.json",
  "title": "Quarto-Needs Graph Envelope v1",
  "type": "object",
  "required": ["schemaVersion", "objects", "relations", "coverage", "validation", "backlinks"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "objects": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "needs.schema.json"},
          {"required": ["id", "type", "title", "status", "body", "rationale", "attributes", "relations", "source", "href"]}
        ]
      }
    },
    "relations": {"type": "array", "items": {"$ref": "#/$defs/relation"}},
    "coverage": {"$ref": "#/$defs/coverage"},
    "validation": {"type": "array", "items": {"$ref": "#/$defs/finding"}},
    "backlinks": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"$ref": "#/$defs/backlink"}
      }
    },
    "extensions": {"type": "object"}
  },
  "additionalProperties": false,
  "$defs": {
    "relation": {
      "type": "object",
      "required": ["type", "source", "target", "attributes"],
      "properties": {
        "type": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "attributes": {"type": "object"}
      },
      "additionalProperties": false
    },
    "coverage": {
      "type": "object",
      "required": ["requirements", "approved", "implemented", "verified", "implementation_coverage", "verification_coverage"],
      "properties": {
        "requirements": {"type": "integer", "minimum": 0},
        "approved": {"type": "integer", "minimum": 0},
        "implemented": {"type": "integer", "minimum": 0},
        "verified": {"type": "integer", "minimum": 0},
        "implementation_coverage": {"type": "number", "minimum": 0, "maximum": 100},
        "verification_coverage": {"type": "number", "minimum": 0, "maximum": 100}
      },
      "additionalProperties": false
    },
    "finding": {
      "type": "object",
      "required": ["code", "severity", "message", "object_id"],
      "properties": {
        "code": {"type": "string"},
        "severity": {"enum": ["error", "warning", "info"]},
        "message": {"type": "string"},
        "object_id": {"type": ["string", "null"]}
      },
      "additionalProperties": true
    },
    "backlink": {
      "type": "object",
      "required": ["source", "type"],
      "properties": {
        "source": {"type": "string"},
        "type": {"type": "string"}
      },
      "additionalProperties": false
    }
  }
}
```

Also extend `schemas/needs.schema.json` so its existing `properties` map contains these exact additions while keeping the current `$id` and object-level purpose:

```json
"source": {
  "type": ["object", "null"],
  "required": ["file", "line", "anchor"],
  "properties": {
    "file": {"type": "string"},
    "line": {"type": "integer", "minimum": 1},
    "anchor": {"type": ["string", "null"]}
  },
  "additionalProperties": false
},
"href": {"type": "string", "minLength": 1}
```

Require `attributes` on relation items because the actual v1 writer always emits it, and set `additionalProperties: false` on relation items. Leave object-level additional properties allowed so older/newer tolerant object consumers are not accidentally narrowed by the object-only schema.

- [ ] **Step 4: Write contract tests against the frozen fixture**

Add these test helpers and assertions to `tests/test_v1_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_projection(payload: dict[str, object]) -> dict[str, object]:
    projected = {key: value for key, value in payload.items() if key != "extensions"}
    projected["objects"] = sorted(projected["objects"], key=lambda item: (item["id"].casefold(), item["id"]))
    projected["relations"] = sorted(
        projected["relations"],
        key=lambda item: (
            item["source"].casefold(), item["source"], item["type"],
            item["target"].casefold(), item["target"],
            json.dumps(item.get("attributes", {}), ensure_ascii=False, sort_keys=True),
        ),
    )
    projected["validation"] = sorted(
        projected["validation"],
        key=lambda item: (item["severity"], item["code"], item.get("object_id") or "", item["message"]),
    )
    projected["backlinks"] = {
        key: sorted(value, key=lambda item: (item["source"].casefold(), item["type"]))
        for key, value in sorted(projected["backlinks"].items())
    }
    for item in projected["objects"]:
        item["relations"] = sorted(
            item.get("relations", []),
            key=lambda relation: (
                relation["type"], relation["target"].casefold(), relation["target"],
                json.dumps(relation.get("attributes", {}), ensure_ascii=False, sort_keys=True),
            ),
        )
    return projected


def test_frozen_aegis_payload_validates_against_v1_envelope() -> None:
    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    resolver = RefResolver((SCHEMAS / "needs-envelope-v1.schema.json").as_uri(), schema)
    Draft202012Validator(schema, resolver=resolver).validate(load_json(GOLDEN))


def test_frozen_payload_has_nested_and_top_level_relation_equivalence() -> None:
    payload = load_json(GOLDEN)
    nested = [relation for item in payload["objects"] for relation in item.get("relations", [])]
    key = lambda relation: json.dumps(relation, ensure_ascii=False, sort_keys=True)
    assert sorted(nested, key=key) == sorted(payload["relations"], key=key)
```

If the installed jsonschema version warns that `RefResolver` is deprecated, keep the test behavior for this milestone and record migration to the referencing registry as test-infrastructure cleanup; do not weaken validation.

- [ ] **Step 5: Run the contract tests before refactoring**

Run:

```bash
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest tests/test_v1_contract.py -q
```

Expected: PASS against the current payload. If the frozen file lacks a field required by the proposed schema, correct the schema to describe the actual v1 payload; do not edit the frozen payload to make the test pass.

- [ ] **Step 6: Record the compatibility checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add pyproject.toml Makefile .github/workflows/ci.yml schemas/needs.schema.json schemas/needs-envelope-v1.schema.json tests/fixtures/v1/aegis-needs-v1.json tests/test_v1_contract.py
  git commit -m "test: freeze schema v1 compatibility contract"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```

Expected: a commit is created only inside an existing Git worktree; otherwise the verified changes remain in place.

---

