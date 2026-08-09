# Simplify Aug. 7 Figure Titles and Footers

## Objective

Clean the Aug. 7 BioSMB figure package so every figure title contains only
`Aug. 7 BioSMB RL Test`, the target legends use `Target` instead of
`Reconstructed target`, and the generated-UTC and bottle-out explanatory
footers and all descriptions below the title are removed.

## Files changed

- `helpers/biosmb_experiment_plotting.py`
  - Uses the experiment label alone for combined and stream-specific titles.
  - Removes visible generation timestamps from combined and stream-specific
    figures.
  - Removes the bottle-out/instantaneous-flow footer.
  - Removes method descriptions below the title from combined and
    stream-specific figures.
  - Simplifies the two target legend labels to `Target` and
    `Target +/- 0.10 pH`.
  - Shortens every x-axis label to `Time [min]`.
  - Simplifies every input legend to only `Commanded flow` and
    `Calculated flow`.
  - Removes the unused `generated_at` plotting arguments.
- `analysis/plot_biosmb_experiment.py`
  - Updates calls to the simplified plotting interfaces.
- `tests/test_biosmb_experiment_plotting.py`
  - Updates the focused plotting-interface test.

## Implementation summary

This was a presentation-only change. Flow calculations, interval definitions,
pH processing, stream selection, tables, metrics, and the run manifest were not
changed. The manifest continues to preserve the UTC generation time and code
provenance even though the timestamp is no longer printed on the PNG files.
Interval definitions and densities also remain available in the generated
tables and manifest after their visible title descriptions were removed.

## Generated artifacts

Regenerated all six figures under:

```text
results/aug7_biosmb_figures_20260807_210733/
```

The combined second-level and one-minute figures and all four stream-specific
acid/sodium acetate figures now use the simplified title and contain neither
requested footer. The two combined figures also use the simplified target
legend labels.

## Verification

Commands:

```powershell
& '.\.venv\Scripts\python.exe' -m py_compile helpers/biosmb_experiment_plotting.py analysis/plot_biosmb_experiment.py tests/test_biosmb_experiment_plotting.py
& '.\.venv\Scripts\python.exe' -m unittest tests.test_biosmb_experiment_plotting -v
& '.\.venv\Scripts\python.exe' analysis/plot_biosmb_experiment.py --output-dir 'results/aug7_biosmb_figures_20260807_210733'
```

Results:

- Compilation passed.
- All 5 focused tests passed.
- The runner regenerated three figures in each resolution package.
- Source search found no remaining `Generated` or `Bottle-out` plot text.
- Visual inspection of a combined figure and a stream-specific figure confirmed
  the requested title, description, target/input legends, x-axis, and footer
  cleanup.

## Known limitations or next steps

- Legends, annotations, axis labels, and units remain visible because they
  identify the plotted signals.
