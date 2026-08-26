# Task 1 review package (no Git metadata)

## Changed-file inventory
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/.github/workflows/ci.yml and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/.github/workflows/ci.yml differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/Makefile and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/Makefile differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/pyproject.toml and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/pyproject.toml differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas: needs-envelope-v1.schema.json
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/schemas/needs.schema.json and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas/needs.schema.json differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after: tests

## Full diff
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/.github/workflows/ci.yml .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/.github/workflows/ci.yml
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/.github/workflows/ci.yml	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/.github/workflows/ci.yml	2026-08-25 09:13:06.774378133 -0300
@@ -12,7 +12,7 @@
       - uses: actions/setup-python@v5
         with:
           python-version: "3.12"
-      - run: python -m pip install -e . pytest
+      - run: python -m pip install -e ".[test]"
       - run: pytest -q
       - run: quarto-needs scan
       - run: quarto-needs check
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/Makefile .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/Makefile
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/Makefile	2026-08-25 00:42:03.377633610 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/Makefile	2026-08-25 09:13:06.774378133 -0300
@@ -7,7 +7,7 @@
 	python3 -m venv .venv
 
 setup: .venv/bin/python
-	$(VENV_PYTHON) -m pip install -e . pytest
+	$(VENV_PYTHON) -m pip install -e ".[test]"
 
 test:
 	$(VENV_PYTHON) -m pytest -q
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/pyproject.toml .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/pyproject.toml
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/pyproject.toml	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/pyproject.toml	2026-08-25 09:13:06.774378133 -0300
@@ -20,6 +20,12 @@
 [project.scripts]
 quarto-needs = "quarto_needs.cli:main"
 
+[project.optional-dependencies]
+test = [
+  "pytest>=8",
+  "jsonschema>=4.23",
+]
+
 [tool.setuptools.packages.find]
 where = ["src"]
 
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/schemas/needs-envelope-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas/needs-envelope-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/schemas/needs-envelope-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas/needs-envelope-v1.schema.json	2026-08-25 09:16:13.681748831 -0300
@@ -0,0 +1,77 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/needs-envelope-v1.schema.json",
+  "title": "Quarto-Needs Graph Envelope v1",
+  "type": "object",
+  "required": ["schemaVersion", "objects", "relations", "coverage", "validation", "backlinks"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "relations": {"type": "array", "items": {"$ref": "#/$defs/relation"}},
+    "coverage": {"$ref": "#/$defs/coverage"},
+    "validation": {"type": "array", "items": {"$ref": "#/$defs/finding"}},
+    "backlinks": {
+      "type": "object",
+      "additionalProperties": {
+        "type": "array",
+        "items": {"$ref": "#/$defs/backlink"}
+      }
+    },
+    "extensions": {"type": "object"},
+    "objects": {
+      "type": "array",
+      "items": {
+        "allOf": [
+          {"$ref": "needs.schema.json"},
+          {"required": ["id", "type", "title", "status", "body", "rationale", "attributes", "relations", "source", "href"]}
+        ]
+      }
+    }
+  },
+  "additionalProperties": false,
+  "$defs": {
+    "relation": {
+      "type": "object",
+      "required": ["type", "source", "target", "attributes"],
+      "properties": {
+        "type": {"type": "string", "minLength": 1},
+        "source": {"type": "string", "minLength": 1},
+        "target": {"type": "string", "minLength": 1},
+        "attributes": {"type": "object"}
+      },
+      "additionalProperties": false
+    },
+    "coverage": {
+      "type": "object",
+      "required": ["requirements", "approved", "implemented", "verified", "implementation_coverage", "verification_coverage"],
+      "properties": {
+        "requirements": {"type": "integer", "minimum": 0},
+        "approved": {"type": "integer", "minimum": 0},
+        "implemented": {"type": "integer", "minimum": 0},
+        "verified": {"type": "integer", "minimum": 0},
+        "implementation_coverage": {"type": "number", "minimum": 0, "maximum": 100},
+        "verification_coverage": {"type": "number", "minimum": 0, "maximum": 100}
+      },
+      "additionalProperties": false
+    },
+    "finding": {
+      "type": "object",
+      "required": ["code", "severity", "message", "object_id"],
+      "properties": {
+        "code": {"type": "string"},
+        "severity": {"enum": ["error", "warning", "info"]},
+        "message": {"type": "string"},
+        "object_id": {"type": ["string", "null"]}
+      },
+      "additionalProperties": true
+    },
+    "backlink": {
+      "type": "object",
+      "required": ["source", "type"],
+      "properties": {
+        "source": {"type": "string"},
+        "type": {"type": "string"}
+      },
+      "additionalProperties": false
+    }
+  }
+}
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/schemas/needs.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas/needs.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/schemas/needs.schema.json	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/schemas/needs.schema.json	2026-08-25 09:14:13.918171206 -0300
@@ -16,14 +16,26 @@
       "type": "array",
       "items": {
         "type": "object",
-        "required": ["type", "source", "target"],
+        "required": ["type", "source", "target", "attributes"],
         "properties": {
           "type": {"type": "string"},
           "source": {"type": "string"},
           "target": {"type": "string"},
           "attributes": {"type": "object"}
-        }
+        },
+        "additionalProperties": false
       }
-    }
+    },
+    "source": {
+      "type": ["object", "null"],
+      "required": ["file", "line", "anchor"],
+      "properties": {
+        "file": {"type": "string"},
+        "line": {"type": "integer", "minimum": 1},
+        "anchor": {"type": ["string", "null"]}
+      },
+      "additionalProperties": false
+    },
+    "href": {"type": "string", "minLength": 1}
   }
 }
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/tests/fixtures/v1/aegis-needs-v1.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/tests/fixtures/v1/aegis-needs-v1.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/tests/fixtures/v1/aegis-needs-v1.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/tests/fixtures/v1/aegis-needs-v1.json	2026-08-25 09:12:59.954401093 -0300
@@ -0,0 +1,3520 @@
+{
+  "schemaVersion": "1",
+  "objects": [
+    {
+      "id": "IAM-SYS-001",
+      "type": "system-requirement",
+      "title": "Autenticar identidades antes de emitir sessão",
+      "status": "approved",
+      "body": "O Aegis IAM deve autenticar a identidade antes de emitir uma sessão utilizável.\n\n### Rationale\n\nEvita que recursos protegidos sejam expostos a solicitantes anônimos.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-001",
+          "target": "IAM-STK-001",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-001",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-001",
+          "target": "IAM-TC-001",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 5,
+        "anchor": "IAM-SYS-001"
+      },
+      "href": "requirements/system.html#IAM-SYS-001"
+    },
+    {
+      "id": "IAM-SYS-002",
+      "type": "system-requirement",
+      "title": "Decidir acesso por política central",
+      "status": "approved",
+      "body": "O sistema deve decidir acesso por políticas centralizadas e atributos confiáveis.\n\n### Rationale\n\nCentralizar a decisão reduz divergências entre aplicações consumidoras.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-002",
+          "target": "IAM-STK-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-002",
+          "target": "IAM-COMP-002",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-002",
+          "target": "IAM-TC-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 15,
+        "anchor": "IAM-SYS-002"
+      },
+      "href": "requirements/system.html#IAM-SYS-002"
+    },
+    {
+      "id": "IAM-SYS-003",
+      "type": "system-requirement",
+      "title": "Gerir o ciclo de vida de contas",
+      "status": "approved",
+      "body": "O sistema deve provisionar, alterar, suspender e encerrar contas de forma auditável.\n\n### Rationale\n\nContas órfãs e privilégios persistentes são riscos operacionais relevantes.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-003",
+          "target": "IAM-STK-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-003",
+          "target": "IAM-COMP-003",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-003",
+          "target": "IAM-TC-007",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 25,
+        "anchor": "IAM-SYS-003"
+      },
+      "href": "requirements/system.html#IAM-SYS-003"
+    },
+    {
+      "id": "IAM-SYS-004",
+      "type": "system-requirement",
+      "title": "Registrar eventos de identidade imutáveis",
+      "status": "approved",
+      "body": "O sistema deve registrar eventos de autenticação, autorização e administração.\n\n### Rationale\n\nRegistros íntegros sustentam investigação, conformidade e responsabilização.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;compliance"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-004",
+          "target": "IAM-STK-005",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-004",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-004",
+          "target": "IAM-TC-010",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 35,
+        "anchor": "IAM-SYS-004"
+      },
+      "href": "requirements/system.html#IAM-SYS-004"
+    },
+    {
+      "id": "IAM-SYS-005",
+      "type": "system-requirement",
+      "title": "Recuperar acesso com prova de identidade",
+      "status": "approved",
+      "body": "O sistema deve recuperar acesso somente após validação de identidade proporcional ao risco.\n\n### Rationale\n\nO processo de recuperação não pode se tornar uma via de tomada de conta.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-005",
+          "target": "IAM-STK-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-005",
+          "target": "IAM-COMP-005",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-005",
+          "target": "IAM-TC-012",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 45,
+        "anchor": "IAM-SYS-005"
+      },
+      "href": "requirements/system.html#IAM-SYS-005"
+    },
+    {
+      "id": "IAM-SYS-006",
+      "type": "system-requirement",
+      "title": "Expor integração de identidade padronizada",
+      "status": "approved",
+      "body": "O sistema deve oferecer protocolos abertos de federação e provisão.\n\n### Rationale\n\nProtocolos padronizados diminuem o custo e o risco das integrações.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;standards"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-006",
+          "target": "IAM-STK-004",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-SYS-006",
+          "target": "IAM-IF-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-SYS-006",
+          "target": "IAM-TC-017",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 55,
+        "anchor": "IAM-SYS-006"
+      },
+      "href": "requirements/system.html#IAM-SYS-006"
+    },
+    {
+      "id": "IAM-SYS-007",
+      "type": "system-requirement",
+      "title": "Detectar anomalias de privilégio",
+      "status": "in-review",
+      "body": "O sistema deve priorizar para revisão acessos com padrão anômalo.\n\n### Rationale\n\nA análise de anomalias pode antecipar abuso de privilégios.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "analytics;governance"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-007",
+          "target": "IAM-STK-005",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 65,
+        "anchor": "IAM-SYS-007"
+      },
+      "href": "requirements/system.html#IAM-SYS-007"
+    },
+    {
+      "id": "IAM-SYS-008",
+      "type": "system-requirement",
+      "title": "Oferecer credencial móvel corporativa",
+      "status": "draft",
+      "body": "O sistema poderá oferecer uma credencial móvel para acesso presencial.\n\n### Rationale\n\nA necessidade depende de avaliação conjunta de segurança física e privacidade.",
+      "rationale": "",
+      "attributes": {
+        "priority": "low",
+        "tags": "experience;mobile"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-SYS-008",
+          "target": "IAM-STK-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/system.qmd",
+        "line": 75,
+        "anchor": "IAM-SYS-008"
+      },
+      "href": "requirements/system.html#IAM-SYS-008"
+    },
+    {
+      "id": "IAM-FUN-001",
+      "type": "functional-requirement",
+      "title": "Validar credenciais corporativas",
+      "status": "approved",
+      "body": "O serviço deve validar credenciais contra o diretório corporativo antes de criar sessão.\n\n### Rationale\n\nGarante que a sessão represente uma identidade corporativa conhecida.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-001",
+          "target": "IAM-SYS-001",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-001",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-001",
+          "target": "IAM-TC-001",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 6,
+        "anchor": "IAM-FUN-001"
+      },
+      "href": "requirements/functional.html#IAM-FUN-001"
+    },
+    {
+      "id": "IAM-FUN-002",
+      "type": "functional-requirement",
+      "title": "Exigir MFA para acesso privilegiado",
+      "status": "approved",
+      "body": "O serviço deve exigir um segundo fator para papéis privilegiados.\n\n### Rationale\n\nReduz a eficácia de credenciais capturadas por phishing.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;mfa;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-002",
+          "target": "IAM-SYS-001",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-002",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-002",
+          "target": "IAM-TC-002",
+          "attributes": {}
+        },
+        {
+          "type": "mitigates",
+          "source": "IAM-FUN-002",
+          "target": "IAM-RISK-001",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 16,
+        "anchor": "IAM-FUN-002"
+      },
+      "href": "requirements/functional.html#IAM-FUN-002"
+    },
+    {
+      "id": "IAM-FUN-003",
+      "type": "functional-requirement",
+      "title": "Revogar sessões após mudança de risco",
+      "status": "approved",
+      "body": "O serviço deve revogar sessões quando a conta for suspensa ou o risco subir.\n\n### Rationale\n\nLimita a janela de abuso após um evento de risco.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;session"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-003",
+          "target": "IAM-SYS-001",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-003",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-003",
+          "target": "IAM-TC-003",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 26,
+        "anchor": "IAM-FUN-003"
+      },
+      "href": "requirements/functional.html#IAM-FUN-003"
+    },
+    {
+      "id": "IAM-FUN-004",
+      "type": "functional-requirement",
+      "title": "Avaliar políticas por atributo",
+      "status": "approved",
+      "body": "O motor deve avaliar sujeito, recurso, ação e contexto na decisão de acesso.\n\n### Rationale\n\nPermite aplicar políticas consistentes independentemente da aplicação consumidora.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-004",
+          "target": "IAM-SYS-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-004",
+          "target": "IAM-COMP-002",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-004",
+          "target": "IAM-TC-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 36,
+        "anchor": "IAM-FUN-004"
+      },
+      "href": "requirements/functional.html#IAM-FUN-004"
+    },
+    {
+      "id": "IAM-FUN-005",
+      "type": "functional-requirement",
+      "title": "Aplicar menor privilégio por padrão",
+      "status": "approved",
+      "body": "O motor deve negar solicitações que não correspondam a uma regra permissiva.\n\n### Rationale\n\nEvita escalada de privilégio causada por política ausente ou excessivamente ampla.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-005",
+          "target": "IAM-SYS-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-005",
+          "target": "IAM-COMP-002",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-005",
+          "target": "IAM-TC-005",
+          "attributes": {}
+        },
+        {
+          "type": "mitigates",
+          "source": "IAM-FUN-005",
+          "target": "IAM-RISK-002",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 46,
+        "anchor": "IAM-FUN-005"
+      },
+      "href": "requirements/functional.html#IAM-FUN-005"
+    },
+    {
+      "id": "IAM-FUN-006",
+      "type": "functional-requirement",
+      "title": "Registrar delegação temporária",
+      "status": "approved",
+      "body": "O sistema deve limitar e registrar delegações de acesso com data de expiração.\n\n### Rationale\n\nMantém delegações excepcionais temporárias e responsabilizáveis.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "authorization;delegation"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-006",
+          "target": "IAM-SYS-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-006",
+          "target": "IAM-COMP-002",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-006",
+          "target": "IAM-TC-006",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 56,
+        "anchor": "IAM-FUN-006"
+      },
+      "href": "requirements/functional.html#IAM-FUN-006"
+    },
+    {
+      "id": "IAM-FUN-007",
+      "type": "functional-requirement",
+      "title": "Provisionar conta por evento de admissão",
+      "status": "approved",
+      "body": "O orquestrador deve criar conta após receber evento válido de admissão.\n\n### Rationale\n\nReduz trabalho manual e garante que o acesso comece com dados de origem confiável.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-007",
+          "target": "IAM-SYS-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-007",
+          "target": "IAM-COMP-003",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-007",
+          "target": "IAM-TC-007",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 66,
+        "anchor": "IAM-FUN-007"
+      },
+      "href": "requirements/functional.html#IAM-FUN-007"
+    },
+    {
+      "id": "IAM-FUN-008",
+      "type": "functional-requirement",
+      "title": "Suspender conta no desligamento",
+      "status": "approved",
+      "body": "O orquestrador deve suspender a conta e remover sessões após evento de desligamento.\n\n### Rationale\n\nEvita que identidades desligadas mantenham acesso operacional.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-008",
+          "target": "IAM-SYS-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-008",
+          "target": "IAM-COMP-003",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-008",
+          "target": "IAM-TC-008",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 76,
+        "anchor": "IAM-FUN-008"
+      },
+      "href": "requirements/functional.html#IAM-FUN-008"
+    },
+    {
+      "id": "IAM-FUN-009",
+      "type": "functional-requirement",
+      "title": "Solicitar revisão periódica de acesso",
+      "status": "approved",
+      "body": "O sistema deve abrir campanhas de revisão para responsáveis por recursos.\n\n### Rationale\n\nRevisões periódicas removem privilégios que deixaram de ser necessários.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-009",
+          "target": "IAM-SYS-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-009",
+          "target": "IAM-COMP-003",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-009",
+          "target": "IAM-TC-009",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 86,
+        "anchor": "IAM-FUN-009"
+      },
+      "href": "requirements/functional.html#IAM-FUN-009"
+    },
+    {
+      "id": "IAM-FUN-010",
+      "type": "functional-requirement",
+      "title": "Registrar decisão de autorização",
+      "status": "approved",
+      "body": "O sistema deve registrar política aplicada, sujeito, recurso, resultado e correlação.\n\n### Rationale\n\nPermite explicar e investigar decisões de autorização.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-010",
+          "target": "IAM-SYS-004",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-010",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-010",
+          "target": "IAM-TC-010",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 96,
+        "anchor": "IAM-FUN-010"
+      },
+      "href": "requirements/functional.html#IAM-FUN-010"
+    },
+    {
+      "id": "IAM-FUN-011",
+      "type": "functional-requirement",
+      "title": "Consultar trilha de auditoria por conta",
+      "status": "approved",
+      "body": "Auditores devem consultar eventos de uma conta em ordem temporal e com filtros.\n\n### Rationale\n\nReduz o tempo necessário para investigar uma identidade específica.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-011",
+          "target": "IAM-SYS-004",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-011",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-011",
+          "target": "IAM-TC-011",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 106,
+        "anchor": "IAM-FUN-011"
+      },
+      "href": "requirements/functional.html#IAM-FUN-011"
+    },
+    {
+      "id": "IAM-FUN-012",
+      "type": "functional-requirement",
+      "title": "Recuperar conta com verificação reforçada",
+      "status": "approved",
+      "body": "O fluxo deve exigir prova de posse e validação adicional para uma conta de alto risco.\n\n### Rationale\n\nEvita que a recuperação de conta seja explorada como tomada de acesso.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-012",
+          "target": "IAM-SYS-005",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-FUN-012",
+          "target": "IAM-COMP-005",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-FUN-012",
+          "target": "IAM-TC-012",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 116,
+        "anchor": "IAM-FUN-012"
+      },
+      "href": "requirements/functional.html#IAM-FUN-012"
+    },
+    {
+      "id": "IAM-FUN-013",
+      "type": "functional-requirement",
+      "title": "Delegar recuperação ao suporte supervisionado",
+      "status": "in-review",
+      "body": "O produto deve permitir recuperação assistida com aprovação de segundo operador.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "recovery;support"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-013",
+          "target": "IAM-SYS-005",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 126,
+        "anchor": "IAM-FUN-013"
+      },
+      "href": "requirements/functional.html#IAM-FUN-013"
+    },
+    {
+      "id": "IAM-FUN-014",
+      "type": "functional-requirement",
+      "title": "Provisionar grupos via SCIM",
+      "status": "draft",
+      "body": "O produto poderá sincronizar grupos autorizados a partir de provedor externo.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;scim"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-FUN-014",
+          "target": "IAM-SYS-006",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 132,
+        "anchor": "IAM-FUN-014"
+      },
+      "href": "requirements/functional.html#IAM-FUN-014"
+    },
+    {
+      "id": "IAM-FUN-015",
+      "type": "functional-requirement",
+      "title": "Permitir senha compartilhada por equipe",
+      "status": "disapproved",
+      "body": "A proposta permitiria uma senha comum para equipes temporárias; foi reprovada por\neliminar responsabilização individual.",
+      "rationale": "",
+      "attributes": {
+        "priority": "low",
+        "tags": "authentication;password"
+      },
+      "relations": [
+        {
+          "type": "conflicts-with",
+          "source": "IAM-FUN-015",
+          "target": "IAM-SYS-001",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/functional.qmd",
+        "line": 138,
+        "anchor": "IAM-FUN-015"
+      },
+      "href": "requirements/functional.html#IAM-FUN-015"
+    },
+    {
+      "id": "IAM-NFR-001",
+      "type": "non-functional-requirement",
+      "title": "Proteger credenciais em trânsito e repouso",
+      "status": "approved",
+      "body": "Credenciais e segredos devem usar criptografia aprovada durante transporte e armazenamento.\n\n### Rationale\n\nProtege segredos contra interceptação e exposição em armazenamento persistente.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-001",
+          "target": "IAM-STK-001",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-001",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-001",
+          "target": "IAM-TC-016",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 6,
+        "anchor": "IAM-NFR-001"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-001"
+    },
+    {
+      "id": "IAM-NFR-002",
+      "type": "non-functional-requirement",
+      "title": "Manter autenticação disponível",
+      "status": "approved",
+      "body": "O serviço de autenticação deve atingir disponibilidade mensal de 99,95%.\n\n### Rationale\n\nIdentidade indisponível bloqueia o trabalho de todos os sistemas consumidores.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;availability"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-002",
+          "target": "IAM-STK-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-002",
+          "target": "IAM-COMP-001",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-002",
+          "target": "IAM-TC-014",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 16,
+        "anchor": "IAM-NFR-002"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-002"
+    },
+    {
+      "id": "IAM-NFR-003",
+      "type": "non-functional-requirement",
+      "title": "Minimizar dados pessoais em eventos",
+      "status": "approved",
+      "body": "Eventos de auditoria devem conter somente dados pessoais necessários à finalidade.\n\n### Rationale\n\nMinimiza o impacto de um acesso indevido ou vazamento do repositório de logs.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-003",
+          "target": "IAM-STK-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-003",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-003",
+          "target": "IAM-TC-015",
+          "attributes": {}
+        },
+        {
+          "type": "mitigates",
+          "source": "IAM-NFR-003",
+          "target": "IAM-RISK-003",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 26,
+        "anchor": "IAM-NFR-003"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-003"
+    },
+    {
+      "id": "IAM-NFR-004",
+      "type": "non-functional-requirement",
+      "title": "Responder decisão de acesso em até 200 ms",
+      "status": "approved",
+      "body": "O percentil 95 das decisões de autorização deve ser inferior a 200 ms sob carga nominal.\n\n### Rationale\n\nDecisões lentas degradam a experiência e estimulam contornos inseguros.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "performance;authorization"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-004",
+          "target": "IAM-STK-004",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-004",
+          "target": "IAM-COMP-002",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-004",
+          "target": "IAM-TC-006",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 36,
+        "anchor": "IAM-NFR-004"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-004"
+    },
+    {
+      "id": "IAM-NFR-005",
+      "type": "non-functional-requirement",
+      "title": "Preservar integridade de auditoria",
+      "status": "approved",
+      "body": "O armazenamento de auditoria deve detectar alteração ou remoção de eventos.\n\n### Rationale\n\nUma trilha adulterável não sustenta investigação nem comprovação de conformidade.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;logging"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-005",
+          "target": "IAM-STK-005",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-005",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-005",
+          "target": "IAM-TC-010",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 46,
+        "anchor": "IAM-NFR-005"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-005"
+    },
+    {
+      "id": "IAM-NFR-006",
+      "type": "non-functional-requirement",
+      "title": "Oferecer autenticação acessível",
+      "status": "approved",
+      "body": "As telas de autenticação devem atender critérios de acessibilidade de nível AA.\n\n### Rationale\n\nTodos os usuários precisam concluir autenticação sem depender de um único modo de interação.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "usability;accessibility"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-006",
+          "target": "IAM-STK-004",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-006",
+          "target": "IAM-COMP-006",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-006",
+          "target": "IAM-TC-013",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 56,
+        "anchor": "IAM-NFR-006"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-006"
+    },
+    {
+      "id": "IAM-NFR-007",
+      "type": "non-functional-requirement",
+      "title": "Reter evidências pelo prazo regulatório",
+      "status": "approved",
+      "body": "Evidências de acesso devem permanecer disponíveis durante o prazo de retenção definido.\n\n### Rationale\n\nAtende obrigações de auditoria e permite investigar fatos ocorridos no passado.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "compliance;retention"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-007",
+          "target": "IAM-STK-002",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-007",
+          "target": "IAM-COMP-004",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-007",
+          "target": "IAM-TC-011",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 66,
+        "anchor": "IAM-NFR-007"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-007"
+    },
+    {
+      "id": "IAM-NFR-008",
+      "type": "non-functional-requirement",
+      "title": "Restaurar fluxo de recuperação em até quatro horas",
+      "status": "approved",
+      "body": "O serviço deve restaurar a recuperação de conta dentro do objetivo de quatro horas.\n\n### Rationale\n\nLimita o período em que usuários legítimos ficam sem um caminho seguro de retorno.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "resilience;recovery"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-008",
+          "target": "IAM-STK-003",
+          "attributes": {}
+        },
+        {
+          "type": "implemented-by",
+          "source": "IAM-NFR-008",
+          "target": "IAM-COMP-005",
+          "attributes": {}
+        },
+        {
+          "type": "verified-by",
+          "source": "IAM-NFR-008",
+          "target": "IAM-TC-012",
+          "attributes": {}
+        },
+        {
+          "type": "mitigates",
+          "source": "IAM-NFR-008",
+          "target": "IAM-RISK-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 76,
+        "anchor": "IAM-NFR-008"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-008"
+    },
+    {
+      "id": "IAM-NFR-009",
+      "type": "non-functional-requirement",
+      "title": "Expor métricas operacionais de identidade",
+      "status": "in-review",
+      "body": "O produto deve publicar métricas de latência, erros e bloqueios para operações.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "observability;operations"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-009",
+          "target": "IAM-STK-003",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 86,
+        "anchor": "IAM-NFR-009"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-009"
+    },
+    {
+      "id": "IAM-NFR-010",
+      "type": "non-functional-requirement",
+      "title": "Medir consumo energético por autenticação",
+      "status": "draft",
+      "body": "O produto poderá medir consumo energético por transação de autenticação.",
+      "rationale": "",
+      "attributes": {
+        "priority": "low",
+        "tags": "sustainability;operations"
+      },
+      "relations": [
+        {
+          "type": "derives-from",
+          "source": "IAM-NFR-010",
+          "target": "IAM-STK-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "requirements/non-functional.qmd",
+        "line": 92,
+        "anchor": "IAM-NFR-010"
+      },
+      "href": "requirements/non-functional.html#IAM-NFR-010"
+    },
+    {
+      "id": "IAM-STK-001",
+      "type": "stakeholder-need",
+      "title": "Diretora de segurança precisa reduzir invasões de conta",
+      "status": "approved",
+      "body": "A CISO precisa de autenticação resistente a phishing para contas privilegiadas.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;authentication"
+      },
+      "relations": [],
+      "source": {
+        "file": "context/stakeholders.qmd",
+        "line": 5,
+        "anchor": "IAM-STK-001"
+      },
+      "href": "context/stakeholders.html#IAM-STK-001"
+    },
+    {
+      "id": "IAM-STK-002",
+      "type": "stakeholder-need",
+      "title": "Encarregado de dados precisa controlar exposição de dados pessoais",
+      "status": "approved",
+      "body": "O DPO precisa de evidências de consentimento, retenção e acesso mínimo.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "relations": [],
+      "source": {
+        "file": "context/stakeholders.qmd",
+        "line": 11,
+        "anchor": "IAM-STK-002"
+      },
+      "href": "context/stakeholders.html#IAM-STK-002"
+    },
+    {
+      "id": "IAM-STK-003",
+      "type": "stakeholder-need",
+      "title": "Operações precisam recuperar acesso com segurança",
+      "status": "approved",
+      "body": "A central de suporte precisa restaurar contas sem criar um atalho para fraude.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "operations;availability"
+      },
+      "relations": [],
+      "source": {
+        "file": "context/stakeholders.qmd",
+        "line": 17,
+        "anchor": "IAM-STK-003"
+      },
+      "href": "context/stakeholders.html#IAM-STK-003"
+    },
+    {
+      "id": "IAM-STK-004",
+      "type": "stakeholder-need",
+      "title": "Equipes de produto precisam integrar aplicações rapidamente",
+      "status": "approved",
+      "body": "Times internos precisam de uma interface padronizada para login e autorização.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "developer;integration"
+      },
+      "relations": [],
+      "source": {
+        "file": "context/stakeholders.qmd",
+        "line": 23,
+        "anchor": "IAM-STK-004"
+      },
+      "href": "context/stakeholders.html#IAM-STK-004"
+    },
+    {
+      "id": "IAM-STK-005",
+      "type": "stakeholder-need",
+      "title": "Auditoria precisa de rastreabilidade de decisões de acesso",
+      "status": "approved",
+      "body": "Auditores precisam reconstruir quem autorizou cada privilégio e quando.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;governance"
+      },
+      "relations": [],
+      "source": {
+        "file": "context/stakeholders.qmd",
+        "line": 29,
+        "anchor": "IAM-STK-005"
+      },
+      "href": "context/stakeholders.html#IAM-STK-005"
+    },
+    {
+      "id": "IAM-COMP-001",
+      "type": "component",
+      "title": "Serviço de autenticação",
+      "status": "implemented",
+      "body": "Valida credenciais, MFA e sessões para os canais do Aegis IAM.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 6,
+        "anchor": "IAM-COMP-001"
+      },
+      "href": "architecture/components.html#IAM-COMP-001"
+    },
+    {
+      "id": "IAM-COMP-002",
+      "type": "component",
+      "title": "Motor de políticas",
+      "status": "implemented",
+      "body": "Avalia políticas por atributo e retorna decisões de permitir ou negar.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 12,
+        "anchor": "IAM-COMP-002"
+      },
+      "href": "architecture/components.html#IAM-COMP-002"
+    },
+    {
+      "id": "IAM-COMP-003",
+      "type": "component",
+      "title": "Orquestrador de ciclo de vida",
+      "status": "implemented",
+      "body": "Consome eventos de pessoas e executa mudanças controladas em contas e grupos.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 18,
+        "anchor": "IAM-COMP-003"
+      },
+      "href": "architecture/components.html#IAM-COMP-003"
+    },
+    {
+      "id": "IAM-COMP-004",
+      "type": "component",
+      "title": "Cofre de auditoria",
+      "status": "implemented",
+      "body": "Armazena eventos com integridade verificável e consulta controlada.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;compliance"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 24,
+        "anchor": "IAM-COMP-004"
+      },
+      "href": "architecture/components.html#IAM-COMP-004"
+    },
+    {
+      "id": "IAM-COMP-005",
+      "type": "component",
+      "title": "Serviço de recuperação",
+      "status": "implemented",
+      "body": "Coordena prova de identidade, aprovação e emissão segura de nova credencial.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 30,
+        "anchor": "IAM-COMP-005"
+      },
+      "href": "architecture/components.html#IAM-COMP-005"
+    },
+    {
+      "id": "IAM-COMP-006",
+      "type": "component",
+      "title": "Portal de identidade",
+      "status": "implemented",
+      "body": "Oferece telas acessíveis para login, consentimento e administração de conta.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "experience;accessibility"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 36,
+        "anchor": "IAM-COMP-006"
+      },
+      "href": "architecture/components.html#IAM-COMP-006"
+    },
+    {
+      "id": "IAM-IF-001",
+      "type": "interface",
+      "title": "API OpenID Connect",
+      "status": "implemented",
+      "body": "Interface de federação para emissão de tokens e descoberta de metadados.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "integration;oidc"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 42,
+        "anchor": "IAM-IF-001"
+      },
+      "href": "architecture/components.html#IAM-IF-001"
+    },
+    {
+      "id": "IAM-IF-002",
+      "type": "interface",
+      "title": "API SCIM de provisão",
+      "status": "implemented",
+      "body": "Interface para sincronizar usuários e grupos a partir de sistemas de origem.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;scim"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 48,
+        "anchor": "IAM-IF-002"
+      },
+      "href": "architecture/components.html#IAM-IF-002"
+    },
+    {
+      "id": "IAM-IF-003",
+      "type": "interface",
+      "title": "Fluxo de eventos de auditoria",
+      "status": "implemented",
+      "body": "Interface de eventos assinados entregue ao cofre e ao monitoramento de segurança.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;events"
+      },
+      "relations": [],
+      "source": {
+        "file": "architecture/components.qmd",
+        "line": 54,
+        "anchor": "IAM-IF-003"
+      },
+      "href": "architecture/components.html#IAM-IF-003"
+    },
+    {
+      "id": "IAM-RISK-001",
+      "type": "risk",
+      "title": "Tomada de conta por phishing",
+      "status": "in-review",
+      "body": "Uma credencial capturada pode permitir acesso indevido sem um segundo fator resistente.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;account-takeover"
+      },
+      "relations": [],
+      "source": {
+        "file": "risks/security.qmd",
+        "line": 6,
+        "anchor": "IAM-RISK-001"
+      },
+      "href": "risks/security.html#IAM-RISK-001"
+    },
+    {
+      "id": "IAM-RISK-002",
+      "type": "risk",
+      "title": "Escalada de privilégio por política permissiva",
+      "status": "approved",
+      "body": "Uma política ampla ou ausente pode conceder acesso além da necessidade de trabalho.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;privilege-escalation"
+      },
+      "relations": [],
+      "source": {
+        "file": "risks/security.qmd",
+        "line": 12,
+        "anchor": "IAM-RISK-002"
+      },
+      "href": "risks/security.html#IAM-RISK-002"
+    },
+    {
+      "id": "IAM-RISK-003",
+      "type": "risk",
+      "title": "Vazamento de dados pessoais em logs",
+      "status": "approved",
+      "body": "Eventos excessivamente detalhados podem expor identificadores e atributos pessoais.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;audit"
+      },
+      "relations": [],
+      "source": {
+        "file": "risks/security.qmd",
+        "line": 18,
+        "anchor": "IAM-RISK-003"
+      },
+      "href": "risks/security.html#IAM-RISK-003"
+    },
+    {
+      "id": "IAM-RISK-004",
+      "type": "risk",
+      "title": "Indisponibilidade durante recuperação de conta",
+      "status": "draft",
+      "body": "Uma falha prolongada pode impedir usuários legítimos de recuperar acesso crítico.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "availability;recovery"
+      },
+      "relations": [],
+      "source": {
+        "file": "risks/security.qmd",
+        "line": 24,
+        "anchor": "IAM-RISK-004"
+      },
+      "href": "risks/security.html#IAM-RISK-004"
+    },
+    {
+      "id": "IAM-TC-001",
+      "type": "test-case",
+      "title": "Autenticação com credencial válida",
+      "status": "passed",
+      "body": "Verifica criação de sessão somente para credencial corporativa válida.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;regression"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-001",
+          "target": "IAM-EVD-001",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 6,
+        "anchor": "IAM-TC-001"
+      },
+      "href": "verification/test-cases.html#IAM-TC-001"
+    },
+    {
+      "id": "IAM-TC-002",
+      "type": "test-case",
+      "title": "MFA obrigatório para administrador",
+      "status": "passed",
+      "body": "Verifica bloqueio de papel privilegiado quando o segundo fator não é satisfeito.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "mfa;security"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-002",
+          "target": "IAM-EVD-002",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 12,
+        "anchor": "IAM-TC-002"
+      },
+      "href": "verification/test-cases.html#IAM-TC-002"
+    },
+    {
+      "id": "IAM-TC-003",
+      "type": "test-case",
+      "title": "Revogação de sessão suspensa",
+      "status": "passed",
+      "body": "Verifica invalidação de tokens após suspensão de conta.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "session;security"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-003",
+          "target": "IAM-EVD-003",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 18,
+        "anchor": "IAM-TC-003"
+      },
+      "href": "verification/test-cases.html#IAM-TC-003"
+    },
+    {
+      "id": "IAM-TC-004",
+      "type": "test-case",
+      "title": "Decisão por atributo",
+      "status": "passed",
+      "body": "Verifica avaliação de sujeito, recurso, ação e contexto em uma política.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-004",
+          "target": "IAM-EVD-004",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 24,
+        "anchor": "IAM-TC-004"
+      },
+      "href": "verification/test-cases.html#IAM-TC-004"
+    },
+    {
+      "id": "IAM-TC-005",
+      "type": "test-case",
+      "title": "Negação sem regra permissiva",
+      "status": "passed",
+      "body": "Verifica que uma solicitação sem regra permissiva é negada.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-005",
+          "target": "IAM-EVD-005",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 30,
+        "anchor": "IAM-TC-005"
+      },
+      "href": "verification/test-cases.html#IAM-TC-005"
+    },
+    {
+      "id": "IAM-TC-006",
+      "type": "test-case",
+      "title": "Latência da decisão de acesso",
+      "status": "passed",
+      "body": "Verifica a resposta de autorização dentro do objetivo sob carga nominal.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;performance"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-006",
+          "target": "IAM-EVD-006",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 36,
+        "anchor": "IAM-TC-006"
+      },
+      "href": "verification/test-cases.html#IAM-TC-006"
+    },
+    {
+      "id": "IAM-TC-007",
+      "type": "test-case",
+      "title": "Criação por evento de admissão",
+      "status": "passed",
+      "body": "Verifica criação de conta após evento de admissão válido.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-007",
+          "target": "IAM-EVD-007",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 42,
+        "anchor": "IAM-TC-007"
+      },
+      "href": "verification/test-cases.html#IAM-TC-007"
+    },
+    {
+      "id": "IAM-TC-008",
+      "type": "test-case",
+      "title": "Suspensão por desligamento",
+      "status": "passed",
+      "body": "Verifica suspensão e encerramento de sessão após desligamento.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-008",
+          "target": "IAM-EVD-008",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 48,
+        "anchor": "IAM-TC-008"
+      },
+      "href": "verification/test-cases.html#IAM-TC-008"
+    },
+    {
+      "id": "IAM-TC-009",
+      "type": "test-case",
+      "title": "Campanha de revisão de acesso",
+      "status": "passed",
+      "body": "Verifica abertura de tarefa de revisão para o responsável adequado.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-009",
+          "target": "IAM-EVD-009",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 54,
+        "anchor": "IAM-TC-009"
+      },
+      "href": "verification/test-cases.html#IAM-TC-009"
+    },
+    {
+      "id": "IAM-TC-010",
+      "type": "test-case",
+      "title": "Registro de decisão de autorização",
+      "status": "passed",
+      "body": "Verifica correlação e integridade do evento da decisão de acesso.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;security"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-010",
+          "target": "IAM-EVD-010",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 60,
+        "anchor": "IAM-TC-010"
+      },
+      "href": "verification/test-cases.html#IAM-TC-010"
+    },
+    {
+      "id": "IAM-TC-011",
+      "type": "test-case",
+      "title": "Consulta e retenção de trilha",
+      "status": "passed",
+      "body": "Verifica consulta ordenada e disponibilidade da evidência retida.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-011",
+          "target": "IAM-EVD-011",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 66,
+        "anchor": "IAM-TC-011"
+      },
+      "href": "verification/test-cases.html#IAM-TC-011"
+    },
+    {
+      "id": "IAM-TC-012",
+      "type": "test-case",
+      "title": "Recuperação reforçada",
+      "status": "passed",
+      "body": "Verifica prova adicional de identidade antes da redefinição de credencial.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-012",
+          "target": "IAM-EVD-012",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 72,
+        "anchor": "IAM-TC-012"
+      },
+      "href": "verification/test-cases.html#IAM-TC-012"
+    },
+    {
+      "id": "IAM-TC-013",
+      "type": "test-case",
+      "title": "Acessibilidade da autenticação",
+      "status": "passed",
+      "body": "Verifica navegação por teclado, foco visível e nomes acessíveis no portal.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "accessibility;portal"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-013",
+          "target": "IAM-EVD-013",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 78,
+        "anchor": "IAM-TC-013"
+      },
+      "href": "verification/test-cases.html#IAM-TC-013"
+    },
+    {
+      "id": "IAM-TC-014",
+      "type": "test-case",
+      "title": "Disponibilidade de autenticação",
+      "status": "passed",
+      "body": "Verifica o objetivo mensal em exercício de monitoramento e failover.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "availability;resilience"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-014",
+          "target": "IAM-EVD-014",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 84,
+        "anchor": "IAM-TC-014"
+      },
+      "href": "verification/test-cases.html#IAM-TC-014"
+    },
+    {
+      "id": "IAM-TC-015",
+      "type": "test-case",
+      "title": "Minimização de evento pessoal",
+      "status": "passed",
+      "body": "Verifica ausência de atributos pessoais não necessários no evento de auditoria.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-015",
+          "target": "IAM-EVD-015",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 90,
+        "anchor": "IAM-TC-015"
+      },
+      "href": "verification/test-cases.html#IAM-TC-015"
+    },
+    {
+      "id": "IAM-TC-016",
+      "type": "test-case",
+      "title": "Criptografia de credenciais e segredos",
+      "status": "passed",
+      "body": "Verifica TLS aprovado em trânsito e criptografia de segredos no armazenamento.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-016",
+          "target": "IAM-EVD-016",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 96,
+        "anchor": "IAM-TC-016"
+      },
+      "href": "verification/test-cases.html#IAM-TC-016"
+    },
+    {
+      "id": "IAM-TC-017",
+      "type": "test-case",
+      "title": "Federação OpenID Connect",
+      "status": "passed",
+      "body": "Verifica descoberta, emissão e validação de token OIDC com uma aplicação consumidora.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;oidc"
+      },
+      "relations": [
+        {
+          "type": "evidenced-by",
+          "source": "IAM-TC-017",
+          "target": "IAM-EVD-017",
+          "attributes": {}
+        }
+      ],
+      "source": {
+        "file": "verification/test-cases.qmd",
+        "line": 102,
+        "anchor": "IAM-TC-017"
+      },
+      "href": "verification/test-cases.html#IAM-TC-017"
+    },
+    {
+      "id": "IAM-EVD-001",
+      "type": "evidence",
+      "title": "Relatório de autenticação 2026-08-25",
+      "status": "verified",
+      "body": "Execução automatizada do cenário de credencial válida no ambiente de integração.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 5,
+        "anchor": "IAM-EVD-001"
+      },
+      "href": "verification/evidence.html#IAM-EVD-001"
+    },
+    {
+      "id": "IAM-EVD-002",
+      "type": "evidence",
+      "title": "Relatório de MFA administrativo",
+      "status": "verified",
+      "body": "Execução automatizada do bloqueio sem segundo fator.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "mfa;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 11,
+        "anchor": "IAM-EVD-002"
+      },
+      "href": "verification/evidence.html#IAM-EVD-002"
+    },
+    {
+      "id": "IAM-EVD-003",
+      "type": "evidence",
+      "title": "Relatório de revogação de sessão",
+      "status": "verified",
+      "body": "Execução automatizada de suspensão e invalidação de tokens.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "session;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 17,
+        "anchor": "IAM-EVD-003"
+      },
+      "href": "verification/evidence.html#IAM-EVD-003"
+    },
+    {
+      "id": "IAM-EVD-004",
+      "type": "evidence",
+      "title": "Relatório de política por atributo",
+      "status": "verified",
+      "body": "Execução automatizada de decisão contextual de acesso.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 23,
+        "anchor": "IAM-EVD-004"
+      },
+      "href": "verification/evidence.html#IAM-EVD-004"
+    },
+    {
+      "id": "IAM-EVD-005",
+      "type": "evidence",
+      "title": "Relatório de negação padrão",
+      "status": "verified",
+      "body": "Execução automatizada de uma solicitação sem regra permissiva.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "least-privilege;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 29,
+        "anchor": "IAM-EVD-005"
+      },
+      "href": "verification/evidence.html#IAM-EVD-005"
+    },
+    {
+      "id": "IAM-EVD-006",
+      "type": "evidence",
+      "title": "Relatório de carga da autorização",
+      "status": "verified",
+      "body": "Resultado do teste de carga para o objetivo de resposta de autorização.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "performance;load"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 35,
+        "anchor": "IAM-EVD-006"
+      },
+      "href": "verification/evidence.html#IAM-EVD-006"
+    },
+    {
+      "id": "IAM-EVD-007",
+      "type": "evidence",
+      "title": "Relatório de provisão por admissão",
+      "status": "verified",
+      "body": "Execução automatizada que registra a conta criada a partir de um evento válido de RH.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;ci"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 41,
+        "anchor": "IAM-EVD-007"
+      },
+      "href": "verification/evidence.html#IAM-EVD-007"
+    },
+    {
+      "id": "IAM-EVD-008",
+      "type": "evidence",
+      "title": "Relatório de suspensão por desligamento",
+      "status": "verified",
+      "body": "Execução automatizada que confirma suspensão da conta e invalidação das sessões.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 47,
+        "anchor": "IAM-EVD-008"
+      },
+      "href": "verification/evidence.html#IAM-EVD-008"
+    },
+    {
+      "id": "IAM-EVD-009",
+      "type": "evidence",
+      "title": "Relatório de campanha de revisão",
+      "status": "verified",
+      "body": "Execução automatizada que comprova a criação de tarefa para o responsável pelo recurso.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 53,
+        "anchor": "IAM-EVD-009"
+      },
+      "href": "verification/evidence.html#IAM-EVD-009"
+    },
+    {
+      "id": "IAM-EVD-010",
+      "type": "evidence",
+      "title": "Relatório de evento de autorização",
+      "status": "verified",
+      "body": "Execução automatizada que valida correlação e integridade de uma decisão registrada.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;integrity"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 59,
+        "anchor": "IAM-EVD-010"
+      },
+      "href": "verification/evidence.html#IAM-EVD-010"
+    },
+    {
+      "id": "IAM-EVD-011",
+      "type": "evidence",
+      "title": "Relatório de consulta e retenção",
+      "status": "verified",
+      "body": "Resultado de consulta ordenada em eventos preservados no período de retenção configurado.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 65,
+        "anchor": "IAM-EVD-011"
+      },
+      "href": "verification/evidence.html#IAM-EVD-011"
+    },
+    {
+      "id": "IAM-EVD-012",
+      "type": "evidence",
+      "title": "Relatório de recuperação reforçada",
+      "status": "verified",
+      "body": "Execução automatizada que registra a prova adicional de identidade antes da redefinição.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 71,
+        "anchor": "IAM-EVD-012"
+      },
+      "href": "verification/evidence.html#IAM-EVD-012"
+    },
+    {
+      "id": "IAM-EVD-013",
+      "type": "evidence",
+      "title": "Relatório de acessibilidade do portal",
+      "status": "verified",
+      "body": "Resultado de teste automatizado e manual de teclado, foco e nomes acessíveis.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "accessibility;portal"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 77,
+        "anchor": "IAM-EVD-013"
+      },
+      "href": "verification/evidence.html#IAM-EVD-013"
+    },
+    {
+      "id": "IAM-EVD-014",
+      "type": "evidence",
+      "title": "Relatório de disponibilidade da autenticação",
+      "status": "verified",
+      "body": "Resultado do exercício de failover e monitoramento mensal do serviço de autenticação.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "availability;failover"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 83,
+        "anchor": "IAM-EVD-014"
+      },
+      "href": "verification/evidence.html#IAM-EVD-014"
+    },
+    {
+      "id": "IAM-EVD-015",
+      "type": "evidence",
+      "title": "Relatório de minimização de dados",
+      "status": "verified",
+      "body": "Resultado da inspeção que confirma a ausência de atributos pessoais desnecessários.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 89,
+        "anchor": "IAM-EVD-015"
+      },
+      "href": "verification/evidence.html#IAM-EVD-015"
+    },
+    {
+      "id": "IAM-EVD-016",
+      "type": "evidence",
+      "title": "Relatório de criptografia de credenciais",
+      "status": "verified",
+      "body": "Resultado da verificação de TLS e criptografia de segredos em armazenamento.",
+      "rationale": "",
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 95,
+        "anchor": "IAM-EVD-016"
+      },
+      "href": "verification/evidence.html#IAM-EVD-016"
+    },
+    {
+      "id": "IAM-EVD-017",
+      "type": "evidence",
+      "title": "Relatório de interoperabilidade OIDC",
+      "status": "verified",
+      "body": "Resultado da integração de descoberta e troca de token com a aplicação consumidora.",
+      "rationale": "",
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;oidc"
+      },
+      "relations": [],
+      "source": {
+        "file": "verification/evidence.qmd",
+        "line": 101,
+        "anchor": "IAM-EVD-017"
+      },
+      "href": "verification/evidence.html#IAM-EVD-017"
+    }
+  ],
+  "relations": [
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-001",
+      "target": "IAM-STK-001",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-001",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-001",
+      "target": "IAM-TC-001",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-002",
+      "target": "IAM-STK-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-002",
+      "target": "IAM-COMP-002",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-002",
+      "target": "IAM-TC-004",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-003",
+      "target": "IAM-STK-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-003",
+      "target": "IAM-COMP-003",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-003",
+      "target": "IAM-TC-007",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-004",
+      "target": "IAM-STK-005",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-004",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-004",
+      "target": "IAM-TC-010",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-005",
+      "target": "IAM-STK-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-005",
+      "target": "IAM-COMP-005",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-005",
+      "target": "IAM-TC-012",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-006",
+      "target": "IAM-STK-004",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-SYS-006",
+      "target": "IAM-IF-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-SYS-006",
+      "target": "IAM-TC-017",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-007",
+      "target": "IAM-STK-005",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-SYS-008",
+      "target": "IAM-STK-004",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-001",
+      "target": "IAM-SYS-001",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-001",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-001",
+      "target": "IAM-TC-001",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-002",
+      "target": "IAM-SYS-001",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-002",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-002",
+      "target": "IAM-TC-002",
+      "attributes": {}
+    },
+    {
+      "type": "mitigates",
+      "source": "IAM-FUN-002",
+      "target": "IAM-RISK-001",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-003",
+      "target": "IAM-SYS-001",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-003",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-003",
+      "target": "IAM-TC-003",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-004",
+      "target": "IAM-SYS-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-004",
+      "target": "IAM-COMP-002",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-004",
+      "target": "IAM-TC-004",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-005",
+      "target": "IAM-SYS-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-005",
+      "target": "IAM-COMP-002",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-005",
+      "target": "IAM-TC-005",
+      "attributes": {}
+    },
+    {
+      "type": "mitigates",
+      "source": "IAM-FUN-005",
+      "target": "IAM-RISK-002",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-006",
+      "target": "IAM-SYS-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-006",
+      "target": "IAM-COMP-002",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-006",
+      "target": "IAM-TC-006",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-007",
+      "target": "IAM-SYS-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-007",
+      "target": "IAM-COMP-003",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-007",
+      "target": "IAM-TC-007",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-008",
+      "target": "IAM-SYS-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-008",
+      "target": "IAM-COMP-003",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-008",
+      "target": "IAM-TC-008",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-009",
+      "target": "IAM-SYS-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-009",
+      "target": "IAM-COMP-003",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-009",
+      "target": "IAM-TC-009",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-010",
+      "target": "IAM-SYS-004",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-010",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-010",
+      "target": "IAM-TC-010",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-011",
+      "target": "IAM-SYS-004",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-011",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-011",
+      "target": "IAM-TC-011",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-012",
+      "target": "IAM-SYS-005",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-FUN-012",
+      "target": "IAM-COMP-005",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-FUN-012",
+      "target": "IAM-TC-012",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-013",
+      "target": "IAM-SYS-005",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-FUN-014",
+      "target": "IAM-SYS-006",
+      "attributes": {}
+    },
+    {
+      "type": "conflicts-with",
+      "source": "IAM-FUN-015",
+      "target": "IAM-SYS-001",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-001",
+      "target": "IAM-STK-001",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-001",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-001",
+      "target": "IAM-TC-016",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-002",
+      "target": "IAM-STK-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-002",
+      "target": "IAM-COMP-001",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-002",
+      "target": "IAM-TC-014",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-003",
+      "target": "IAM-STK-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-003",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-003",
+      "target": "IAM-TC-015",
+      "attributes": {}
+    },
+    {
+      "type": "mitigates",
+      "source": "IAM-NFR-003",
+      "target": "IAM-RISK-003",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-004",
+      "target": "IAM-STK-004",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-004",
+      "target": "IAM-COMP-002",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-004",
+      "target": "IAM-TC-006",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-005",
+      "target": "IAM-STK-005",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-005",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-005",
+      "target": "IAM-TC-010",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-006",
+      "target": "IAM-STK-004",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-006",
+      "target": "IAM-COMP-006",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-006",
+      "target": "IAM-TC-013",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-007",
+      "target": "IAM-STK-002",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-007",
+      "target": "IAM-COMP-004",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-007",
+      "target": "IAM-TC-011",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-008",
+      "target": "IAM-STK-003",
+      "attributes": {}
+    },
+    {
+      "type": "implemented-by",
+      "source": "IAM-NFR-008",
+      "target": "IAM-COMP-005",
+      "attributes": {}
+    },
+    {
+      "type": "verified-by",
+      "source": "IAM-NFR-008",
+      "target": "IAM-TC-012",
+      "attributes": {}
+    },
+    {
+      "type": "mitigates",
+      "source": "IAM-NFR-008",
+      "target": "IAM-RISK-004",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-009",
+      "target": "IAM-STK-003",
+      "attributes": {}
+    },
+    {
+      "type": "derives-from",
+      "source": "IAM-NFR-010",
+      "target": "IAM-STK-004",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-001",
+      "target": "IAM-EVD-001",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-002",
+      "target": "IAM-EVD-002",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-003",
+      "target": "IAM-EVD-003",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-004",
+      "target": "IAM-EVD-004",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-005",
+      "target": "IAM-EVD-005",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-006",
+      "target": "IAM-EVD-006",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-007",
+      "target": "IAM-EVD-007",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-008",
+      "target": "IAM-EVD-008",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-009",
+      "target": "IAM-EVD-009",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-010",
+      "target": "IAM-EVD-010",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-011",
+      "target": "IAM-EVD-011",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-012",
+      "target": "IAM-EVD-012",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-013",
+      "target": "IAM-EVD-013",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-014",
+      "target": "IAM-EVD-014",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-015",
+      "target": "IAM-EVD-015",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-016",
+      "target": "IAM-EVD-016",
+      "attributes": {}
+    },
+    {
+      "type": "evidenced-by",
+      "source": "IAM-TC-017",
+      "target": "IAM-EVD-017",
+      "attributes": {}
+    }
+  ],
+  "coverage": {
+    "requirements": 33,
+    "approved": 26,
+    "implemented": 26,
+    "verified": 26,
+    "implementation_coverage": 78.8,
+    "verification_coverage": 78.8
+  },
+  "validation": [],
+  "backlinks": {
+    "IAM-SYS-001": [
+      {
+        "source": "IAM-FUN-001",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-002",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-003",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-015",
+        "type": "conflicts-with"
+      }
+    ],
+    "IAM-SYS-002": [
+      {
+        "source": "IAM-FUN-004",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-005",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-006",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-SYS-003": [
+      {
+        "source": "IAM-FUN-007",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-008",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-009",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-SYS-004": [
+      {
+        "source": "IAM-FUN-010",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-011",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-SYS-005": [
+      {
+        "source": "IAM-FUN-012",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-FUN-013",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-SYS-006": [
+      {
+        "source": "IAM-FUN-014",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-SYS-007": [],
+    "IAM-SYS-008": [],
+    "IAM-FUN-001": [],
+    "IAM-FUN-002": [],
+    "IAM-FUN-003": [],
+    "IAM-FUN-004": [],
+    "IAM-FUN-005": [],
+    "IAM-FUN-006": [],
+    "IAM-FUN-007": [],
+    "IAM-FUN-008": [],
+    "IAM-FUN-009": [],
+    "IAM-FUN-010": [],
+    "IAM-FUN-011": [],
+    "IAM-FUN-012": [],
+    "IAM-FUN-013": [],
+    "IAM-FUN-014": [],
+    "IAM-FUN-015": [],
+    "IAM-NFR-001": [],
+    "IAM-NFR-002": [],
+    "IAM-NFR-003": [],
+    "IAM-NFR-004": [],
+    "IAM-NFR-005": [],
+    "IAM-NFR-006": [],
+    "IAM-NFR-007": [],
+    "IAM-NFR-008": [],
+    "IAM-NFR-009": [],
+    "IAM-NFR-010": [],
+    "IAM-STK-001": [
+      {
+        "source": "IAM-SYS-001",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-001",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-STK-002": [
+      {
+        "source": "IAM-SYS-002",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-003",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-007",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-STK-003": [
+      {
+        "source": "IAM-SYS-003",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-SYS-005",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-002",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-008",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-009",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-STK-004": [
+      {
+        "source": "IAM-SYS-006",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-SYS-008",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-004",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-006",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-010",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-STK-005": [
+      {
+        "source": "IAM-SYS-004",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-SYS-007",
+        "type": "derives-from"
+      },
+      {
+        "source": "IAM-NFR-005",
+        "type": "derives-from"
+      }
+    ],
+    "IAM-COMP-001": [
+      {
+        "source": "IAM-SYS-001",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-001",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-002",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-003",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-001",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-002",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-COMP-002": [
+      {
+        "source": "IAM-SYS-002",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-004",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-005",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-006",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-004",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-COMP-003": [
+      {
+        "source": "IAM-SYS-003",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-007",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-008",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-009",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-COMP-004": [
+      {
+        "source": "IAM-SYS-004",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-010",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-011",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-003",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-005",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-007",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-COMP-005": [
+      {
+        "source": "IAM-SYS-005",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-FUN-012",
+        "type": "implemented-by"
+      },
+      {
+        "source": "IAM-NFR-008",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-COMP-006": [
+      {
+        "source": "IAM-NFR-006",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-IF-001": [
+      {
+        "source": "IAM-SYS-006",
+        "type": "implemented-by"
+      }
+    ],
+    "IAM-IF-002": [],
+    "IAM-IF-003": [],
+    "IAM-RISK-001": [
+      {
+        "source": "IAM-FUN-002",
+        "type": "mitigates"
+      }
+    ],
+    "IAM-RISK-002": [
+      {
+        "source": "IAM-FUN-005",
+        "type": "mitigates"
+      }
+    ],
+    "IAM-RISK-003": [
+      {
+        "source": "IAM-NFR-003",
+        "type": "mitigates"
+      }
+    ],
+    "IAM-RISK-004": [
+      {
+        "source": "IAM-NFR-008",
+        "type": "mitigates"
+      }
+    ],
+    "IAM-TC-001": [
+      {
+        "source": "IAM-SYS-001",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-FUN-001",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-002": [
+      {
+        "source": "IAM-FUN-002",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-003": [
+      {
+        "source": "IAM-FUN-003",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-004": [
+      {
+        "source": "IAM-SYS-002",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-FUN-004",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-005": [
+      {
+        "source": "IAM-FUN-005",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-006": [
+      {
+        "source": "IAM-FUN-006",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-NFR-004",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-007": [
+      {
+        "source": "IAM-SYS-003",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-FUN-007",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-008": [
+      {
+        "source": "IAM-FUN-008",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-009": [
+      {
+        "source": "IAM-FUN-009",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-010": [
+      {
+        "source": "IAM-SYS-004",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-FUN-010",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-NFR-005",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-011": [
+      {
+        "source": "IAM-FUN-011",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-NFR-007",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-012": [
+      {
+        "source": "IAM-SYS-005",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-FUN-012",
+        "type": "verified-by"
+      },
+      {
+        "source": "IAM-NFR-008",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-013": [
+      {
+        "source": "IAM-NFR-006",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-014": [
+      {
+        "source": "IAM-NFR-002",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-015": [
+      {
+        "source": "IAM-NFR-003",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-016": [
+      {
+        "source": "IAM-NFR-001",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-TC-017": [
+      {
+        "source": "IAM-SYS-006",
+        "type": "verified-by"
+      }
+    ],
+    "IAM-EVD-001": [
+      {
+        "source": "IAM-TC-001",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-002": [
+      {
+        "source": "IAM-TC-002",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-003": [
+      {
+        "source": "IAM-TC-003",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-004": [
+      {
+        "source": "IAM-TC-004",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-005": [
+      {
+        "source": "IAM-TC-005",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-006": [
+      {
+        "source": "IAM-TC-006",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-007": [
+      {
+        "source": "IAM-TC-007",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-008": [
+      {
+        "source": "IAM-TC-008",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-009": [
+      {
+        "source": "IAM-TC-009",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-010": [
+      {
+        "source": "IAM-TC-010",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-011": [
+      {
+        "source": "IAM-TC-011",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-012": [
+      {
+        "source": "IAM-TC-012",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-013": [
+      {
+        "source": "IAM-TC-013",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-014": [
+      {
+        "source": "IAM-TC-014",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-015": [
+      {
+        "source": "IAM-TC-015",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-016": [
+      {
+        "source": "IAM-TC-016",
+        "type": "evidenced-by"
+      }
+    ],
+    "IAM-EVD-017": [
+      {
+        "source": "IAM-TC-017",
+        "type": "evidenced-by"
+      }
+    ]
+  }
+}
\ No newline at end of file
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/tests/test_v1_contract.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/tests/test_v1_contract.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-before/tests/test_v1_contract.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-1-after/tests/test_v1_contract.py	2026-08-25 09:14:34.030121183 -0300
@@ -0,0 +1,66 @@
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+from jsonschema import Draft202012Validator, RefResolver
+
+ROOT = Path(__file__).resolve().parents[1]
+SCHEMAS = ROOT / "schemas"
+GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"
+
+
+def load_json(path: Path) -> dict[str, object]:
+    return json.loads(path.read_text(encoding="utf-8"))
+
+
+def legacy_projection(payload: dict[str, object]) -> dict[str, object]:
+    projected = {key: value for key, value in payload.items() if key != "extensions"}
+    projected["objects"] = sorted(projected["objects"], key=lambda item: (item["id"].casefold(), item["id"]))
+    projected["relations"] = sorted(
+        projected["relations"],
+        key=lambda item: (
+            item["source"].casefold(), item["source"], item["type"],
+            item["target"].casefold(), item["target"],
+            json.dumps(item.get("attributes", {}), ensure_ascii=False, sort_keys=True),
+        ),
+    )
+    projected["validation"] = sorted(
+        projected["validation"],
+        key=lambda item: (item["severity"], item["code"], item.get("object_id") or "", item["message"]),
+    )
+    projected["backlinks"] = {
+        key: sorted(value, key=lambda item: (item["source"].casefold(), item["type"]))
+        for key, value in sorted(projected["backlinks"].items())
+    }
+    for item in projected["objects"]:
+        item["relations"] = sorted(
+            item.get("relations", []),
+            key=lambda relation: (
+                relation["type"], relation["target"].casefold(), relation["target"],
+                json.dumps(relation.get("attributes", {}), ensure_ascii=False, sort_keys=True),
+            ),
+        )
+    return projected
+
+
+def test_frozen_aegis_payload_validates_against_v1_envelope() -> None:
+    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
+    Draft202012Validator.check_schema(schema)
+    resolver = RefResolver(
+        (SCHEMAS / "needs-envelope-v1.schema.json").as_uri(),
+        schema,
+        store={
+            "https://quarto-needs.dev/schema/needs.schema.json": load_json(
+                SCHEMAS / "needs.schema.json"
+            )
+        },
+    )
+    Draft202012Validator(schema, resolver=resolver).validate(load_json(GOLDEN))
+
+
+def test_frozen_payload_has_nested_and_top_level_relation_equivalence() -> None:
+    payload = load_json(GOLDEN)
+    nested = [relation for item in payload["objects"] for relation in item.get("relations", [])]
+    key = lambda relation: json.dumps(relation, ensure_ascii=False, sort_keys=True)
+    assert sorted(nested, key=key) == sorted(payload["relations"], key=key)
