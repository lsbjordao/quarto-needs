# Vacuous gates implementation plan

Goal: distinguish measured verdicts from empty or unavailable measurements without changing CoverageMeasure.percent.

Architecture: validate declared scopes and rule dependencies at configuration load; evaluate population gates with an explicit measurement status and an author-controlled empty-scope waiver. Preserve valid zero-finding counts after completed analysis. Publish the optional status in quality-v1, as approved, and render non-measurement distinctly.

- [ ] Add failing regression tests for each percentage strength, missing scope/coverage/findings, risk population, opt-in, and structural failure.
- [ ] Implement configuration validation, population checks and presentation in Python; retain REQ013 dependency validation.
- [ ] Add the quality schema and compatibility classification; verify existing consumers and serialization contracts.
- [ ] Document English and Portuguese behavior and model requirement, test case and evidence in the self-hosted example.
- [ ] Run make test, make check-self-example and make quality; record gate inventory and changed expectations in the PR description.
