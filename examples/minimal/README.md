# Minimal Quarto-Needs example

A deliberately small, non-self-hosted engineering project: a **payments
retry service** with one stakeholder need, four system requirements, one
architecture decision, two components, four test cases, and three evidence
records — fifteen objects total.

It exists to answer one question:

> Can a new user understand the core model without first understanding the
> Quarto-Needs codebase?

## The engineering story

1. **STK-001** — the business cannot lose paid orders to transient payment
   provider failures.
2. **REQ-001 … REQ-004** — four requirements derived from that need: retry
   transient faults, never double-charge, record outcomes, bound the backlog.
3. **ADR-001** — one accepted decision (idempotent retry client + bounded
   ledger) that *addresses* the driving requirements and *applies to* the
   two components that implement them.
4. **TC-001 … TC-004** — one passing test per requirement, each pointing at
   pipeline **evidence** (EVD-001 … EVD-003).

Every relation is declared in `index.qmd`; every table, matrix, flow, and
graph on the page is generated from those declarations at build time.

## Run it

From the repository root:

```bash
quarto-needs --root examples/minimal scan
quarto-needs --root examples/minimal check
quarto-needs --root examples/minimal trace STK-001
quarto render examples/minimal --to html
```

The render works with any Quarto satisfying `>= 1.6`; the pre-render hook
analyzes the project, syncs the extension, and writes
`.quarto-needs/needs.json` before Pandoc runs.
