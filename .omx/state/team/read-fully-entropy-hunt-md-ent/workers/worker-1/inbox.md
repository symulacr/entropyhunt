# New Task Assignment

**Worker:** worker-1
**Task ID:** 1

## Task Description

Implement the core functionality for: READ FULLY: entropy_hunt.md + entropy_hunt_mockup.html + entropy_hunt_v2.html (no skimming). Work together to build clean production-grade Entropy Hunt codebase. Deploy iteratively to Vercel. Use: architect, frontend-design, frontend-code-review, code-review, deep-interview, security-review, ralph, ralplan, note, ai-slop-cleaner, ultrawork, trace, Frontend Skill, autopilot.

## Instructions

1. Resolve canonical team state root and read the task file at `<team_state_root>/team/read-fully-entropy-hunt-md-ent/tasks/task-1.json`
2. Task id format:
   - State/MCP APIs use `task_id: "1"` (not `"task-1"`).
3. Request a claim via CLI interop (`omx team api claim-task --json`)
4. Complete the work
5. After completing work, commit your changes before reporting completion:
   `git add -A && git commit -m "task: <task-subject>"`
   This ensures your changes are available for incremental integration into the leader branch.
6. Complete/fail via lifecycle transition API (`omx team api transition-task-status --json`) from `"in_progress"` to `"completed"` or `"failed"` (include `result`/`error`)
7. Use `omx team api release-task-claim --json` only for rollback to `pending`
8. Write `{"state": "idle", "updated_at": "<current ISO timestamp>"}` to your status file


## Verification Requirements

## Verification Protocol

Verify the following task is complete: Implement the core functionality for: READ FULLY: entropy_hunt.md + entropy_hunt_mockup.html + entropy_hunt_v2.html (no skimming). Work together to build clean production-grade Entropy Hunt codebase. Deploy iteratively to Vercel. Use: architect, frontend-design, frontend-code-review, code-review, deep-interview, security-review, ralph, ralplan, note, ai-slop-cleaner, ultrawork, trace, Frontend Skill, autopilot.

### Required Evidence:

1. Run full type check (tsc --noEmit or equivalent)
2. Run test suite (focus on changed areas)
3. Run linter on modified files
4. Verify the feature/fix works end-to-end
5. Check for regressions in related functionality

Report: PASS/FAIL with command output for each check.

## Fix-Verify Loop

If verification fails:
1. Identify the root cause of each failure
2. Fix the issue (prefer minimal changes)
3. Re-run verification
4. Repeat up to 3 times
5. If still failing after 3 attempts, escalate with:
   - What was attempted
   - What failed and why
   - Recommended next steps

When marking completion, include structured verification evidence in your task result:
- `Verification:`
- One or more PASS/FAIL checks with command/output references

