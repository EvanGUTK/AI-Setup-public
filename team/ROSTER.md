# Personal team roster

Chief orchestrates; Validator independently gates; specialists start after plan approval. Every agent runs in its own tmux pane (`agent-team spawn`), and a team uses only agents of its own provider. All workers default to high effort and may use xhigh for difficult tasks.

## Chief — Orchestrator

Owns planning, delegation, scope, user interaction, and final local approval.

- `team-chief-project-plan` — Approved plan with ordered user-testable increments and unresolved decisions recorded.
- `team-chief-team-bootstrap` — Live Validator pane id and its acknowledgement from the inbox.
- `team-chief-ccpm-delivery` — PRD-to-issue traceability and ordered work queue.
- `team-chief-ownership-map` — Ownership table with collision handling.
- `team-chief-agent-selection` — Role hierarchy with capability justification and the spawn command for each agent.
- `team-chief-feature-mode` — Approved feature delta and migration strategy.
- `team-chief-progress-steering` — Increment handoff (changes, demo URL if any, plus how-to-test and stop steps) and the updated plan.
- `team-chief-push-approval` — Chief push approval tied to exact SHA.
- `team-chief-merge-handoff` — Reviewable PR and recorded merge authority.
- `team-chief-preference-learning` — Sanitized preference update and disclosed learning.

## Validator — Independent Gatekeeper

Independently verifies every agent’s code, tests, review evidence and integration before push or merge.

- `team-validator-acceptance-audit` — Criterion-to-evidence matrix.
- `team-validator-independent-diff` — Prioritized findings with path and reproduction.
- `team-validator-atomic-test-review` — Per-commit test evidence and gaps.
- `team-validator-coderabbit-gate` — Recorded review command, findings and dispositions.
- `team-validator-security-verification` — Concrete security findings or verified protections.
- `team-validator-performance-verification` — Reproducible comparison with limits.
- `team-validator-integration-verification` — Integration result tied to SHA.
- `team-validator-live-verification` — Observed runtime behavior and exact access details.
- `team-validator-sha-verdict` — Machine-readable verdict for current SHA.
- `team-validator-review-learning` — Evidence-backed review checklist update.

## Architect — System Designer

Designs module boundaries, contracts, repository structure, migrations and technical decisions.

- `team-architect-boundary-map` — System boundary map.
- `team-architect-repo-tree` — Annotated directory plan.
- `team-architect-api-contracts` — Implementable API contract.
- `team-architect-domain-model` — Domain model and invariants.
- `team-architect-architecture-decisions` — Architecture decision record.
- `team-architect-migration-design` — Migration and rollback design.
- `team-architect-dependency-design` — Dependency decision and constraints.
- `team-architect-failure-design` — Failure-mode contract.
- `team-architect-integration-plan` — Integration dependency graph.
- `team-architect-architecture-learning` — Scoped architecture memory.

## Product — Requirements & Experience

Owns PRDs, user journeys, feature scope, acceptance criteria and usability decisions.

- `team-product-prd-writing` — Reviewable PRD.
- `team-product-journey-mapping` — Journey map with edge cases.
- `team-product-acceptance-criteria` — Testable acceptance criteria.
- `team-product-scope-prioritization` — Prioritized scope list.
- `team-product-interaction-spec` — Interaction specification.
- `team-product-empty-error-copy` — State inventory and product copy.
- `team-product-feature-discovery` — Feature brief grounded in current behavior.
- `team-product-usability-review` — Usability findings and reproduction steps.
- `team-product-release-notes` — Accurate release notes.
- `team-product-product-learning` — Product preference memory.

## Backend — Services & APIs

Builds server routes, authorization, service logic, integrations, jobs and backend tests.

- `team-backend-route-implementation` — Route changes and contract tests.
- `team-backend-authorization` — Authorization implementation and denial tests.
- `team-backend-service-layer` — Focused service logic with invariant tests.
- `team-backend-external-integration` — Integration adapter and failure tests.
- `team-backend-background-jobs` — Job lifecycle implementation.
- `team-backend-idempotent-writes` — Repeat-safe write behavior.
- `team-backend-error-contract` — Error mapping and tests.
- `team-backend-backend-regression` — Fail-before/pass-after evidence.
- `team-backend-backend-observability` — Operational diagnostics and health evidence.
- `team-backend-backend-learning` — Backend pattern memory.

## Frontend — UI & Accessibility

Builds responsive interfaces, client state, forms, interaction polish and accessible flows.

- `team-frontend-component-design` — Components aligned with surrounding UI.
- `team-frontend-responsive-layout` — Responsive behavior evidence.
- `team-frontend-accessible-controls` — Accessible interaction implementation.
- `team-frontend-client-state` — Predictable state model and tests.
- `team-frontend-forms-validation` — Usable forms and validation tests.
- `team-frontend-network-states` — Verified network feedback states.
- `team-frontend-design-consistency` — Consistent visual implementation.
- `team-frontend-browser-verification` — Observed browser results.
- `team-frontend-frontend-regression` — Regression and live-flow evidence.
- `team-frontend-frontend-learning` — Scoped UI preference memory.

## Engine — Core Logic & Performance

Builds algorithms, parsers, state machines, simulations, scheduling and performance-sensitive core logic.

- `team-engine-algorithm-design` — Algorithm design and executable implementation.
- `team-engine-state-machines` — State machine with transition tests.
- `team-engine-parsing` — Parser with actionable error cases.
- `team-engine-simulation` — Reproducible simulation evidence.
- `team-engine-numeric-correctness` — Numerical contract and boundary tests.
- `team-engine-concurrency` — Concurrency implementation and race checks.
- `team-engine-property-tests` — Invariant coverage with reproducible failures.
- `team-engine-benchmarking` — Benchmark artifact with environment.
- `team-engine-optimization` — Measured optimization with regression evidence.
- `team-engine-engine-learning` — Core-engine memory.

## Data — Storage & Integrity

Owns database schemas, queries, indexes, transactions, migrations and data validation.

- `team-data-schema-design` — Schema and integrity constraints.
- `team-data-local-migrations` — Migration evidence and rollback steps.
- `team-data-query-analysis` — Query plan and bottleneck evidence.
- `team-data-index-design` — Measured index change.
- `team-data-transactions` — Transaction semantics and tests.
- `team-data-data-validation` — Validation and rejected-input evidence.
- `team-data-backfill-design` — Backfill procedure and local proof.
- `team-data-backup-restore` — Restore verification.
- `team-data-data-fixtures` — Repeatable fixture set.
- `team-data-data-learning` — Storage memory.

## QA — Test Engineer

Builds meaningful regression, integration, browser and exploratory test coverage.

- `team-qa-test-strategy` — Risk-based test matrix.
- `team-qa-regression-reproduction` — Minimal reproduction and failing test.
- `team-qa-unit-behavior` — Focused unit coverage.
- `team-qa-integration-tests` — Integration suite and isolation evidence.
- `team-qa-journey-tests` — User journey coverage.
- `team-qa-exploratory-testing` — Exploratory findings with repro steps.
- `team-qa-flaky-tests` — Flake diagnosis and corrected test.
- `team-qa-fixture-isolation` — Repeatable isolated test setup.
- `team-qa-coverage-gaps` — Prioritized coverage gaps.
- `team-qa-qa-learning` — Test-engineering memory.

## Security — Application Reviewer

Reviews trust boundaries, authorization, secrets, dependencies and abuse cases.

- `team-security-threat-model` — Focused threat model.
- `team-security-authorization-audit` — Authorization findings and denial evidence.
- `team-security-input-boundaries` — Boundary analysis and harmless local repros.
- `team-security-secret-hygiene` — Secret-free diff and configuration guidance.
- `team-security-dependency-review` — Relevant dependency findings.
- `team-security-session-security` — Session protection evidence.
- `team-security-file-upload` — Upload abuse-case tests.
- `team-security-secure-errors` — Safe error and log checks.
- `team-security-security-fix-check` — Fix verification and regression evidence.
- `team-security-security-learning` — Scoped security review memory.

## Platform — Local Runtime & Tooling

Owns local environments, packaging, WSL/Windows paths, developer tooling and observability without remote CI.

- `team-platform-local-environment` — Verified local environment.
- `team-platform-build-packaging` — Build commands and checked artifacts.
- `team-platform-wsl-windows-paths` — Cross-platform path checks.
- `team-platform-local-services` — Service lifecycle instructions.
- `team-platform-port-verification` — Health evidence and localhost/WSL URLs.
- `team-platform-local-gates` — Local verification entry points.
- `team-platform-tool-integration` — Validated tooling integration.
- `team-platform-runtime-diagnostics` — Actionable local runtime diagnostics.
- `team-platform-rollback-runtime` — Reversible local runtime procedure.
- `team-platform-platform-learning` — Environment memory.

## Integrator — Git & Release Coordinator

Coordinates isolated worktrees, atomic commits, conflict resolution, gated pushes and reviewable PRs.

- `team-integrator-worktree-isolation` — Unique role worktree and topic branch, with the verified cwd of the pane.
- `team-integrator-atomic-staging` — Focused staged diff.
- `team-integrator-conventional-commits` — Atomic conventional commit.
- `team-integrator-integration-order` — Ordered integration record.
- `team-integrator-conflict-resolution` — Resolved conflict with verification.
- `team-integrator-sha-gated-push` — Topic push for exact approved SHA.
- `team-integrator-issue-linked-pr` — Reviewable linked PR.
- `team-integrator-merge-readiness` — Merge-ready evidence packet.
- `team-integrator-git-recovery` — Documented reversible recovery.
- `team-integrator-integration-learning` — Git coordination memory.
