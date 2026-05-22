# Rewrite AGENTS Modeling And Git Workflow

Generated: 2026-05-22 01:10:36

## Objective

Rewrite `AGENTS.md` so future work follows the current pH modeling workflow and the new local change-report plus commit policy.

## Files Changed

- `AGENTS.md`
- `change-reports/20260522_011036_rewrite_agents_modeling_git_workflow.md`

## Method Summary

The project instructions were replaced with current guidance for:

- first-principles pH modeling scope,
- lab CSV column conventions,
- Henderson-Hasselbalch and equilibrium charge-balance workflows,
- timestamped result folders,
- presentation-ready reports with equations, figures, observations, conclusions, and next steps,
- dynamic-data interpretation,
- local change reports after each task,
- local commits after completed work,
- push-to-GitHub only when explicitly requested.

## Generated Artifacts

- New canonical change-report folder: `change-reports/`
- This change report.

## Verification

Documentation-only task. Verified by inspecting `AGENTS.md`.

- Current model and runner names are documented.
- The `rl-env` interpreter command is documented.
- No `outputs/` workflow is documented.
- MPC/RL/controller work is still excluded for now.
- `change-reports/` and commit-after-work policy are documented.
- Push-only-when-requested policy is documented.

## Known Limitations And Next Steps

- This task does not edit code, raw data, reports, or generated results.
- Existing dirty files from previous tasks remain outside this documentation commit unless explicitly staged later.
