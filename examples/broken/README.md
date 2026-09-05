# The broken gallery

Deliberately failing Quarto-Needs projects. Each directory is a real,
self-contained project whose defect teaches one specific failure mode —
what the engine says, how loudly it says it, and what the reader should do
about it. Nothing here is imported by, rendered into, or otherwise shared
with the canonical self-hosted model in `examples/quarto-needs/`.

Every expectation described below is executable: `tests/test_teaching_fixtures.py`
runs the engine against each fixture and fails if the engine's actual
diagnostics ever drift from this page. To explore by hand, run the same
command the tests use, for example:

```bash
quarto-needs --root examples/broken/missing-evidence check
```

## The fixtures

| Fixture | The mistake | What the engine does |
| --- | --- | --- |
| `missing-evidence/` | A passed test has no evidence behind it (REQ012 enabled). | Warning on `TC-001`; the project still scans and renders. |
| `invalid-relations/` | A relation targets an undeclared object (REQ005) and an identifier is declared twice (REQ004). | Two error findings; the snapshot is refused — nothing renders. |
| `relation-typo/` | A relation name is mistyped (`linked-to` instead of a catalog name). | No finding at all: the edge silently does not exist, and the typo survives as an inert attribute. The trap that makes `check` a CI requirement. |
| `orphan-requirements/` | Well-formed requirements connected to nothing (REQ014 enabled). | Info findings naming both objects; scanning succeeds. |
| `overdue-decision/` | An accepted decision's `revisit-after` date has passed (DEC006 enabled). | Warning on `ADR-001` naming the overdue review. |
| `expired-evidence/` | Evidence carrying an `expires` date in the past (REQ015 enabled). | Warning on `EVD-001`; freshness is re-checked, never assumed. |
| `localization-drift/` | The pt-BR sibling quietly changes a requirement's status. | The semantic-parity check refuses the pair by name (`REQ-001`) before publication. |
| `migration-loss/` | A Sphinx-Needs export with an unmapped type and an unmapped link field. | The import plan records `TYPE_UNMAPPED` and `LINK_FIELD_UNMAPPED` as review items — loss is planned, never guessed. |
| `interchange-loss/` | Treating the ReqIF/JSON-LD export as a lossless round trip. | The project scans clean, and both projections document inside the export exactly which authored details stay behind (source `file:line` provenance, and in ReqIF non-string cells) via `PROJECTION-NOTE` / `quartoNeedsProjectionNotes`. |
| `editor-refactor/` | Renaming `REQ-2` onto the existing `REQ-1` in an unsaved buffer. | The LSP rename refuses with `Cannot rename REQ-2 to existing object ID REQ-1`, surfacing the engine's canonical diagnostic instead of writing a `REQ004` duplicate; a rename onto a free identifier still edits every reference. |

One member of the gallery has no directory: **suspect-after-change** is two
states of a project across a Git history, not a single snapshot, so it is
built dynamically instead of forced into a checked-in directory.
`tests/test_teaching_fixtures.py::test_suspect_after_change_names_the_now_stale_verification`
builds it. To explore by hand:

```bash
mkdir /tmp/suspect-demo && cd /tmp/suspect-demo
git init -q
cat > index.qmd <<'QMD'
::: {.need #REQ-1 type="functional-requirement" status="approved" verified-by="TC-1"}
## Authenticate the user

The system shall authenticate the user with a password.
:::

::: {.need #TC-1 type="test-case" status="passed"}
## Login test

Verifies REQ-1.
:::
QMD
git add -A && git commit -q -m "base"
sed -i 's/with a password\./with a password and a second factor./' index.qmd
git add -A && git commit -q -m "REQ-1: require a second factor"
quarto-needs --root . suspect --git HEAD~1..HEAD
```

REQ-1 changed meaning; TC-1 never moved. `suspect` reports
`suspect TC-1 from REQ-1 d=1 via REQ-1 --verified-by--> TC-1` — a
verification that still points at REQ-1, but at a version of it nobody has
re-checked.

## What each fixture is teaching

**Errors block, warnings inform, info surfaces.** `invalid-relations/`
cannot produce a graph at all; `missing-evidence/` produces a graph plus a
warning; `orphan-requirements/` produces info-level visibility. Three
severities, three different relationships to publication.

**Silence is a failure mode too.** `relation-typo/` produces zero findings
and is the most dangerous fixture in the gallery: the author's intent is
lost without any diagnostic. Only catalog names parse as relations, so a
mistyped name becomes an inert attribute — visible in the inspector, dead
in the graph. The engine refuses to guess, but it also cannot read minds.

**Freshness is data, not belief.** `expired-evidence/` and
`overdue-decision/` both encode "this was true when written" — the engine
re-checks dates against the reference date instead of trusting the prose.

**Translation changes words, not meaning.** `localization-drift/` shows the
parity check refusing a sibling that altered engineering metadata; only
presentation text may differ across languages.

**Loss is explicit.** `migration-loss/` shows the migration contract's
central rule: content the mapping cannot express becomes a named review
item on the plan, never a silent drop and never a guessed conversion.

**The projection is not a round trip.** `interchange-loss/` scans clean and
exports clean — that is the trap. ReqIF and JSON-LD are read-only views, so
the loss that every export carries (the authored `file:line` provenance of
each object and relation, and in ReqIF the typed structure of attribute
cells) is documented *inside the export itself*: `PROJECTION-NOTE` entries
under `TOOL-EXTENSIONS` in ReqIF, and the `quartoNeedsProjectionNotes`
member in JSON-LD. A consumer can read exactly which authored details stayed
behind, which is what makes the loss explicit instead of accidental.

**The editor refuses to author the failure.** `editor-refactor/` shows a
rename in an unsaved buffer colliding with an existing ID. The LSP refuses
it with the engine's canonical message (`Cannot rename REQ-2 to existing
object ID REQ-1`) — the same diagnostic vocabulary as every other gate — so
a "merge by rename" can never become a `REQ004` duplicate on disk. Renaming
onto a free identifier still rewrites every declaration and reference.

**A relation can survive its own premise.** `suspect-after-change` shows
that `verified-by` staying structurally valid — TC-1 still names a real
object — says nothing about whether the verification is still true. Only a
second engineering state, compared explicitly, can surface that.

## Planned next slices

- RSP (ReSpec proposal-style) parsing and the remaining transformables from
  the migration gallery — tracked on `notes/ROADMAP.md` under Phase 9.
