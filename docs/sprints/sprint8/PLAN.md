# PLAN: sprint8-code-review-agent

**Status:** [ Draft | Approved | In-Progress | Complete ]
**Derived From Spec:** sprint8-code-review-agent.yaml
**Generated:** 2026-07-27

---

## 1. Intent & Goals

### Summary
Build LLM-powered code review agent with pattern enforcement, security scanning, and CI/CD integration

### Dependencies
None

### Global Goals (from project)
- G1: Core specification published
- G2: Core data models with schemas & 100% conformance
- G3: End-to-end pipeline functional
- G4: Data store operational
- G5: State machine enforced
- G6: Intelligence model performing
- G7: Fraud detection performing
- G8: Verification engine deterministic
- G9: Proof generation operational
- G10: Reward pipeline functional
- G11: Client SDK within size budget
- G12: Extension published
- G13: Public APIs with OpenAPI spec + generated SDKs
- G14: Security posture production-ready
- G15: Privacy compliance (GDPR/CCPA)
- G16: Observability stack operational
- G17: Load tests passing
- G18: Chaos tests passing
- G19: All CI gates pass

### Task-Local Goals
- **L1**: CREATE: Code review skill with diff analysis and pattern enforcement
- **L2**: CREATE: Review diff script with structured output (findings: block/warn/info)
- **L3**: CREATE: Pattern library with naming, structure, imports, testing rules
- **L4**: CREATE: Security scanner for secrets, vulnerabilities, license issues
- **L5**: CREATE: Pattern enforcement script
- **L6**: VERIFY: Review agent catches injected bugs in test diffs
- **L7**: VERIFY: Pattern enforcement passes on clean code, fails on violations

---

## 2. Preconditions
Everything that must exist before Stage 1 starts.

Python 3.11+, pip installed
- Virtual environment active

---

## 3. Execution Stages

### Stage 1: CREATE: Code review skill with diff analysis and pattern enf (CREATE)

#### Objective
CREATE: Code review skill with diff analysis and pattern enforcement

#### Action
CREATE

#### Verification Command
```bash
test -f skills/software-development/code-review-agent/SKILL.md && grep -q -- 'code-review-agent' skills/software-development/code-review-agent/SKILL.md
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 2: CREATE: Review diff script with structured output (findings: (CREATE)

#### Objective
CREATE: Review diff script with structured output (findings: block/warn/info)

#### Action
CREATE

#### Verification Command
```bash
test -f skills/software-development/code-review-agent/scripts/review_diff.py && grep -q -- 'block|warn|info' skills/software-development/code-review-agent/scripts/review_diff.py
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 3: CREATE: Pattern library with naming, structure, imports, tes (CREATE)

#### Objective
CREATE: Pattern library with naming, structure, imports, testing rules

#### Action
CREATE

#### Verification Command
```bash
test -f .hermes/patterns/naming.yaml
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 4: CREATE: Security scanner for secrets, vulnerabilities, licen (CREATE)

#### Objective
CREATE: Security scanner for secrets, vulnerabilities, license issues

#### Action
CREATE

#### Verification Command
```bash
test -f skills/software-development/code-review-agent/scripts/security_scan.py && grep -q -- 'secret|vulnerab' skills/software-development/code-review-agent/scripts/security_scan.py
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 5: CREATE: Pattern enforcement script (CREATE)

#### Objective
CREATE: Pattern enforcement script

#### Action
CREATE

#### Verification Command
```bash
test -f skills/software-development/code-review-agent/scripts/enforce_patterns.py && grep -q -- 'pattern|naming|import' skills/software-development/code-review-agent/scripts/enforce_patterns.py
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 6: VERIFY: Review agent catches injected bugs in test diffs (VERIFY)

#### Objective
VERIFY: Review agent catches injected bugs in test diffs

#### Action
VERIFY

#### Verification Command
```bash
python skills/software-development/code-review-agent/scripts/review_diff.py --diff tests/fixtures/buggy.diff --format json && echo 'exit_code=0'
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)


### Stage 7: VERIFY: Pattern enforcement passes on clean code, fails on v (VERIFY)

#### Objective
VERIFY: Pattern enforcement passes on clean code, fails on violations

#### Action
VERIFY

#### Verification Command
```bash
python skills/software-development/code-review-agent/scripts/enforce_patterns.py --path . --strict && echo 'exit_code=0'
```

#### Expected Result
Exit code 0 (or expected HTTP status / file content)



---

## 4. Global Verification
Run after all stages complete.

Full test suite: pytest (or project equivalent)
Integration tests
Security scan
Build verification

---

## 5. Rollback Plan
If any stage fails irreversibly.

git reset --hard HEAD~7
Clear build artifacts

