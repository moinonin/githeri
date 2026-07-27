# COMMAND_RUNWAY -- model-provider-switching

**Target**: Add model provider switching to run_pipeline.py
**Specification**: `docs/specs/0001-verified-attention-protocol.md` (VAP), `docs/specs/0000-project-charter.md` (Charter), `docs/specs/0010-verified-attention-engine.md` (VAE)
**Sprint Plan**: `SPRINTS.md` (21 sprints across 5 phases to VAE 1.0)
**Monorepo**: TypeScript/Node.js (pnpm + Turborepo), packages: `core`, `pipeline`, `store`, `verification`, `crypto`, `ml/attention`, `ml/fraud`, `sdk/browser`, `sdk/mobile`, `sdk/desktop`, `extension`, `api`, `verifier`, `reward`, `analytics`, `cli`

---

# Feature

Name: model-provider-switching
Purpose: Add model provider switching to run_pipeline.py
Reference Specification: `docs/specs/0001-verified-attention-protocol.md`, `docs/specs/0000-project-charter.md`, `docs/specs/0010-verified-attention-engine.md`
Expected Deliverables: INSPECT: check existing run_pipeline.py structure, CREATE: add CLI flags --provider (ollama|openroute, CREATE: add model provider switching logic for Oll, CREATE: add .env configuration for Ollama and Open, VERIFY: run_pipeline.py recognizes --provider olla, VERIFY: run_pipeline.py recognizes --provider open
Dependencies: None
Assumptions: Node.js >= 20, pnpm >= 9, Turborepo configured, Prisma ORM, Vitest test framework

---

# Global Success Criteria


---

# Target Environment

Language: Python
Framework: githeri
ORM: Prisma
Test Framework: pytest

---

# Execution Stages

## Stage 1: check existing run_pipeline.py structure

### Objective
INSPECT: check existing run_pipeline.py structure

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 1 verified complete (if 1 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] INSPECT: check existing run_pipeline.py structure

### Execution Tasks
1. **INSPECT**: INSPECT: check existing run_pipeline.py structure


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L1.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L1 | `L1` | exit 0 |
## Stage 2: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py

### Objective
CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 2 verified complete (if 2 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing APIs
- [ ] Inspect interfaces
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **CREATE**: CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py
   - Write implementation
   - Write tests
   - Export from index


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L2.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L2 | `L2` | exit 0 |
## Stage 3: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py

### Objective
CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 3 verified complete (if 3 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing APIs
- [ ] Inspect interfaces
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **CREATE**: CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py
   - Write implementation
   - Write tests
   - Export from index


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L3.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L3 | `L3` | exit 0 |
## Stage 4: add .env configuration for Ollama and OpenRouter

### Objective
CREATE: add .env configuration for Ollama and OpenRouter

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 4 verified complete (if 4 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing APIs
- [ ] Inspect interfaces
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **CREATE**: CREATE: add .env configuration for Ollama and OpenRouter
   - Write implementation
   - Write tests
   - Export from index


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L4.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L4 | `L4` | exit 0 |
## Stage 5: run_pipeline.py recognizes --provider ollama flag

### Objective
VERIFY: run_pipeline.py recognizes --provider ollama flag

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 5 verified complete (if 5 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing APIs
- [ ] Inspect interfaces
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **VERIFY**: VERIFY: run_pipeline.py recognizes --provider ollama flag
   - Run verification command
   - Confirm expected output


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L5.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L5 | `L5` | exit 0 |
## Stage 6: run_pipeline.py recognizes --provider openrouter flag

### Objective
VERIFY: run_pipeline.py recognizes --provider openrouter flag

### Inputs
- VAP Spec Sections (see per-sprint SPRINTS.md)
- SPRINTS.md Sprint switching tasks

### Preconditions
- Stage 6 verified complete (if 6 > 1)
- Node.js >= 20, pnpm >= 9 installed
- Git repo initialized

### Discovery Tasks
- [ ] Inspect project structure
- [ ] Inspect existing APIs
- [ ] Inspect interfaces
- [ ] Inspect tests
- [ ] Inspect configuration
- [ ] Inspect dependencies

### Execution Tasks
1. **VERIFY**: VERIFY: run_pipeline.py recognizes --provider openrouter flag
   - Run verification command
   - Confirm expected output


### Suggested Commands
```bash
# 1. Inspect existing structure
cat packages/core/src/index.ts

# 2. Create/Modify implementation
cat > packages/core/src/L6.ts << 'EOF'
// Implementation here
EOF

# 3. Run verification
pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core
```

### Expected Outputs
- Implementation file(s)
- Test file(s) (>=80% coverage)
- Exports added to index.ts
- Documentation updated

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| L6 | `L6` | exit 0 |


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
