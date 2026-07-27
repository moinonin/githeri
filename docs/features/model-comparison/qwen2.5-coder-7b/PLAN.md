# COMMAND_RUNWAY -- sprint-5-model-provider-switching

**Target**: Add model provider switching functionality
**Specification**: `docs/specs/0001-verified-attention-protocol.md` (VAP), `docs/specs/0000-project-charter.md` (Charter), `docs/specs/0010-verified-attention-engine.md` (VAE)
**Sprint Plan**: `SPRINTS.md` (21 sprints across 5 phases to VAE 1.0)
**Monorepo**: TypeScript/Node.js (pnpm + Turborepo), packages: `core`, `pipeline`, `store`, `verification`, `crypto`, `ml/attention`, `ml/fraud`, `sdk/browser`, `sdk/mobile`, `sdk/desktop`, `extension`, `api`, `verifier`, `reward`, `analytics`, `cli`

---

# Feature

Name: sprint-5-model-provider-switching
Purpose: Add model provider switching functionality
Reference Specification: `docs/specs/0001-verified-attention-protocol.md`, `docs/specs/0000-project-charter.md`, `docs/specs/0010-verified-attention-engine.md`
Expected Deliverables: CREATE: ModelProviderSwitcher class in run_pipelin, VERIFY: Model provider switching tests pass
Dependencies: None
Assumptions: Node.js >= 20, pnpm >= 9, Turborepo configured, Prisma ORM, Vitest test framework

---

# Global Success Criteria


---

# Target Environment

Language: Python
Framework: None
ORM: Prisma
Test Framework: pytest

---

# Execution Stages

## Stage 1: ModelProviderSwitcher class in run_pipeline.py

### Objective
CREATE: ModelProviderSwitcher class in run_pipeline.py

### Inputs
- Spec: sprint-5-model-provider-switching


### Preconditions
- Stage 1 verified complete (if 1 > 1)
- Python 3.11+, pip installed
- Virtual environment active

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing Python modules
- [ ] Inspect requirements.txt / pyproject.toml
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **CREATE**: CREATE: ModelProviderSwitcher class in run_pipeline.py
   - Write implementation
   - Write tests
   - Export from index


### Suggested Commands
```bash
# 1. Inspect existing structure
cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'

# 2. Create/Modify implementation
cat > packages/pipeline/src/run_pipeline.py << 'EOF'
# Implementation here
EOF

# 3. Run verification
test -f packages/pipeline/src/run_pipeline.py && grep -q -- 'ModelProviderSwitcher' packages/pipeline/src/run_pipeline.py
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L1 | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` | exit 0 |

## Stage 2: Model provider switching tests pass

### Objective
VERIFY: Model provider switching tests pass

### Inputs
- Spec: sprint-5-model-provider-switching


### Preconditions
- Stage 2 verified complete (if 2 > 1)
- Python 3.11+, pip installed
- Virtual environment active

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing Python modules
- [ ] Inspect requirements.txt / pyproject.toml
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **VERIFY**: VERIFY: Model provider switching tests pass
   - Run verification command
   - Confirm expected output


### Suggested Commands
```bash
# 1. Inspect existing structure
cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'

# 2. Create/Modify implementation
cat > src/main.py << 'EOF'
# Implementation here
EOF

# 3. Run verification
pnpm test --filter=@verified-attention/pipeline-model-provider-switching && echo 'exit_code=0'
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L2 | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` | exit 0 |



---

# Global Verification (Post-Stage {0})

After all stages complete, perform complete project validation:

| Verification | Command / Action | Pass Criteria |
|--------------|------------------|---------------|
| Full Build | `pnpm build` | All packages build |
| Full Test Suite | `pnpm test` | All unit + integration + conformance pass |
| Typecheck | `pnpm typecheck` | Zero errors |
| Lint | `pnpm lint` | Zero errors |
| Format | `pnpm format --check` | No changes needed |
| Conformance | `pnpm test:conformance` | 100% VAP coverage |
| Load Tests | `pnpm test:load` | All thresholds met |
| Chaos Tests | `pnpm test:chaos` | Recovery < 30s, zero data loss |
| Security | Pen test report, SBOM | Critical/High = 0, SBOM current |
| Privacy | DPIA sign-off, conformance | Auditor approved, tests pass |
| Observability | Dashboards, alerts, tracing | All operational |
| Documentation | `docs/` complete | API, SDK, quickstart, architecture |
| VAP Spec | `docs/specs/0001-verified-attention-protocol.md` | v1.0 published |
| Release | GitHub Release `vae-1.0` | Tagged, artifacts published |

**Only after every global verification succeeds may the COMMAND_RUNWAY declare the feature complete.**

---

# Execution Rules (Mandatory)

1. **Never skip stages** -- Each stage builds on verified outputs of previous stages
2. **Never skip verification** -- Local verification must pass before proceeding
3. **Never continue after failed verification** -- Diagnose, produce corrective plan, repeat stage
4. **Never modify uninspected files** -- Read before write, always
5. **Prefer incremental implementation** -- Small commits, isolated changes
6. **Minimize edits** -- Touch only what the stage requires
7. **Preserve backwards compatibility** -- API changes only in Stage 19 with versioning
8. **Do not duplicate functionality** -- Reuse existing packages, check before creating
9. **Keep commits small and isolated** -- One logical change per commit
10. **Treat every stage as a complete iteration** -- Understand -> Inspect -> Plan -> Execute -> Verify

---

# Failure Procedure Template (Per Stage)

When any local verification fails:

```markdown
## Failure: [Stage N] - [Check Name]
**Command**: `pnpm test --filter=...`
**Exit Code**: N
**Output**: (last 50 lines)

### Root Cause Analysis
- [ ] Incorrect assumption about [spec/interface/dependency]
- [ ] Missing dependency: [package/service]
- [ ] Incorrect implementation: [file:function]
- [ ] Environment problem: [Node version, missing service, etc.]
- [ ] Test failure: [flaky, incorrect assertion, spec mismatch]
- [ ] Unexpected architecture: [discovered during inspection]

### Corrective Plan
1. [Specific fix action]
2. [Verification step]
3. [Re-run failed check]

### Repeat Stage
Re-execute failed stage tasks after fix. Do not proceed to next stage.
```

