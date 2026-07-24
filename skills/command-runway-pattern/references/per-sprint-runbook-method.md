# Per-Sprint Runbook Method

This reference captures the technique of generating individual COMMAND_RUNWAY plan/runbook pairs for each sprint in a multi-sprint project, rather than a single monolithic runbook for the entire project.

## Context

The Verified Attention Engine (VAE) project has 24 sprints across 6 phases (SPRINTS.md). In this session, we generated 20 individual sprint runbooks (Sprints 2–21) using the `command-runway-pattern` skill, each as a separate PLAN.md + RUNBOOK.md pair in `/tmp/sprint-runbooks/sprint-XX/`.

## Why Per-Sprint Runbooks

### Advantages Over Monolithic Runbook

| Aspect | Monolithic | Per-Sprint |
|--------|------------|------------|
| **Retry granularity** | Entire project re-run on failure | Failed sprint re-run only |
| **Parallel execution** | Sequential by default | Independent sprints can run in parallel (when DAG allows) |
| **Audit trail** | Mixed concerns in one log | Clean separation per sprint |
| **Team ownership** | Single owner for all | Each sprint assignable to different agent/team |
| **Context size** | Grows unbounded | Bounded per sprint |
| **CI integration** | One giant pipeline | Per-sprint CI gates |

### When to Use Per-Sprint

- Multi-sprint projects with formal sprint plans (SPRINTS.md style)
- Projects with explicit sprint dependencies (DAG between sprints)
- Teams that want to track velocity per sprint
- CI/CD pipelines that gate per-sprint

### When Monolithic Is Fine

- Single-sprint or < 3 sprints total
- Highly coupled work that can't be meaningfully separated
- Throwaway/prototype work

## Generation Pattern

For each sprint, we created:

1. **PLAN.md** — Layer 2 static plan
   - Sprint context, spec sources, task table
   - Stages (1 per major task, sometimes 2 for complex tasks)
   - Each stage: preconditions, command table (⏾/✎/✓), local verification, failure procedure, completion condition
   - Global verification block at end

2. **RUNBOOK.md** — Layer 3 execution template
   - Same stage structure as PLAN.md
   - Empty Execution Log table (Start/End/Exit/Retry#/Output Summary)
   - Goal verification (local + global)
   - Iteration & Notes section
   - Machine-readable JSON serialization

## Sprint Dependency DAG

The per-sprint runbooks encode sprint dependencies via preconditions. Example from Sprint 3:

```markdown
### Preconditions
- [ ] Sprint 1 verified (monorepo, CI/CD, ADR-001)
- [ ] Sprint 2 verified (evidence model, pipeline, store)
- [ ] packages/core/dist/ exists with Evidence, Observation types
- [ ] packages/pipeline/dist/ exists with validation, normalization
- [ ] packages/store/dist/ exists with InMemoryEvidenceStore
```

This creates a verifiable DAG: Sprint 3 cannot start until Sprint 2's completion condition is met.

## Execution Patterns

### Sequential (Default)

Run Sprint 2 → wait for completion → run Sprint 3 → etc.

### Parallel Where Possible

Sprints with no dependency overlap can run in parallel. Example: Sprints 8 (Attention Intelligence) and 9 (Fraud Intelligence) both depend on Sprint 7 (Pipeline Hardening) but not on each other. After Sprint 7 completes, 8 and 9 can run concurrently.

### CI/CD Integration

Each sprint's Global Verification block maps to a CI job:

```yaml
# .github/workflows/sprint-02.yml
jobs:
  sprint-02:
    needs: [sprint-01]
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm build --filter=@verified-attention/core
      - run: pnpm test --filter=@verified-attention/core --coverage
      - run: pnpm test:conformance --filter=@verified-attention/core
```

## Lessons Learned

### 1. Sprint Boundaries Match Verification Gates

Each sprint's tasks naturally map to stages that end with verification. The sprint acceptance criteria become the stage completion conditions.

### 2. Stage Count ≈ Sprint Tasks

Sprint 2 had 7 tasks → 9 stages. Sprint 11 had 7 tasks → 7 stages. Rule of thumb: 1–2 stages per sprint task.

### 3. Cross-Sprint Artifacts Need Explicit Preconditions

Don't assume "Sprint 2 done" implies "EvidenceStore available." State explicitly: `packages/store/dist/evidence-store.js exists`.

### 4. Spec Traceability Scales Per-Sprint

Each sprint's spec sources are a subset of the full spec. Sprint 2 references VAP §4–5; Sprint 11 references VAP §10 + Appendix A. Per-sprint runbooks keep spec context focused.

### 5. Templates Required Zero Modification

The `stage-template.md` and `runbook-template.md` from the skill handled all 20 sprints without changes. This confirms the template design is robust.

## File Structure

```
/tmp/sprint-runbooks/
├── sprint-02/
│   ├── PLAN.md      # ~38 KB
│   └── RUNBOOK.md   # ~36 KB
├── sprint-03/
│   ├── PLAN.md
│   └── RUNBOOK.md
...
├── sprint-21/
│   ├── PLAN.md
│   └── RUNBOOK.md
```

Total: 20 sprints × 2 files = 40 documents, ~1.5 MB total.

## Next Steps for This Project

1. **Execute Sprint 2** — partially complete in repo; run its RUNBOOK.md from where it left off
2. **Wire CI/CD** — add per-sprint workflow files
3. **Track Velocity** — log actual vs planned per sprint
4. **Retrospective** — after Sprint 3, review runbook effectiveness