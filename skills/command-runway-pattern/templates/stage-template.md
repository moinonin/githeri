# COMMAND_RUNWAY Plan Stage Template

Copy this template once per stage when authoring a Layer 2 plan (`COMMAND_RUNWAY.md` or equivalent). Fill every section. Stages are typically < 1 hour and contain 5–15 commands.

```markdown
## Stage N: <Stage Name>

### Objective
<One sentence: what this stage accomplishes — what is built or what capability is enabled>

### Preconditions
- [ ] <condition 1 — tool installed, file present, prior stage verified>
- [ ] <condition 2>

### Commands

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1   | —    | ⏾    | <read_file path>          | <expected understanding> | <search if missing> |
| C2   | C1   | ✎    | <write_file / patch>      | <file changed>          | <revert + re-read>  |
| C3   | C2   | ✓    | <build && test>            | exit 0                  | see Failure Procedure |

### Expected Outputs
- **Files:** <list of file paths created/modified>
- **Tests:** <test file paths and what they assert>
- **Other artifacts:** <migrations, configs, generated assets>

### Local Verification
| Check | Command | Expected |
|-------|---------|----------|
| Build | `<exact build cmd>` | Exit 0 |
| Tests | `<exact test cmd>` | All pass |
| <Other> | <exact cmd> | <exact expected> |

### Failure Procedure
On any ✓ failure:
1. Stop — do not run dependent commands
2. Diagnose — classify: incorrect assumption | missing dependency | bad implementation | environment | test mismatch | unexpected architecture
3. Record — write the diagnosis + fix in Section 6 of the runbook
4. Retry — re-run the failed command (increment Retry#)
5. Never advance until the retry exits 0
6. Never weaken the assertion to pass — fix the implementation, not the gate

### Completion Condition
<Binary rule. E.g. "C3 exits 0 AND Local Verification row Tests passes AND precondition P2 of the next stage is satisfiable">
```

## Usage Notes

1. **Discovery commands (⏾) are not optional.** They prevent fabricated-path errors. Every stage that mutates something must inspect it first.
2. **Commands are copy-paste runnable.** Avoid placeholders; if unavoidable, use `[PLACEHOLDER: <meaning>]`.
3. **`Deps` enforces the in-stage DAG.** A command cannot start until all `Deps` have exited 0.
4. **Completion is binary.** Either the condition is met or it isn't — no partial progress.
5. **Keep stages atomic.** If a stage exceeds 15 commands or 1 hour, split it. Retry granularity is per-stage.
6. **Falls back, doesn't give up.** Every ✎/✓ command states the corrective hook — never "fix it."
