# Review package

Snapshot range: `task-4-before` -> `task-4-after`

## Files changed (8)

- `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md`
- `schemas/vendor/sarif-2.1.0/VENDORED.md`
- `schemas/vendor/sarif-2.1.0/sarif-schema.json`
- `src/quarto_needs/cli.py`
- `src/quarto_needs/diff.py`
- `src/quarto_needs/exporters/sarif_export.py`
- `src/quarto_needs/impact.py`
- `tests/test_export_sarif.py`

## Summary

3241 lines added, 58 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 15:50:43.859907314 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 17:17:22.941258395 -0300
@@ -365,21 +365,21 @@
 
 Create `tests/test_export_sarif.py`:
 
 ```python
 from __future__ import annotations
 
 import json
 from pathlib import Path
 
 import pytest
-from jsonschema import Draft202012Validator
+from jsonschema import Draft7Validator
 
 from quarto_needs.analysis import analyze_project
 from quarto_needs.config import load_config
 from quarto_needs.exporters import sarif_export
 
 ROOT = Path(__file__).resolve().parents[1]
 SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"
 
 
 def write_project(root: Path) -> None:
@@ -395,30 +395,30 @@
     )
 
 
 def snapshot_with_findings(root: Path):
     result = analyze_project(root, config=load_config(root))
     return result.declarations and result.findings and result or None
 
 
 def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
     schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
-    Draft202012Validator.check_schema(schema)
+    Draft7Validator.check_schema(schema)
 
     (tmp_path / "ok.qmd").write_text(
         "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
     )
     result = analyze_project(tmp_path, config=load_config(tmp_path))
     assert result.snapshot is not None
 
     payload = json.loads(sarif_export.render(result.snapshot))
-    Draft202012Validator(schema).validate(payload)
+    Draft7Validator(schema).validate(payload)
 
 
 def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
     write_project(tmp_path)
     result = analyze_project(tmp_path, config=load_config(tmp_path))
     assert any(f.code == "REQ004" for f in result.findings)
 
     payload = json.loads(sarif_export.render_from_findings(result.findings))
     result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/schemas/vendor/sarif-2.1.0/sarif-schema.json .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/schemas/vendor/sarif-2.1.0/sarif-schema.json
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/schemas/vendor/sarif-2.1.0/sarif-schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/schemas/vendor/sarif-2.1.0/sarif-schema.json	2026-08-26 17:23:56.831984356 -0300
@@ -0,0 +1,2882 @@
+{
+  "$schema": "http://json-schema.org/draft-07/schema#",
+  "$id": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
+  "additionalProperties": false,
+  "definitions": {
+    "address": {
+      "description": "A physical or virtual address, or a range of addresses, in an 'addressable region' (memory or a binary file).",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "absoluteAddress": {
+          "description": "The address expressed as a byte offset from the start of the addressable region.",
+          "type": "integer",
+          "minimum": -1,
+          "default": -1
+        },
+        "relativeAddress": {
+          "description": "The address expressed as a byte offset from the absolute address of the top-most parent object.",
+          "type": "integer"
+        },
+        "length": {
+          "description": "The number of bytes in this range of addresses.",
+          "type": "integer"
+        },
+        "kind": {
+          "description": "An open-ended string that identifies the address kind. 'data', 'function', 'header','instruction', 'module', 'page', 'section', 'segment', 'stack', 'stackFrame', 'table' are well-known values.",
+          "type": "string"
+        },
+        "name": {
+          "description": "A name that is associated with the address, e.g., '.text'.",
+          "type": "string"
+        },
+        "fullyQualifiedName": {
+          "description": "A human-readable fully qualified name that is associated with the address.",
+          "type": "string"
+        },
+        "offsetFromParent": {
+          "description": "The byte offset of this address from the absolute or relative address of the parent object.",
+          "type": "integer"
+        },
+        "index": {
+          "description": "The index within run.addresses of the cached object for this address.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "parentIndex": {
+          "description": "The index within run.addresses of the parent object.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the address."
+        }
+      }
+    },
+    "artifact": {
+      "description": "A single artifact. In some cases, this artifact might be nested within another artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the artifact."
+        },
+        "location": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact."
+        },
+        "parentIndex": {
+          "description": "Identifies the index of the immediate parent of the artifact, if this artifact is nested.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "offset": {
+          "description": "The offset in bytes of the artifact within its containing artifact.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "length": {
+          "description": "The length of the artifact in bytes.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "roles": {
+          "description": "The role or roles played by the artifact in the analysis.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "enum": [
+              "analysisTarget",
+              "attachment",
+              "responseFile",
+              "resultFile",
+              "standardStream",
+              "tracedFile",
+              "unmodified",
+              "modified",
+              "added",
+              "deleted",
+              "renamed",
+              "uncontrolled",
+              "driver",
+              "extension",
+              "translation",
+              "taxonomy",
+              "policy",
+              "referencedOnCommandLine",
+              "memoryContents",
+              "directory",
+              "userSpecifiedConfiguration",
+              "toolSpecifiedConfiguration",
+              "debugOutputFile"
+            ]
+          }
+        },
+        "mimeType": {
+          "description": "The MIME type (RFC 2045) of the artifact.",
+          "type": "string",
+          "pattern": "[^/]+/.+"
+        },
+        "contents": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The contents of the artifact."
+        },
+        "encoding": {
+          "description": "Specifies the encoding for an artifact object that refers to a text file.",
+          "type": "string"
+        },
+        "sourceLanguage": {
+          "description": "Specifies the source language for any artifact object that refers to a text file that contains source code.",
+          "type": "string"
+        },
+        "hashes": {
+          "description": "A dictionary, each of whose keys is the name of a hash function and each of whose values is the hashed value of the artifact produced by the specified hash function.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "lastModifiedTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the artifact was most recently modified. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact."
+        }
+      }
+    },
+    "artifactChange": {
+      "description": "A change to a single artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact to change."
+        },
+        "replacements": {
+          "description": "An array of replacement objects, each of which represents the replacement of a single region in a single artifact specified by 'artifactLocation'.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/replacement"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the change."
+        }
+      },
+      "required": ["artifactLocation", "replacements"]
+    },
+    "artifactContent": {
+      "description": "Represents the contents of an artifact.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "UTF-8-encoded content from a text artifact.",
+          "type": "string"
+        },
+        "binary": {
+          "description": "MIME Base64-encoded content from a binary artifact, or from a text artifact in its original encoding.",
+          "type": "string"
+        },
+        "rendered": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "An alternate rendered representation of the artifact (e.g., a decompiled representation of a binary region)."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact content."
+        }
+      }
+    },
+    "artifactLocation": {
+      "description": "Specifies the location of an artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "uri": {
+          "description": "A string containing a valid relative or absolute URI.",
+          "type": "string",
+          "format": "uri-reference"
+        },
+        "uriBaseId": {
+          "description": "A string which indirectly specifies the absolute URI with respect to which a relative URI in the \"uri\" property is interpreted.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index within the run artifacts array of the artifact object associated with the artifact location.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the artifact location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact location."
+        }
+      }
+    },
+    "attachment": {
+      "description": "An artifact relevant to a result.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A message describing the role played by the attachment."
+        },
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the attachment."
+        },
+        "regions": {
+          "description": "An array of regions of interest within the attachment.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/region"
+          }
+        },
+        "rectangles": {
+          "description": "An array of rectangles specifying areas of interest within the image.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/rectangle"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the attachment."
+        }
+      },
+      "required": ["artifactLocation"]
+    },
+    "codeFlow": {
+      "description": "A set of threadFlows which together describe a pattern of code execution relevant to detecting a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the code flow."
+        },
+        "threadFlows": {
+          "description": "An array of one or more unique threadFlow objects, each of which describes the progress of a program through a thread of execution.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/threadFlow"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the code flow."
+        }
+      },
+      "required": ["threadFlows"]
+    },
+    "configurationOverride": {
+      "description": "Information about how a specific rule or notification was reconfigured at runtime.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "configuration": {
+          "$ref": "#/definitions/reportingConfiguration",
+          "description": "Specifies how the rule or notification was configured during the scan."
+        },
+        "descriptor": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the descriptor whose configuration was overridden."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the configuration override."
+        }
+      },
+      "required": ["configuration", "descriptor"]
+    },
+    "conversion": {
+      "description": "Describes how a converter transformed the output of a static analysis tool from the analysis tool's native output format into the SARIF format.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "tool": {
+          "$ref": "#/definitions/tool",
+          "description": "A tool object that describes the converter."
+        },
+        "invocation": {
+          "$ref": "#/definitions/invocation",
+          "description": "An invocation object that describes the invocation of the converter."
+        },
+        "analysisToolLogFiles": {
+          "description": "The locations of the analysis tool's per-run log files.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the conversion."
+        }
+      },
+      "required": ["tool"]
+    },
+    "edge": {
+      "description": "Represents a directed edge in a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "A string that uniquely identifies the edge within its graph.",
+          "type": "string"
+        },
+        "label": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the edge."
+        },
+        "sourceNodeId": {
+          "description": "Identifies the source node (the node at which the edge starts).",
+          "type": "string"
+        },
+        "targetNodeId": {
+          "description": "Identifies the target node (the node at which the edge ends).",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the edge."
+        }
+      },
+      "required": ["id", "sourceNodeId", "targetNodeId"]
+    },
+    "edgeTraversal": {
+      "description": "Represents the traversal of a single edge during a graph traversal.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "edgeId": {
+          "description": "Identifies the edge being traversed.",
+          "type": "string"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message to display to the user as the edge is traversed."
+        },
+        "finalState": {
+          "description": "The values of relevant expressions after the edge has been traversed.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "stepOverEdgeCount": {
+          "description": "The number of edge traversals necessary to return from a nested graph.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the edge traversal."
+        }
+      },
+      "required": ["edgeId"]
+    },
+    "exception": {
+      "description": "Describes a runtime exception encountered during the execution of an analysis tool.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "kind": {
+          "type": "string",
+          "description": "A string that identifies the kind of exception, for example, the fully qualified type name of an object that was thrown, or the symbolic name of a signal."
+        },
+        "message": {
+          "description": "A message that describes the exception.",
+          "type": "string"
+        },
+        "stack": {
+          "$ref": "#/definitions/stack",
+          "description": "The sequence of function calls leading to the exception."
+        },
+        "innerExceptions": {
+          "description": "An array of exception objects each of which is considered a cause of this exception.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/exception"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the exception."
+        }
+      }
+    },
+    "externalProperties": {
+      "description": "The top-level element of an external property file.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "schema": {
+          "description": "The URI of the JSON schema corresponding to the version of the external property file format.",
+          "type": "string",
+          "format": "uri"
+        },
+        "version": {
+          "description": "The SARIF format version of this external properties object.",
+          "enum": ["2.1.0"]
+        },
+        "guid": {
+          "description": "A stable, unique identifier for this external properties object, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "runGuid": {
+          "description": "A stable, unique identifier for the run associated with this external properties object, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "conversion": {
+          "$ref": "#/definitions/conversion",
+          "description": "A conversion object that will be merged with a separate run."
+        },
+        "graphs": {
+          "description": "An array of graph objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "externalizedProperties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information that will be merged with a separate run."
+        },
+        "artifacts": {
+          "description": "An array of artifact objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifact"
+          }
+        },
+        "invocations": {
+          "description": "Describes the invocation of the analysis tool that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/invocation"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of logical locations such as namespaces, types or functions that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "threadFlowLocations": {
+          "description": "An array of threadFlowLocation objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "results": {
+          "description": "An array of result objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/result"
+          }
+        },
+        "taxonomies": {
+          "description": "Tool taxonomies that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "driver": {
+          "$ref": "#/definitions/toolComponent",
+          "description": "The analysis tool object that will be merged with a separate run."
+        },
+        "extensions": {
+          "description": "Tool extensions that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "policies": {
+          "description": "Tool policies that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "translations": {
+          "description": "Tool translations that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "addresses": {
+          "description": "Addresses that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/address"
+          }
+        },
+        "webRequests": {
+          "description": "Requests that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webRequest"
+          }
+        },
+        "webResponses": {
+          "description": "Responses that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webResponse"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external properties."
+        }
+      }
+    },
+    "externalPropertyFileReference": {
+      "description": "Contains information that enables a SARIF consumer to locate the external property file that contains the value of an externalized property associated with the run.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "location": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the external property file."
+        },
+        "guid": {
+          "description": "A stable, unique identifier for the external property file in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "itemCount": {
+          "description": "A non-negative integer specifying the number of items contained in the external property file.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external property file."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["location"]
+        },
+        {
+          "required": ["guid"]
+        }
+      ]
+    },
+    "externalPropertyFileReferences": {
+      "description": "References to external property files that should be inlined with the content of a root log file.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "conversion": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.conversion object to be merged with the root log file."
+        },
+        "graphs": {
+          "description": "An array of external property files containing a run.graphs object to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "externalizedProperties": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.properties object to be merged with the root log file."
+        },
+        "artifacts": {
+          "description": "An array of external property files containing run.artifacts arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "invocations": {
+          "description": "An array of external property files containing run.invocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of external property files containing run.logicalLocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "threadFlowLocations": {
+          "description": "An array of external property files containing run.threadFlowLocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "results": {
+          "description": "An array of external property files containing run.results arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "taxonomies": {
+          "description": "An array of external property files containing run.taxonomies arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "addresses": {
+          "description": "An array of external property files containing run.addresses arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "driver": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.driver object to be merged with the root log file."
+        },
+        "extensions": {
+          "description": "An array of external property files containing run.extensions arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "policies": {
+          "description": "An array of external property files containing run.policies arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "translations": {
+          "description": "An array of external property files containing run.translations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "webRequests": {
+          "description": "An array of external property files containing run.requests arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "webResponses": {
+          "description": "An array of external property files containing run.responses arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external property files."
+        }
+      }
+    },
+    "fix": {
+      "description": "A proposed fix for the problem represented by a result object. A fix specifies a set of artifacts to modify. For each artifact, it specifies a set of bytes to remove, and provides a set of new bytes to replace them.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the proposed fix, enabling viewers to present the proposed change to an end user."
+        },
+        "artifactChanges": {
+          "description": "One or more artifact changes that comprise a fix for a result.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifactChange"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the fix."
+        }
+      },
+      "required": ["artifactChanges"]
+    },
+    "graph": {
+      "description": "A network of nodes and directed edges that describes some aspect of the structure of the code (for example, a call graph).",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the graph."
+        },
+        "nodes": {
+          "description": "An array of node objects representing the nodes of the graph.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/node"
+          }
+        },
+        "edges": {
+          "description": "An array of edge objects representing the edges of the graph.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/edge"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the graph."
+        }
+      }
+    },
+    "graphTraversal": {
+      "description": "Represents a path through a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "runGraphIndex": {
+          "description": "The index within the run.graphs to be associated with the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "resultGraphIndex": {
+          "description": "The index within the result.graphs to be associated with the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of this graph traversal."
+        },
+        "initialState": {
+          "description": "Values of relevant expressions at the start of the graph traversal that may change during graph traversal.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "immutableState": {
+          "description": "Values of relevant expressions at the start of the graph traversal that remain constant for the graph traversal.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "edgeTraversals": {
+          "description": "The sequences of edges traversed by this graph traversal.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/edgeTraversal"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the graph traversal."
+        }
+      },
+      "oneOf": [
+        {
+          "required": ["runGraphIndex"]
+        },
+        {
+          "required": ["resultGraphIndex"]
+        }
+      ]
+    },
+    "invocation": {
+      "description": "The runtime environment of the analysis tool run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "commandLine": {
+          "description": "The command line used to invoke the tool.",
+          "type": "string"
+        },
+        "arguments": {
+          "description": "An array of strings, containing in order the command line arguments passed to the tool from the operating system.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "type": "string"
+          }
+        },
+        "responseFiles": {
+          "description": "The locations of any response files specified on the tool's command line.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "startTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the invocation started. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "endTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the invocation ended. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "exitCode": {
+          "description": "The process exit code.",
+          "type": "integer"
+        },
+        "ruleConfigurationOverrides": {
+          "description": "An array of configurationOverride objects that describe rules related runtime overrides.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/configurationOverride"
+          }
+        },
+        "notificationConfigurationOverrides": {
+          "description": "An array of configurationOverride objects that describe notifications related runtime overrides.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/configurationOverride"
+          }
+        },
+        "toolExecutionNotifications": {
+          "description": "A list of runtime conditions detected by the tool during the analysis.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/notification"
+          }
+        },
+        "toolConfigurationNotifications": {
+          "description": "A list of conditions detected by the tool that are relevant to the tool's configuration.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/notification"
+          }
+        },
+        "exitCodeDescription": {
+          "description": "The reason for the process exit.",
+          "type": "string"
+        },
+        "exitSignalName": {
+          "description": "The name of the signal that caused the process to exit.",
+          "type": "string"
+        },
+        "exitSignalNumber": {
+          "description": "The numeric value of the signal that caused the process to exit.",
+          "type": "integer"
+        },
+        "processStartFailureMessage": {
+          "description": "The reason given by the operating system that the process failed to start.",
+          "type": "string"
+        },
+        "executionSuccessful": {
+          "description": "Specifies whether the tool's execution completed successfully.",
+          "type": "boolean"
+        },
+        "machine": {
+          "description": "The machine on which the invocation occurred.",
+          "type": "string"
+        },
+        "account": {
+          "description": "The account under which the invocation occurred.",
+          "type": "string"
+        },
+        "processId": {
+          "description": "The id of the process in which the invocation occurred.",
+          "type": "integer"
+        },
+        "executableLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "An absolute URI specifying the location of the executable that was invoked."
+        },
+        "workingDirectory": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The working directory for the invocation."
+        },
+        "environmentVariables": {
+          "description": "The environment variables associated with the analysis tool process, expressed as key/value pairs.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "stdin": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard input stream to the process that was invoked."
+        },
+        "stdout": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard output stream from the process that was invoked."
+        },
+        "stderr": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard error stream from the process that was invoked."
+        },
+        "stdoutStderr": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the interleaved standard output and standard error stream from the process that was invoked."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the invocation."
+        }
+      },
+      "required": ["executionSuccessful"]
+    },
+    "location": {
+      "description": "A location within a programming artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "id": {
+          "description": "Value that distinguishes this location from all other locations within a single result object.",
+          "type": "integer",
+          "minimum": -1,
+          "default": -1
+        },
+        "physicalLocation": {
+          "$ref": "#/definitions/physicalLocation",
+          "description": "Identifies the artifact and region."
+        },
+        "logicalLocations": {
+          "description": "The logical locations associated with the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the location."
+        },
+        "annotations": {
+          "description": "A set of regions relevant to the location.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/region"
+          }
+        },
+        "relationships": {
+          "description": "An array of objects that describe relationships between this location and others.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/locationRelationship"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the location."
+        }
+      }
+    },
+    "locationRelationship": {
+      "description": "Information about the relation of one location to another.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "target": {
+          "description": "A reference to the related location.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the relationship. Well-known kinds include 'includes', 'isIncludedBy' and 'relevant'.",
+          "type": "array",
+          "default": ["relevant"],
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the location relationship."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the location relationship."
+        }
+      },
+      "required": ["target"]
+    },
+    "logicalLocation": {
+      "description": "A logical location of a construct that produced a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "name": {
+          "description": "Identifies the construct in which the result occurred. For example, this property might contain the name of a class or a method.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index within the logical locations array.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "fullyQualifiedName": {
+          "description": "The human-readable fully qualified name of the logical location.",
+          "type": "string"
+        },
+        "decoratedName": {
+          "description": "The machine-readable name for the logical location, such as a mangled function name provided by a C++ compiler that encodes calling convention, return type and other details along with the function name.",
+          "type": "string"
+        },
+        "parentIndex": {
+          "description": "Identifies the index of the immediate parent of the construct in which the result was detected. For example, this property might point to a logical location that represents the namespace that holds a type.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "kind": {
+          "description": "The type of construct this logical location component refers to. Should be one of 'function', 'member', 'module', 'namespace', 'parameter', 'resource', 'returnType', 'type', 'variable', 'object', 'array', 'property', 'value', 'element', 'text', 'attribute', 'comment', 'declaration', 'dtd' or 'processingInstruction', if any of those accurately describe the construct.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the logical location."
+        }
+      }
+    },
+    "message": {
+      "description": "Encapsulates a message intended to be read by the end user.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "A plain text message string.",
+          "type": "string"
+        },
+        "markdown": {
+          "description": "A Markdown message string.",
+          "type": "string"
+        },
+        "id": {
+          "description": "The identifier for this message.",
+          "type": "string"
+        },
+        "arguments": {
+          "description": "An array of strings to substitute into the message string.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the message."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["text"]
+        },
+        {
+          "required": ["id"]
+        }
+      ]
+    },
+    "multiformatMessageString": {
+      "description": "A message string or message format string rendered in multiple formats.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "A plain text message string or format string.",
+          "type": "string"
+        },
+        "markdown": {
+          "description": "A Markdown message string or format string.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the message."
+        }
+      },
+      "required": ["text"]
+    },
+    "node": {
+      "description": "Represents a node in a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "A string that uniquely identifies the node within its graph.",
+          "type": "string"
+        },
+        "label": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the node."
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "A code location associated with the node."
+        },
+        "children": {
+          "description": "Array of child nodes.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/node"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the node."
+        }
+      },
+      "required": ["id"]
+    },
+    "notification": {
+      "description": "Describes a condition relevant to the tool itself, as opposed to being relevant to a target being analyzed by the tool.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "locations": {
+          "description": "The locations relevant to this notification.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the condition that was encountered."
+        },
+        "level": {
+          "description": "A value specifying the severity level of the notification.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "threadId": {
+          "description": "The thread identifier of the code that generated the notification.",
+          "type": "integer"
+        },
+        "timeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the analysis tool generated the notification.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "exception": {
+          "$ref": "#/definitions/exception",
+          "description": "The runtime exception, if any, relevant to this notification."
+        },
+        "descriptor": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the descriptor relevant to this notification."
+        },
+        "associatedRule": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the rule descriptor associated with this notification."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the notification."
+        }
+      },
+      "required": ["message"]
+    },
+    "physicalLocation": {
+      "description": "A physical location relevant to a result. Specifies a reference to a programming artifact together with a range of bytes or characters within that artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "address": {
+          "$ref": "#/definitions/address",
+          "description": "The address of the location."
+        },
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact."
+        },
+        "region": {
+          "$ref": "#/definitions/region",
+          "description": "Specifies a portion of the artifact."
+        },
+        "contextRegion": {
+          "$ref": "#/definitions/region",
+          "description": "Specifies a portion of the artifact that encloses the region. Allows a viewer to display additional context around the region."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the physical location."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["address"]
+        },
+        {
+          "required": ["artifactLocation"]
+        }
+      ]
+    },
+    "propertyBag": {
+      "description": "Key/value pairs that provide additional information about the object.",
+      "type": "object",
+      "additionalProperties": true,
+      "properties": {
+        "tags": {
+          "description": "A set of distinct strings that provide additional information.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        }
+      }
+    },
+    "rectangle": {
+      "description": "An area within an image.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "top": {
+          "description": "The Y coordinate of the top edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "left": {
+          "description": "The X coordinate of the left edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "bottom": {
+          "description": "The Y coordinate of the bottom edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "right": {
+          "description": "The X coordinate of the right edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the rectangle."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the rectangle."
+        }
+      }
+    },
+    "region": {
+      "description": "A region within an artifact where a result was detected.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "startLine": {
+          "description": "The line number of the first character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "startColumn": {
+          "description": "The column number of the first character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "endLine": {
+          "description": "The line number of the last character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "endColumn": {
+          "description": "The column number of the character following the end of the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "charOffset": {
+          "description": "The zero-based offset from the beginning of the artifact of the first character in the region.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "charLength": {
+          "description": "The length of the region in characters.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "byteOffset": {
+          "description": "The zero-based offset from the beginning of the artifact of the first byte in the region.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "byteLength": {
+          "description": "The length of the region in bytes.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "snippet": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The portion of the artifact contents within the specified region."
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the region."
+        },
+        "sourceLanguage": {
+          "description": "Specifies the source language, if any, of the portion of the artifact specified by the region object.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the region."
+        }
+      }
+    },
+    "replacement": {
+      "description": "The replacement of a single region of an artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "deletedRegion": {
+          "$ref": "#/definitions/region",
+          "description": "The region of the artifact to delete."
+        },
+        "insertedContent": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The content to insert at the location specified by the 'deletedRegion' property."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the replacement."
+        }
+      },
+      "required": ["deletedRegion"]
+    },
+    "reportingDescriptor": {
+      "description": "Metadata that describes a specific report produced by the tool, as part of the analysis it provides or its runtime reporting.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "id": {
+          "description": "A stable, opaque identifier for the report.",
+          "type": "string"
+        },
+        "deprecatedIds": {
+          "description": "An array of stable, opaque identifiers by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "guid": {
+          "description": "A unique identifier for the reporting descriptor in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "deprecatedGuids": {
+          "description": "An array of unique identifies in the form of a GUID by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string",
+            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+          }
+        },
+        "name": {
+          "description": "A report identifier that is understandable to an end user.",
+          "type": "string"
+        },
+        "deprecatedNames": {
+          "description": "An array of readable identifiers by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A concise description of the report. Should be a single sentence that is understandable when visible space is limited to a single line of text."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A description of the report. Should, as far as possible, provide details sufficient to enable resolution of any problem indicated by the result."
+        },
+        "messageStrings": {
+          "description": "A set of name/value pairs with arbitrary names. Each value is a multiformatMessageString object, which holds message strings in plain text and (optionally) Markdown format. The strings can include placeholders, which can be used to construct a message in combination with an arbitrary number of additional string arguments.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "defaultConfiguration": {
+          "$ref": "#/definitions/reportingConfiguration",
+          "description": "Default reporting configuration information."
+        },
+        "helpUri": {
+          "description": "A URI where the primary documentation for the report can be found.",
+          "type": "string",
+          "format": "uri"
+        },
+        "help": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "Provides the primary documentation for the report, useful when there is no online documentation."
+        },
+        "relationships": {
+          "description": "An array of objects that describe relationships between this reporting descriptor and others.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorRelationship"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the report."
+        }
+      },
+      "required": ["id"]
+    },
+    "reportingConfiguration": {
+      "description": "Information about a rule or notification that can be configured at runtime.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "enabled": {
+          "description": "Specifies whether the report may be produced during the scan.",
+          "type": "boolean",
+          "default": true
+        },
+        "level": {
+          "description": "Specifies the failure level for the report.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "rank": {
+          "description": "Specifies the relative priority of the report. Used for analysis output only.",
+          "type": "number",
+          "default": -1,
+          "minimum": -1,
+          "maximum": 100
+        },
+        "parameters": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Contains configuration information specific to a report."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting configuration."
+        }
+      }
+    },
+    "reportingDescriptorReference": {
+      "description": "Information about how to locate a relevant reporting descriptor.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "The id of the descriptor.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index into an array of descriptors in toolComponent.ruleDescriptors, toolComponent.notificationDescriptors, or toolComponent.taxonomyDescriptors, depending on context.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "guid": {
+          "description": "A guid that uniquely identifies the descriptor.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "toolComponent": {
+          "$ref": "#/definitions/toolComponentReference",
+          "description": "A reference used to locate the toolComponent associated with the descriptor."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting descriptor reference."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["index"]
+        },
+        {
+          "required": ["guid"]
+        },
+        {
+          "required": ["id"]
+        }
+      ]
+    },
+    "reportingDescriptorRelationship": {
+      "description": "Information about the relation of one reporting descriptor to another.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "target": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference to the related reporting descriptor."
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the relationship. Well-known kinds include 'canPrecede', 'canFollow', 'willPrecede', 'willFollow', 'superset', 'subset', 'equal', 'disjoint', 'relevant', and 'incomparable'.",
+          "type": "array",
+          "default": ["relevant"],
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the reporting descriptor relationship."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting descriptor reference."
+        }
+      },
+      "required": ["target"]
+    },
+    "result": {
+      "description": "A result produced by an analysis tool.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "ruleId": {
+          "description": "The stable, unique identifier of the rule, if any, to which this result is relevant.",
+          "type": "string"
+        },
+        "ruleIndex": {
+          "description": "The index within the tool component rules array of the rule object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "rule": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the rule descriptor relevant to this result."
+        },
+        "kind": {
+          "description": "A value that categorizes results by evaluation state.",
+          "default": "fail",
+          "enum": [
+            "notApplicable",
+            "pass",
+            "fail",
+            "review",
+            "open",
+            "informational"
+          ]
+        },
+        "level": {
+          "description": "A value specifying the severity level of the result.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the result. The first sentence of the message only will be displayed when visible space is limited."
+        },
+        "analysisTarget": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "Identifies the artifact that the analysis tool was instructed to scan. This need not be the same as the artifact where the result actually occurred."
+        },
+        "locations": {
+          "description": "The set of locations where the result was detected. Specify only one location unless the problem indicated by the result can only be corrected by making a change at every specified location.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "guid": {
+          "description": "A stable, unique identifier for the result in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "correlationGuid": {
+          "description": "A stable, unique identifier for the equivalence class of logically identical results to which this result belongs, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "occurrenceCount": {
+          "description": "A positive integer specifying the number of times this logically unique result was observed in this run.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "partialFingerprints": {
+          "description": "A set of strings that contribute to the stable, unique identity of the result.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "fingerprints": {
+          "description": "A set of strings each of which individually defines a stable, unique identity for the result.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "stacks": {
+          "description": "An array of 'stack' objects relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/stack"
+          }
+        },
+        "codeFlows": {
+          "description": "An array of 'codeFlow' objects relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/codeFlow"
+          }
+        },
+        "graphs": {
+          "description": "An array of zero or more unique graph objects associated with the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "graphTraversals": {
+          "description": "An array of one or more unique 'graphTraversal' objects.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graphTraversal"
+          }
+        },
+        "relatedLocations": {
+          "description": "A set of locations relevant to this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "suppressions": {
+          "description": "A set of suppressions relevant to this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/suppression"
+          }
+        },
+        "baselineState": {
+          "description": "The state of a result relative to a baseline of a previous run.",
+          "enum": ["new", "unchanged", "updated", "absent"]
+        },
+        "rank": {
+          "description": "A number representing the priority or importance of the result.",
+          "type": "number",
+          "default": -1,
+          "minimum": -1,
+          "maximum": 100
+        },
+        "attachments": {
+          "description": "A set of artifacts relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/attachment"
+          }
+        },
+        "hostedViewerUri": {
+          "description": "An absolute URI at which the result can be viewed.",
+          "type": "string",
+          "format": "uri"
+        },
+        "workItemUris": {
+          "description": "The URIs of the work items associated with this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string",
+            "format": "uri"
+          }
+        },
+        "provenance": {
+          "$ref": "#/definitions/resultProvenance",
+          "description": "Information about how and when the result was detected."
+        },
+        "fixes": {
+          "description": "An array of 'fix' objects, each of which represents a proposed fix to the problem indicated by the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/fix"
+          }
+        },
+        "taxa": {
+          "description": "An array of references to taxonomy reporting descriptors that are applicable to the result.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorReference"
+          }
+        },
+        "webRequest": {
+          "$ref": "#/definitions/webRequest",
+          "description": "A web request associated with this result."
+        },
+        "webResponse": {
+          "$ref": "#/definitions/webResponse",
+          "description": "A web response associated with this result."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the result."
+        }
+      },
+      "required": ["message"]
+    },
+    "resultProvenance": {
+      "description": "Contains information about how and when a result was detected.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "firstDetectionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the result was first detected. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "lastDetectionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the result was most recently detected. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "firstDetectionRunGuid": {
+          "description": "A GUID-valued string equal to the automationDetails.guid property of the run in which the result was first detected.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "lastDetectionRunGuid": {
+          "description": "A GUID-valued string equal to the automationDetails.guid property of the run in which the result was most recently detected.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "invocationIndex": {
+          "description": "The index within the run.invocations array of the invocation object which describes the tool invocation that detected the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "conversionSources": {
+          "description": "An array of physicalLocation objects which specify the portions of an analysis tool's output that a converter transformed into the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/physicalLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the result."
+        }
+      }
+    },
+    "run": {
+      "description": "Describes a single run of an analysis tool, and contains the reported output of that run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "tool": {
+          "$ref": "#/definitions/tool",
+          "description": "Information about the tool or tool pipeline that generated the results in this run. A run can only contain results produced by a single tool or tool pipeline. A run can aggregate results from multiple log files, as long as context around the tool run (tool command-line arguments and the like) is identical for all aggregated files."
+        },
+        "invocations": {
+          "description": "Describes the invocation of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/invocation"
+          }
+        },
+        "conversion": {
+          "$ref": "#/definitions/conversion",
+          "description": "A conversion object that describes how a converter transformed an analysis tool's native reporting format into the SARIF format."
+        },
+        "language": {
+          "description": "The language of the messages emitted into the log file during this run (expressed as an ISO 639-1 two-letter lowercase culture code) and an optional region (expressed as an ISO 3166-1 two-letter uppercase subculture code associated with a country or region). The casing is recommended but not required (in order for this data to conform to RFC5646).",
+          "type": "string",
+          "default": "en-US",
+          "pattern": "^[a-zA-Z]{2}|^[a-zA-Z]{2}-[a-zA-Z]{2}?$"
+        },
+        "versionControlProvenance": {
+          "description": "Specifies the revision in version control of the artifacts that were scanned.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/versionControlDetails"
+          }
+        },
+        "originalUriBaseIds": {
+          "description": "The artifact location specified by each uriBaseId symbol on the machine where the tool originally ran.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "artifacts": {
+          "description": "An array of artifact objects relevant to the run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifact"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of logical locations such as namespaces, types or functions.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "graphs": {
+          "description": "An array of zero or more unique graph objects associated with the run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "results": {
+          "description": "The set of results contained in an SARIF log. The results array can be omitted when a run is solely exporting rules metadata. It must be present (but may be empty) if a log file represents an actual scan.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/result"
+          }
+        },
+        "automationDetails": {
+          "$ref": "#/definitions/runAutomationDetails",
+          "description": "Automation details that describe this run."
+        },
+        "runAggregates": {
+          "description": "Automation details that describe the aggregate of runs to which this run belongs.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/runAutomationDetails"
+          }
+        },
+        "baselineGuid": {
+          "description": "The 'guid' property of a previous SARIF 'run' that comprises the baseline that was used to compute result 'baselineState' properties for the run.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "redactionTokens": {
+          "description": "An array of strings used to replace sensitive information in a redaction-aware property.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "defaultEncoding": {
+          "description": "Specifies the default encoding for any artifact object that refers to a text file.",
+          "type": "string"
+        },
+        "defaultSourceLanguage": {
+          "description": "Specifies the default source language for any artifact object that refers to a text file that contains source code.",
+          "type": "string"
+        },
+        "newlineSequences": {
+          "description": "An ordered list of character sequences that were treated as line breaks when computing region information for the run.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": true,
+          "default": ["\r\n", "\n"],
+          "items": {
+            "type": "string"
+          }
+        },
+        "columnKind": {
+          "description": "Specifies the unit in which the tool measures columns.",
+          "enum": ["utf16CodeUnits", "unicodeCodePoints"]
+        },
+        "externalPropertyFileReferences": {
+          "$ref": "#/definitions/externalPropertyFileReferences",
+          "description": "References to external property files that should be inlined with the content of a root log file."
+        },
+        "threadFlowLocations": {
+          "description": "An array of threadFlowLocation objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "taxonomies": {
+          "description": "An array of toolComponent objects relevant to a taxonomy in which results are categorized.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "addresses": {
+          "description": "Addresses associated with this run instance, if any.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/address"
+          }
+        },
+        "translations": {
+          "description": "The set of available translations of the localized data provided by the tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "policies": {
+          "description": "Contains configurations that may potentially override both reportingDescriptor.defaultConfiguration (the tool's default severities) and invocation.configurationOverrides (severities established at run-time from the command line).",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "webRequests": {
+          "description": "An array of request objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webRequest"
+          }
+        },
+        "webResponses": {
+          "description": "An array of response objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webResponse"
+          }
+        },
+        "specialLocations": {
+          "$ref": "#/definitions/specialLocations",
+          "description": "A specialLocations object that defines locations of special significance to SARIF consumers."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the run."
+        }
+      },
+      "required": ["tool"]
+    },
+    "runAutomationDetails": {
+      "description": "Information that describes a run's identity and role within an engineering system process.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the identity and role played within the engineering system by this object's containing run object."
+        },
+        "id": {
+          "description": "A hierarchical string that uniquely identifies this object's containing run object.",
+          "type": "string"
+        },
+        "guid": {
+          "description": "A stable, unique identifier for this object's containing run object in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "correlationGuid": {
+          "description": "A stable, unique identifier for the equivalence class of runs to which this object's containing run object belongs in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the run automation details."
+        }
+      }
+    },
+    "specialLocations": {
+      "description": "Defines locations of special significance to SARIF consumers.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "displayBase": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "Provides a suggestion to SARIF consumers to display file paths relative to the specified location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the special locations."
+        }
+      }
+    },
+    "stack": {
+      "description": "A call stack that is relevant to a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to this call stack."
+        },
+        "frames": {
+          "description": "An array of stack frames that represents a sequence of calls, rendered in reverse chronological order, that comprise the call stack.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/stackFrame"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the stack."
+        }
+      },
+      "required": ["frames"]
+    },
+    "stackFrame": {
+      "description": "A function call within a stack trace.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "The location to which this stack frame refers."
+        },
+        "module": {
+          "description": "The name of the module that contains the code of this stack frame.",
+          "type": "string"
+        },
+        "threadId": {
+          "description": "The thread identifier of the stack frame.",
+          "type": "integer"
+        },
+        "parameters": {
+          "description": "The parameters of the call that is executing.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "type": "string",
+            "default": []
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the stack frame."
+        }
+      }
+    },
+    "suppression": {
+      "description": "A suppression that is relevant to a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "guid": {
+          "description": "A stable, unique identifier for the suppression in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "kind": {
+          "description": "A string that indicates where the suppression is persisted.",
+          "enum": ["inSource", "external"]
+        },
+        "status": {
+          "description": "A string that indicates the review status of the suppression.",
+          "enum": ["accepted", "underReview", "rejected"]
+        },
+        "justification": {
+          "description": "A string representing the justification for the suppression.",
+          "type": "string"
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "Identifies the location associated with the suppression."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the suppression."
+        }
+      },
+      "required": ["kind"]
+    },
+    "threadFlow": {
+      "description": "Describes a sequence of code locations that specify a path through a single thread of execution such as an operating system or fiber.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "An string that uniquely identifies the threadFlow within the codeFlow in which it occurs.",
+          "type": "string"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the thread flow."
+        },
+        "initialState": {
+          "description": "Values of relevant expressions at the start of the thread flow that may change during thread flow execution.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "immutableState": {
+          "description": "Values of relevant expressions at the start of the thread flow that remain constant.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "locations": {
+          "description": "A temporally ordered array of 'threadFlowLocation' objects, each of which describes a location visited by the tool while producing the result.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the thread flow."
+        }
+      },
+      "required": ["locations"]
+    },
+    "threadFlowLocation": {
+      "description": "A location visited by an analysis tool while simulating or monitoring the execution of a program.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "index": {
+          "description": "The index within the run threadFlowLocations array.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "The code location."
+        },
+        "stack": {
+          "$ref": "#/definitions/stack",
+          "description": "The call stack leading to this location."
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the thread flow location. Well-known kinds include 'acquire', 'release', 'enter', 'exit', 'call', 'return', 'branch', 'implicit', 'false', 'true', 'caution', 'danger', 'unknown', 'unreachable', 'taint', 'function', 'handler', 'lock', 'memory', 'resource', 'scope' and 'value'.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "taxa": {
+          "description": "An array of references to rule or taxonomy reporting descriptors that are applicable to the thread flow location.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorReference"
+          }
+        },
+        "module": {
+          "description": "The name of the module that contains the code that is executing.",
+          "type": "string"
+        },
+        "state": {
+          "description": "A dictionary, each of whose keys specifies a variable or expression, the associated value of which represents the variable or expression value. For an annotation of kind 'continuation', for example, this dictionary might hold the current assumed values of a set of global variables.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "nestingLevel": {
+          "description": "An integer representing a containment hierarchy within the thread flow.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "executionOrder": {
+          "description": "An integer representing the temporal order in which execution reached this location.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "executionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which this location was executed.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "importance": {
+          "description": "Specifies the importance of this location in understanding the code flow in which it occurs. The order from most to least important is \"essential\", \"important\", \"unimportant\". Default: \"important\".",
+          "enum": ["important", "essential", "unimportant"],
+          "default": "important"
+        },
+        "webRequest": {
+          "$ref": "#/definitions/webRequest",
+          "description": "A web request associated with this thread flow location."
+        },
+        "webResponse": {
+          "$ref": "#/definitions/webResponse",
+          "description": "A web response associated with this thread flow location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the threadflow location."
+        }
+      }
+    },
+    "tool": {
+      "description": "The analysis tool that was run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "driver": {
+          "$ref": "#/definitions/toolComponent",
+          "description": "The analysis tool that was run."
+        },
+        "extensions": {
+          "description": "Tool extensions that contributed to or reconfigured the analysis tool that was run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the tool."
+        }
+      },
+      "required": ["driver"]
+    },
+    "toolComponent": {
+      "description": "A component, such as a plug-in or the driver, of the analysis tool that was run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "guid": {
+          "description": "A unique identifier for the tool component in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "name": {
+          "description": "The name of the tool component.",
+          "type": "string"
+        },
+        "organization": {
+          "description": "The organization or company that produced the tool component.",
+          "type": "string"
+        },
+        "product": {
+          "description": "A product suite to which the tool component belongs.",
+          "type": "string"
+        },
+        "productSuite": {
+          "description": "A localizable string containing the name of the suite of products to which the tool component belongs.",
+          "type": "string"
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A brief description of the tool component."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A comprehensive description of the tool component."
+        },
+        "fullName": {
+          "description": "The name of the tool component along with its version and any other useful identifying information, such as its locale.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The tool component version, in whatever format the component natively provides.",
+          "type": "string"
+        },
+        "semanticVersion": {
+          "description": "The tool component version in the format specified by Semantic Versioning 2.0.",
+          "type": "string"
+        },
+        "dottedQuadFileVersion": {
+          "description": "The binary version of the tool component's primary executable file expressed as four non-negative integers separated by a period (for operating systems that express file versions in this way).",
+          "type": "string",
+          "pattern": "[0-9]+(\\.[0-9]+){3}"
+        },
+        "releaseDateUtc": {
+          "description": "A string specifying the UTC date (and optionally, the time) of the component's release.",
+          "type": "string"
+        },
+        "downloadUri": {
+          "description": "The absolute URI from which the tool component can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "informationUri": {
+          "description": "The absolute URI at which information about this version of the tool component can be found.",
+          "type": "string",
+          "format": "uri"
+        },
+        "globalMessageStrings": {
+          "description": "A dictionary, each of whose keys is a resource identifier and each of whose values is a multiformatMessageString object, which holds message strings in plain text and (optionally) Markdown format. The strings can include placeholders, which can be used to construct a message in combination with an arbitrary number of additional string arguments.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "notifications": {
+          "description": "An array of reportingDescriptor objects relevant to the notifications related to the configuration and runtime execution of the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "rules": {
+          "description": "An array of reportingDescriptor objects relevant to the analysis performed by the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "taxa": {
+          "description": "An array of reportingDescriptor objects relevant to the definitions of both standalone and tool-defined taxonomies.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "locations": {
+          "description": "An array of the artifactLocation objects associated with the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "language": {
+          "description": "The language of the messages emitted into the log file during this run (expressed as an ISO 639-1 two-letter lowercase language code) and an optional region (expressed as an ISO 3166-1 two-letter uppercase subculture code associated with a country or region). The casing is recommended but not required (in order for this data to conform to RFC5646).",
+          "type": "string",
+          "default": "en-US",
+          "pattern": "^[a-zA-Z]{2}|^[a-zA-Z]{2}-[a-zA-Z]{2}?$"
+        },
+        "contents": {
+          "description": "The kinds of data contained in this object.",
+          "type": "array",
+          "uniqueItems": true,
+          "default": ["localizedData", "nonLocalizedData"],
+          "items": {
+            "enum": ["localizedData", "nonLocalizedData"]
+          }
+        },
+        "isComprehensive": {
+          "description": "Specifies whether this object contains a complete definition of the localizable and/or non-localizable data for this component, as opposed to including only data that is relevant to the results persisted to this log file.",
+          "type": "boolean",
+          "default": false
+        },
+        "localizedDataSemanticVersion": {
+          "description": "The semantic version of the localized strings defined in this component; maintained by components that provide translations.",
+          "type": "string"
+        },
+        "minimumRequiredLocalizedDataSemanticVersion": {
+          "description": "The minimum value of localizedDataSemanticVersion required in translations consumed by this component; used by components that consume translations.",
+          "type": "string"
+        },
+        "associatedComponent": {
+          "$ref": "#/definitions/toolComponentReference",
+          "description": "The component which is strongly associated with this component. For a translation, this refers to the component which has been translated. For an extension, this is the driver that provides the extension's plugin model."
+        },
+        "translationMetadata": {
+          "$ref": "#/definitions/translationMetadata",
+          "description": "Translation metadata, required for a translation, not populated by other component types."
+        },
+        "supportedTaxonomies": {
+          "description": "An array of toolComponentReference objects to declare the taxonomies supported by the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponentReference"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the tool component."
+        }
+      },
+      "required": ["name"]
+    },
+    "toolComponentReference": {
+      "description": "Identifies a particular toolComponent object, either the driver or an extension.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "name": {
+          "description": "The 'name' property of the referenced toolComponent.",
+          "type": "string"
+        },
+        "index": {
+          "description": "An index into the referenced toolComponent in tool.extensions.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "guid": {
+          "description": "The 'guid' property of the referenced toolComponent.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the toolComponentReference."
+        }
+      }
+    },
+    "translationMetadata": {
+      "description": "Provides additional metadata related to translation.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "name": {
+          "description": "The name associated with the translation metadata.",
+          "type": "string"
+        },
+        "fullName": {
+          "description": "The full name associated with the translation metadata.",
+          "type": "string"
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A brief description of the translation metadata."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A comprehensive description of the translation metadata."
+        },
+        "downloadUri": {
+          "description": "The absolute URI from which the translation metadata can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "informationUri": {
+          "description": "The absolute URI from which information related to the translation metadata can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the translation metadata."
+        }
+      },
+      "required": ["name"]
+    },
+    "versionControlDetails": {
+      "description": "Specifies the information necessary to retrieve a desired revision from a version control system.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "repositoryUri": {
+          "description": "The absolute URI of the repository.",
+          "type": "string",
+          "format": "uri"
+        },
+        "revisionId": {
+          "description": "A string that uniquely and permanently identifies the revision within the repository.",
+          "type": "string"
+        },
+        "branch": {
+          "description": "The name of a branch containing the revision.",
+          "type": "string"
+        },
+        "revisionTag": {
+          "description": "A tag that has been applied to the revision.",
+          "type": "string"
+        },
+        "asOfTimeUtc": {
+          "description": "A Coordinated Universal Time (UTC) date and time that can be used to synchronize an enlistment to the state of the repository at that time.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "mappedTo": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location in the local file system to which the root of the repository was mapped at the time of the analysis."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the version control details."
+        }
+      },
+      "required": ["repositoryUri"]
+    },
+    "webRequest": {
+      "description": "Describes an HTTP request.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "index": {
+          "description": "The index within the run.webRequests array of the request object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "protocol": {
+          "description": "The request protocol. Example: 'http'.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The request version. Example: '1.1'.",
+          "type": "string"
+        },
+        "target": {
+          "description": "The target of the request.",
+          "type": "string"
+        },
+        "method": {
+          "description": "The HTTP method. Well-known values are 'GET', 'PUT', 'POST', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'.",
+          "type": "string"
+        },
+        "headers": {
+          "description": "The request headers.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "parameters": {
+          "description": "The request parameters.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "body": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The body of the request."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the request."
+        }
+      }
+    },
+    "webResponse": {
+      "description": "Describes the response to an HTTP request.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "index": {
+          "description": "The index within the run.webResponses array of the response object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "protocol": {
+          "description": "The response protocol. Example: 'http'.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The response version. Example: '1.1'.",
+          "type": "string"
+        },
+        "statusCode": {
+          "description": "The response status code. Example: 451.",
+          "type": "integer"
+        },
+        "reasonPhrase": {
+          "description": "The response reason. Example: 'Not found'.",
+          "type": "string"
+        },
+        "headers": {
+          "description": "The response headers.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "body": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The body of the response."
+        },
+        "noResponseReceived": {
+          "description": "Specifies whether a response was received from the server.",
+          "type": "boolean",
+          "default": false
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the response."
+        }
+      }
+    }
+  },
+  "description": "Static Analysis Results Format (SARIF) Version 2.1.0 JSON Schema: a standard format for the output of static analysis tools.",
+  "properties": {
+    "$schema": {
+      "description": "The URI of the JSON schema corresponding to the version.",
+      "type": "string",
+      "format": "uri"
+    },
+    "version": {
+      "description": "The SARIF format version of this log file.",
+      "enum": ["2.1.0"]
+    },
+    "runs": {
+      "description": "The set of runs contained in this log file.",
+      "type": "array",
+      "minItems": 0,
+      "uniqueItems": false,
+      "items": {
+        "$ref": "#/definitions/run"
+      }
+    },
+    "inlineExternalProperties": {
+      "description": "References to external property files that share data between runs.",
+      "type": "array",
+      "minItems": 0,
+      "uniqueItems": true,
+      "items": {
+        "$ref": "#/definitions/externalProperties"
+      }
+    },
+    "properties": {
+      "$ref": "#/definitions/propertyBag",
+      "description": "Key/value pairs that provide additional information about the log file."
+    }
+  },
+  "required": ["version", "runs"],
+  "title": "Static Analysis Results Format (SARIF) Version 2.1.0 JSON Schema",
+  "type": "object"
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/schemas/vendor/sarif-2.1.0/VENDORED.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/schemas/vendor/sarif-2.1.0/VENDORED.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/schemas/vendor/sarif-2.1.0/VENDORED.md	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/schemas/vendor/sarif-2.1.0/VENDORED.md	2026-08-26 17:24:44.595826188 -0300
@@ -0,0 +1,34 @@
+# Vendored: SARIF 2.1.0 JSON Schema
+
+- **Asset:** `sarif-schema.json`
+- **Upstream URL:** https://json.schemastore.org/sarif-2.1.0.json
+- **Canonical source ($id):** https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json
+- **Version:** SARIF 2.1.0 (OASIS Standard; the schema declares `$schema: http://json-schema.org/draft-07/schema#`)
+- **License:** MIT — the OASIS SARIF schema is distributed under the MIT License
+  (see the [sarif-spec repository](https://github.com/oasis-tcs/sarif-spec) and
+  [schemastore](https://www.schemastore.org/)).
+
+  Permission is hereby granted, free of charge, to any person obtaining a copy
+  of this software and associated documentation files (the "Software"), to deal
+  in the Software without restriction, including without limitation the rights
+  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+  copies of the Software, and to permit persons to whom the Software is
+  furnished to do so, subject to the following conditions:
+
+  The above copyright notice and this permission notice shall be included in
+  all copies or substantial portions of the Software.
+
+  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+  SOFTWARE.
+
+- **Retrieval date:** 2026-08-26
+- **SHA-256** (`sarif-schema.json`):
+  `7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a`
+
+The checksum is verified by `tests/test_export_sarif.py` so an offline build
+cannot drift from the reviewed vendor copy.
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/cli.py	2026-08-26 15:52:20.763606152 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/cli.py	2026-08-26 17:25:38.963645186 -0300
@@ -9,21 +9,21 @@
 from pathlib import Path
 from typing import TextIO
 
 from . import diff as diff_module
 from . import impact as impact_module
 from .analysis import analyze_project
 from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
-from .exporters import csv_export
+from .exporters import csv_export, sarif_export
 from .metrics import render_measure
 from .queries import materialize_queries
 from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
     """Raised when `.quarto-needs.toml` cannot be used."""
 
 
@@ -364,44 +364,54 @@
     effective = config if config is not None else load_config(root)
     if args.baseline is not None and args.format != "markdown":
         # Usage errors are reported before any analysis runs.
         print(
             "usage error: --baseline is only valid with --format markdown "
             f"(got --format {args.format})",
             file=sys.stderr,
         )
         return 2
     result = analyze_project(root, config=effective)
-    if result.snapshot is None:
+    # SARIF is findings-driven: it exports even when a structural failure
+    # left the snapshot None; json/csv still require the snapshot itself.
+    if result.snapshot is None and args.format != "sarif":
         print_findings(result.findings, stream=sys.stderr)
         return 1
     output = root / args.output
     try:
         if args.format == "json":
             # Byte-identity with the pre-task v1 projection holds by
             # construction: the default format keeps the existing writer.
             write_v1_graph(output, result.snapshot)
         elif args.format == "csv":
             # The csv format's --output names a directory (created on
             # demand) receiving objects/relations/findings.csv, each
             # written atomically through export._write_atomic_text.
             csv_export.write_all(output, result.snapshot)
+        elif args.format == "sarif":
+            # Single-file findings export written atomically; a structurally
+            # invalid project still produces its artifact, then fails policy.
+            sarif_export.write(output, result.findings)
         else:
-            # TODO(milestone-4a-writers): Tasks 4-6 replace this raise with
-            # the sarif/junit/markdown writers, each routing its writes
-            # through _write_atomic_text like the branches above.
+            # TODO(milestone-4a-writers): Tasks 5-6 replace this raise with
+            # the junit/markdown writers, each routing its writes through
+            # _write_atomic_text like the branches above.
             raise NotImplementedError(
                 f"--format {args.format} writer lands with the milestone-4a exporter tasks"
             )
     except OSError as error:
         print(f"Could not write {output}: {error}", file=sys.stderr)
         return 3
+    if result.snapshot is None:
+        # The SARIF artifact is on disk; the structural findings still fail.
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
     # The artifact is on disk before the policy verdict leaves the process.
     report = report_from_snapshot(result.snapshot, effective)
     return profile_exit_code(effective.profile, False, report.gate_failures())
 
 
 def main(argv: list[str] | None = None) -> int:
     parser = argparse.ArgumentParser(prog="quarto-needs", description="Requirements-as-code engine for Quarto")
     parser.add_argument("--root", help="Project root (default: current directory)")
     sub = parser.add_subparsers(dest="command", required=True)
     sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/diff.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/diff.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/diff.py	2026-08-26 10:09:28.715101693 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/diff.py	2026-08-26 17:29:52.306841236 -0300
@@ -1,55 +1,69 @@
 """Classified comparison between a baseline and the current snapshot.
 
 Two guards run before any comparison. A changed configuration or a changed
 reference date means the derived numbers were produced under different rules,
 so reporting their deltas as project changes would be a lie; the diff says so
-and suppresses them instead.
+and suppresses them instead. It says so under `--recompute-with current` too:
+recomputation re-resolves authored relations but cannot re-derive stored
+findings, metrics, or gates, so the suppression is just as real there. The
+suppressed categories are named in `suppressed`, so `empty` is never readable
+as "every category was compared and matched".
 """
 from __future__ import annotations
 
 from dataclasses import dataclass
 from typing import Mapping, Sequence
 
 from . import fingerprints
 from .config import NeedsConfig
 from .quality import report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 SCHEMA_VERSION = "1"
 
 OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")
 
+# Categories whose deltas are derived from the baseline's stored results and
+# are therefore not compared at all when either guard fires.
+SUPPRESSIBLE_CATEGORIES = ("findings", "metrics", "gates")
+
 
 class DiffError(Exception):
     """The two sides cannot be compared."""
 
 
 @dataclass(frozen=True, slots=True)
 class DiffReport:
     baseline_reference_date: str
     current_reference_date: str
     recomputed: bool
     notices: tuple[str, ...]
+    suppressed: tuple[str, ...]
     added_objects: tuple[str, ...]
     removed_objects: tuple[str, ...]
     modified: tuple[Mapping[str, object], ...]
     relocated: tuple[Mapping[str, object], ...]
     added_relations: tuple[Mapping[str, object], ...]
     removed_relations: tuple[Mapping[str, object], ...]
     representation_changes: tuple[Mapping[str, object], ...]
     findings_added: tuple[Mapping[str, object], ...]
     findings_removed: tuple[Mapping[str, object], ...]
     metric_deltas: tuple[Mapping[str, object], ...]
     gate_regressions: tuple[Mapping[str, object], ...]
 
     def is_empty(self) -> bool:
+        """True when every *compared* category matched.
+
+        Suppressed categories are not compared at all, so they cannot
+        contribute; `suppressed` names them and must be read alongside this.
+        """
         return not (
             self.added_objects
             or self.removed_objects
             or self.modified
             or self.relocated
             or self.added_relations
             or self.removed_relations
             or self.representation_changes
             or self.findings_added
             or self.findings_removed
@@ -59,20 +73,21 @@
 
     def to_dict(self) -> dict[str, object]:
         return {
             "schemaVersion": SCHEMA_VERSION,
             "referenceDate": {
                 "baseline": self.baseline_reference_date,
                 "current": self.current_reference_date,
             },
             "recomputed": self.recomputed,
             "notices": list(self.notices),
+            "suppressed": list(self.suppressed),
             "objects": {
                 "added": list(self.added_objects),
                 "removed": list(self.removed_objects),
                 "modified": [dict(item) for item in self.modified],
                 "relocated": [dict(item) for item in self.relocated],
             },
             "relations": {
                 "added": [dict(item) for item in self.added_relations],
                 "removed": [dict(item) for item in self.removed_relations],
                 "representationChanged": [dict(item) for item in self.representation_changes],
@@ -246,26 +261,29 @@
     for item in after.get("gates", []):
         name = str(item["name"])
         was = before_gates.get(name)
         if item.get("passed") is False and (was is None or was.get("passed") is not False):
             regressions.append(
                 {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
             )
     return tuple(regressions)
 
 
-def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
+def recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
     """Re-resolve stored relations through the *current* catalog.
 
     `--recompute-with current` must compare both sides under one policy, so the
     baseline's authored names are resolved again rather than trusting the
-    families and roles that were canonical when it was written.
+    families and roles that were canonical when it was written. The impact
+    direction is re-resolved with them: `impact` traverses this list, and a
+    stored direction from an older catalog would otherwise steer half the
+    traversal under the policy the flag exists to leave behind.
     """
     from .relations import DEFAULT_RELATION_CATALOG
     from .snapshot import RelationRecord
 
     recomputed: list[dict[str, object]] = []
     for item in stored:
         authored = str(item["authoredName"])
         try:
             kind = DEFAULT_RELATION_CATALOG.resolve(authored)
         except ValueError:
@@ -285,20 +303,21 @@
             impact_direction=kind.impact_direction,
             attributes=item.get("attributes") or {},
             provenance=(),
         )
         recomputed.append(
             {
                 "source": record.source,
                 "authoredName": record.authored_name,
                 "target": record.target,
                 "semanticFamily": record.semantic_family,
+                "impactDirection": record.impact_direction,
                 "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
                 "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
             }
         )
     return recomputed
 
 
 def compare(
     baseline_payload: Mapping[str, object],
     snapshot: AnalysisSnapshot,
@@ -309,72 +328,90 @@
     if not baseline_payload.get("valid", False):
         raise DiffError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
             "use `baseline inspect` to read it"
         )
 
     current_configuration = snapshot.configuration_fingerprint
     baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
     baseline_date = str(baseline_payload.get("referenceDate", ""))
 
-    notices: list[str] = []
     configuration_differs = baseline_configuration != current_configuration
     date_differs = baseline_date != snapshot.reference_date
-    if not recompute:
-        if configuration_differs:
-            notices.append("configuration-changed")
-        if date_differs:
-            notices.append("reference-date-changed")
-
-    added, removed, modified, relocated = _classify_objects(
-        _baseline_objects(baseline_payload),
-        {record.id: _current_object(record) for record in snapshot.objects},
-    )
-
-    baseline_relations = list(baseline_payload.get("relations", []))
-    if recompute:
-        baseline_relations = _recomputed_relations(baseline_relations)
-    # A catalog change can move families and roles, so semantic fingerprints
-    # from the two sides stop being comparable. Fall back to authored tuples,
-    # which is exactly what the spec prescribes for this case.
-    relation_key = (
-        "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
-    )
-    added_relations, removed_relations, representation = _classify_relations(
-        baseline_relations, _current_relations(snapshot), key=relation_key
-    )
+    # The notice is emitted in both modes: `--recompute-with current` clears
+    # the *relation* guard, not the derived one, and a silent suppression is
+    # indistinguishable from a clean comparison. `recomputed` tells the two
+    # cases apart for any consumer that needs to.
+    notices: list[str] = []
+    if configuration_differs:
+        notices.append("configuration-changed")
+    if date_differs:
+        notices.append("reference-date-changed")
+
+    try:
+        added, removed, modified, relocated = _classify_objects(
+            _baseline_objects(baseline_payload),
+            {record.id: _current_object(record) for record in snapshot.objects},
+        )
 
-    # Derived results are stored in the baseline, never re-derived, so they are
-    # comparable only when both sides were produced under the same rules and
-    # the same reference date. `recompute` re-resolves authored relations
-    # through the current catalog; it cannot make stored findings, metrics, or
-    # gates comparable, so their deltas stay suppressed silently there.
-    derived_suppressed = configuration_differs or date_differs
-    if derived_suppressed:
-        findings_added: tuple[dict[str, object], ...] = ()
-        findings_removed: tuple[dict[str, object], ...] = ()
-        metric_deltas: tuple[dict[str, object], ...] = ()
-        gate_regressions: tuple[dict[str, object], ...] = ()
-    else:
-        current_report = report_from_snapshot(snapshot, config).to_dict()
-        baseline_report = baseline_payload.get("report", {})
-        findings_added, findings_removed = _classify_findings(
-            baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+        baseline_relations = list(baseline_payload.get("relations", []))
+        if recompute:
+            baseline_relations = recomputed_relations(baseline_relations)
+        # A catalog change can move families and roles, so semantic fingerprints
+        # from the two sides stop being comparable. Fall back to authored tuples,
+        # which is exactly what the spec prescribes for this case. Recomputation
+        # re-resolves both sides through one catalog, so it restores semantic
+        # comparison; the key therefore tracks the guard, not the notice.
+        relation_key = (
+            "authoredFingerprint"
+            if configuration_differs and not recompute
+            else "semanticFingerprint"
+        )
+        added_relations, removed_relations, representation = _classify_relations(
+            baseline_relations, _current_relations(snapshot), key=relation_key
         )
-        metric_deltas = _classify_metrics(baseline_report, current_report)
-        gate_regressions = _classify_gates(baseline_report, current_report)
+
+        # Derived results are stored in the baseline, never re-derived, so they
+        # are comparable only when both sides were produced under the same rules
+        # and the same reference date. `recompute` re-resolves authored
+        # relations through the current catalog; it cannot make stored findings,
+        # metrics, or gates comparable, so their deltas stay suppressed there
+        # too — announced, not silently.
+        derived_suppressed = configuration_differs or date_differs
+        if derived_suppressed:
+            findings_added: tuple[dict[str, object], ...] = ()
+            findings_removed: tuple[dict[str, object], ...] = ()
+            metric_deltas: tuple[dict[str, object], ...] = ()
+            gate_regressions: tuple[dict[str, object], ...] = ()
+        else:
+            current_report = report_from_snapshot(snapshot, config).to_dict()
+            baseline_report = baseline_payload.get("report", {})
+            findings_added, findings_removed = _classify_findings(
+                baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+            )
+            metric_deltas = _classify_metrics(baseline_report, current_report)
+            gate_regressions = _classify_gates(baseline_report, current_report)
+    except KeyError as error:
+        # A tampered or truncated artifact can declare schemaVersion "1" and
+        # still omit a key every comparison needs; load_baseline does not
+        # schema-validate, so this is the last line of defense before a raw
+        # traceback reaches the CLI.
+        raise DiffError(
+            f"This baseline is missing required key {error}; it cannot be compared"
+        ) from error
 
     return DiffReport(
         baseline_reference_date=baseline_date,
         current_reference_date=snapshot.reference_date,
         recomputed=recompute,
         notices=tuple(notices),
+        suppressed=SUPPRESSIBLE_CATEGORIES if derived_suppressed else (),
         added_objects=added,
         removed_objects=removed,
         modified=modified,
         relocated=relocated,
         added_relations=added_relations,
         removed_relations=removed_relations,
         representation_changes=representation,
         findings_added=findings_added,
         findings_removed=findings_removed,
         metric_deltas=metric_deltas,
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/exporters/sarif_export.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/exporters/sarif_export.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/exporters/sarif_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/exporters/sarif_export.py	2026-08-26 17:25:22.923699645 -0300
@@ -0,0 +1,120 @@
+"""SARIF 2.1.0 exporter.
+
+SARIF consumes findings, not the snapshot: a structurally invalid project
+(no snapshot) still exports its findings, so `render_from_findings` is the
+load-bearing producer and `render`/`write` are conveniences around it.
+"""
+
+from __future__ import annotations
+
+import json
+from collections.abc import Sequence
+from pathlib import Path
+
+import quarto_needs
+
+from ..diagnostics import Finding
+from ..export import _write_atomic_text
+from ..rules import RULES
+from ..snapshot import AnalysisSnapshot
+
+# The $id of the vendored schema (schemas/vendor/sarif-2.1.0/sarif-schema.json).
+SCHEMA_URI = (
+    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
+    "master/Schemata/sarif-schema-2.1.0.json"
+)
+SARIF_VERSION = "2.1.0"
+TOOL_NAME = "quarto-needs"
+AUTOMATION_ID = "quarto-needs/export"
+
+# Finding severities map onto the SARIF level enum (none/note/warning/error).
+_LEVEL_BY_SEVERITY = {
+    "error": "error",
+    "warning": "warning",
+    "info": "note",
+}
+
+
+def _sort_key(finding: Finding) -> tuple[str, str, str]:
+    # Deterministic output: results ordered by code, object_id, message.
+    return (finding.code, finding.object_id or "", finding.message)
+
+
+def _rule_descriptor(code: str) -> dict[str, object]:
+    spec = RULES.get(code)
+    descriptor: dict[str, object] = {
+        "id": code,
+        # Fall back to the bare code when the finding is not in the registry.
+        "shortDescription": {"text": spec.title if spec is not None else code},
+    }
+    if spec is not None:
+        descriptor["fullDescription"] = {"text": spec.help}
+    return descriptor
+
+
+def _result(finding: Finding) -> dict[str, object]:
+    result: dict[str, object] = {
+        "ruleId": finding.code,
+        "level": _LEVEL_BY_SEVERITY.get(finding.severity, "note"),
+        "message": {"text": finding.message},
+        # The finding's existing stable identity hash, independent of
+        # severity overrides, serves as the primary-location line hash.
+        "fingerprints": {"primaryLocationLineHash": finding.fingerprint},
+    }
+    if finding.location is not None:
+        # location.file is already the project-relative POSIX path.
+        result["locations"] = [
+            {
+                "physicalLocation": {
+                    "artifactLocation": {"uri": finding.location.file},
+                    "region": {"startLine": finding.location.line},
+                }
+            }
+        ]
+    return result
+
+
+def build_payload(findings: Sequence[Finding]) -> dict[str, object]:
+    ordered = sorted(findings, key=_sort_key)
+    return {
+        "$schema": SCHEMA_URI,
+        "version": SARIF_VERSION,
+        "runs": [
+            {
+                "tool": {
+                    "driver": {
+                        "name": TOOL_NAME,
+                        "version": quarto_needs.__version__,
+                        "rules": [
+                            _rule_descriptor(code)
+                            for code in sorted({finding.code for finding in ordered})
+                        ],
+                    }
+                },
+                "automationDetails": {"id": AUTOMATION_ID},
+                "results": [_result(finding) for finding in ordered],
+            }
+        ],
+    }
+
+
+def render_from_findings(findings: Sequence[Finding]) -> str:
+    return (
+        json.dumps(
+            build_payload(findings),
+            ensure_ascii=False,
+            indent=2,
+            sort_keys=True,
+        )
+        + "\n"
+    )
+
+
+def render(snapshot: AnalysisSnapshot) -> str:
+    return render_from_findings(snapshot.findings)
+
+
+def write(path: Path, findings: Sequence[Finding]) -> Path:
+    destination = Path(path)
+    _write_atomic_text(destination, render_from_findings(findings))
+    return destination
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/impact.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/impact.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/src/quarto_needs/impact.py	2026-08-26 11:15:26.013708733 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/src/quarto_needs/impact.py	2026-08-26 17:30:13.366784835 -0300
@@ -34,35 +34,40 @@
             "impacted": [dict(item) for item in self.impacted],
         }
 
 
 def _union_edges(
     baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
 ) -> dict[str, list[tuple[str, str]]]:
     """Adjacency keyed by source, following each relation's impact direction.
 
     `both` yields an edge in each direction; `none` yields none at all.
+
+    `impactDirection` is read, never defaulted. Defaulting an absent key to
+    `none` deletes the edge from the union graph without saying so, which is
+    precisely the silence this traversal exists to avoid; the schema requires
+    the key and the caller turns its absence into an `ImpactError`.
     """
     adjacency: dict[str, list[tuple[str, str]]] = {}
 
     def add(source: str, target: str, name: str, direction: str) -> None:
         if direction in {"source_to_target", "both"}:
             adjacency.setdefault(source, []).append((target, name))
         if direction in {"target_to_source", "both"}:
             adjacency.setdefault(target, []).append((source, name))
 
     for item in baseline_relations:
         add(
             str(item["source"]),
             str(item["target"]),
             str(item["authoredName"]),
-            str(item.get("impactDirection", "none")),
+            str(item["impactDirection"]),
         )
     for record in snapshot.relations:
         add(record.source, record.target, record.authored_name, record.impact_direction)
 
     for key in adjacency:
         adjacency[key] = sorted(set(adjacency[key]))
     return adjacency
 
 
 def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
@@ -115,24 +120,42 @@
             raise ImpactError(
                 "The baseline was produced under a different configuration; "
                 "pass --recompute-with current so one relation policy governs the traversal"
             )
         if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
             raise ImpactError(
                 "The baseline was produced under a different reference date; "
                 "pass --recompute-with current to traverse under the current date"
             )
 
-    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
-    origins = _origins(report)
-    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
-    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    try:
+        report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
+    except diff_module.DiffError as error:
+        raise ImpactError(str(error)) from error
+
+    try:
+        origins = _origins(report)
+        stored_relations = list(baseline_payload.get("relations", []))
+        # An edge present only in the baseline is propagated with its stored
+        # direction otherwise, so a catalog whose impact direction moved would
+        # steer part of the traversal under the policy `--recompute-with
+        # current` exists to leave behind. Recomputing them here is what makes
+        # one relation policy govern the entire traversal.
+        adjacency = _union_edges(
+            diff_module.recomputed_relations(stored_relations) if recompute else stored_relations,
+            snapshot,
+        )
+        baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    except KeyError as error:
+        raise ImpactError(
+            f"This baseline is missing required key {error}; it cannot be traversed"
+        ) from error
     origin_ids = {str(item["id"]) for item in origins}
 
     impacted: dict[tuple[str, str], dict[str, object]] = {}
     for origin in origins:
         start = str(origin["id"])
         queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
         visited = {start}
         while queue:
             current, path, relations = queue.popleft()
             distance = len(path) - 1
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/tests/test_export_sarif.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/tests/test_export_sarif.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-before/tests/test_export_sarif.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-4-after/tests/test_export_sarif.py	2026-08-26 17:24:57.459783717 -0300
@@ -0,0 +1,77 @@
+from __future__ import annotations
+
+import hashlib
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft7Validator
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import sarif_export
+
+
+ROOT = Path(__file__).resolve().parents[1]
+SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"
+
+# Locked in schemas/vendor/sarif-2.1.0/VENDORED.md so an offline build cannot
+# drift from the reviewed vendor copy.
+VENDORED_SHA256 = "7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a"
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #DUP type=need status=draft}\n\n## A\nA.\n:::\n"
+        "\n::: {.need #DUP type=need status=draft}\n\n## B\nB.\n:::\n",
+        encoding="utf-8",
+    )
+
+
+def snapshot_with_findings(root: Path):
+    result = analyze_project(root, config=load_config(root))
+    return result.declarations and result.findings and result or None
+
+
+def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
+    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
+    Draft7Validator.check_schema(schema)
+
+    (tmp_path / "ok.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert result.snapshot is not None
+
+    payload = json.loads(sarif_export.render(result.snapshot))
+    Draft7Validator(schema).validate(payload)
+
+
+def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert any(f.code == "REQ004" for f in result.findings)
+
+    payload = json.loads(sarif_export.render_from_findings(result.findings))
+    result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")
+
+    assert result_entry["fingerprints"]["primaryLocationLineHash"]
+    assert result_entry["locations"][0]["physicalLocation"]["region"]["startLine"] > 0
+    assert payload["runs"][0]["tool"]["driver"]["rules"], "rule metadata must be present"
+
+
+def test_sarif_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert sarif_export.render_from_findings(result.findings) == sarif_export.render_from_findings(result.findings)
+
+
+def test_vendored_sarif_schema_checksum_is_locked() -> None:
+    """The vendored SARIF schema must match the SHA-256 recorded in VENDORED.md."""
+    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == VENDORED_SHA256
```
