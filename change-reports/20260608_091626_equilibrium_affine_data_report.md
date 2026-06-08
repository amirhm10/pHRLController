# Equilibrium Affine Data Report

## Objective

Create a new focused Markdown report from the existing dynamic-identification
and BioSMB plumbing reports. The requested report should explain the data,
include the BioSMB pH plumbing map at the top, and focus only on the
equilibrium charge-balance model and the affine correction to measured `PH_2`.

## Files Changed

- `reports/equilibrium_affine_data_report.md`
- `change-reports/20260608_091626_equilibrium_affine_data_report.md`

## Method Or Implementation Summary

Created a new standalone report with:

- BioSMB pH plumbing map at the top,
- current pump, valve, and `PH_2` interpretation,
- source CSV mapping and raw-column grouping,
- processed modeling-table definitions,
- valid-row and flat-pH trial filtering explanation,
- sampling-time summary from the dynamic-identification report,
- data/context figures,
- equilibrium charge-balance equations,
- affine calibration equation and interpretation,
- validation metrics from the equilibrium main-model workflow,
- relevant equilibrium, residual, RMSE, pump-grid, and water-dilution plots,
- a clear boundary that the model is not yet a dynamic plant simulator or
  controller.

The report intentionally excludes Henderson-Hasselbalch, transport-delay,
first-order dynamic wrapper, MPC, RL, reward, policy, and controller material.

## Generated Artifacts

- `reports/equilibrium_affine_data_report.md`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -c "import pathlib,re; report=pathlib.Path('reports/equilibrium_affine_data_report.md'); text=report.read_text(encoding='utf-8'); links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text); missing=[]; [missing.append(link) for link in links if not (report.parent / link).resolve().exists()]; print('image_links:', len(links)); print('missing:', missing)"
```

Result:

```text
image_links: 9
missing: []
```

```powershell
rg -n ";" reports/equilibrium_affine_data_report.md
```

Result: no matches.

## Known Limitations Or Next Steps

- The report links to existing figures and tables. It does not generate new
  analysis artifacts.
- The report is intentionally static-model focused. A separate report should be
  used for dynamic identification, transport-delay fitting, or open-loop
  experiment execution.
