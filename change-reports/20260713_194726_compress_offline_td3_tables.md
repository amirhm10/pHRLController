# Compress Offline TD3 Result Tables

## Objective

Reduce the disk space used by future offline pH TD3 result folders without
discarding training rows or diagnostic columns. Keep the BioSMB online runner
unchanged.

## Files changed

- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `change-reports/20260713_194726_compress_offline_td3_tables.md`

## Implementation summary

- Replaced the two full 500,000-row files `trajectory.csv` and
  `trajectory_diagnostics.csv` with one `trajectory.csv.gz` file.
- The single compressed trajectory contains the original rollout columns and
  the added diagnostic columns. No rows or scientific fields are downsampled.
- Used gzip compression level 6 for a practical size and write-time balance.
- Kept the small summary, schedule, constraint, and metric tables as ordinary
  CSV files.
- Added result-storage metadata to future `config_snapshot.json` files.
- Updated the result manifest to list the compressed trajectory.
- Updated the report generator to prefer `trajectory.csv.gz` while retaining
  support for historical `trajectory.csv` result folders.
- Left all files under `Biosmb-run-online` unchanged.

## Storage evidence

The latest completed result folder used approximately 753 MB for its tables:

- `trajectory.csv`: 352.658 MB
- `trajectory_diagnostics.csv`: 398.927 MB
- all table files: 752.959 MB

A temporary gzip test of the complete 398.927 MB diagnostic trajectory produced
a 125.233 MB file. Including the remaining small tables, the projected future
table-folder size is about 126.6 MB. This is an approximately 83.2 percent
reduction while preserving the complete trajectory.

The temporary compression file was removed after measurement. The completed
500,000-step result folder was not rewritten or deleted.

## Generated artifacts

A disposable 400-step result was generated under
`results/codex_smoke_compact_tables`. It contained one 57-column compressed
trajectory with 400 readable rows and no duplicate diagnostic trajectory. The
disposable result was removed after verification.

## Verification commands and results

Compilation:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile run_offline_ph_td3_training.py helpers/offline_ph_td3_results.py analysis/generate_offline_ph_td3_report.py tests/test_offline_ph_rl.py
```

Result: passed.

Focused offline TD3 tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m pytest -p no:cacheprovider tests/test_offline_ph_rl.py -q
```

Result: 26 passed.

Full repository test attempt:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m pytest -q
```

Result: 47 passed, 1 skipped, and 2 unrelated failures. The two failures are
BioSMB artifact-copy checks whose hard-coded source result folder
`results/offline_ph_td3_training_20260710_183129` was already absent. This task
did not modify those tests, the deployed model files, or the BioSMB runner.

Additional checks:

- the compressed trajectory round-tripped through `pandas.read_csv`
- all 400 smoke rows and 57 columns were preserved
- the report loader read the current legacy 500,000-row `trajectory.csv`
- the artifact manifest lists `tables/trajectory.csv.gz`
- `git diff --check` passed

## Known limitations and next steps

- Gzip saves substantial disk space but requires decompression while reading.
- Existing result folders remain in their historical format. The report loader
  supports both formats.
- Spreadsheet software may require extracting `trajectory.csv.gz` before
  opening it. Pandas reads it directly.
- The absent historical BioSMB source artifacts must be restored separately if
  the two exact-copy fidelity tests need to pass again.
