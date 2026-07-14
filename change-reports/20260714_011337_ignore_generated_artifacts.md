# Ignore generated artifacts and clean tracked results

## Objective

Reduce the working-tree noise caused by generated experiment results, local
datasets, transfer archives, logs, and the local `Biosmb-interact` reference
application. Remove previously tracked result and data files from the current
Git tree so future generated files remain local.

## Files changed

- `.gitignore`
- `CODEX_CONTEXT.md` removed as approved
- `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` removed from Git
- 100 previously tracked files below `results/` removed from Git
- `change-reports/20260714_011337_ignore_generated_artifacts.md`

## Implementation summary

The existing `results/` and `Data/*.csv` rules did not hide historical files
that were already tracked. Their existing working-tree deletions were therefore
committed. Additional ignore rules cover local dataset formats, logs, transfer
archives, and `Biosmb-interact/`. Reviewed TD3 deployment artifacts remain
tracked because no global model or checkpoint extension was ignored.

## Generated artifacts

None. Existing local ignored results were not deleted or modified.

## Verification

- `git check-ignore -v` confirms result, data, log, archive, and
  `Biosmb-interact` paths are ignored.
- `git diff --check` passes.
- `git status --short` is expected to be empty after the cleanup commit.

## Known limitations and next steps

Ignore rules affect new untracked files. They do not remove large objects from
older Git history. Rewriting repository history was intentionally not performed.
