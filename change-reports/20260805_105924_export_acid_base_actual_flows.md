# Export acid and sodium-acetate actual flows

## Objective

Provide explicit, synchronized actual-flow tables for the valid acid and
sodium-acetate bottle scales at the requested four-second and one-minute
intervals. Keep water excluded because the July 31 water scale cannot support
an actual-flow calculation.

## Data and mappings

Source:

`Data/July31 BioSMB RL Test.csv`

Mappings:

| Stream | Mass signal | Pump signal |
|---|---|---|
| Acetic acid | `mfcs-mass.acid-mass-grams` | `biosmb-flows[0]` |
| Sodium acetate | `mfcs-mass.sodium-mass-grams` | `biosmb-flows[1]` |

Both mass signals decrease during positive pump operation and track their
respective pump commands. The water mass signal increases or remains fixed and
is intentionally excluded.

## Method

For consecutive selected rows at times \(t_0\) and \(t_1\), actual
reservoir-out flow is:

\[
F_{\mathrm{actual}}
=
\frac{m(t_0)-m(t_1)}{\rho}
\frac{60}{t_1-t_0}.
\]

The current density is a provisional 1.0000 g/mL for each stream. No mass or
command samples are averaged.

The short table selects the first real CSV row from each elapsed four-second
bin. The one-minute table selects the first real CSV row from each elapsed
one-minute bin. The calculation uses the exact recorded time difference.

## Files changed

- `analysis/plot_july31_mass_derived_flows.py`
  - Adds a validated acid-and-sodium export builder.
  - Checks that both streams contain complete actual-flow values.
  - Checks that their interval metadata are synchronized.
  - Writes explicit four-second and one-minute wide tables.
  - Records the new tables in the run manifest.
- `change-reports/20260805_105924_export_acid_base_actual_flows.md`
  - Records the method, outputs, validation, and limitations.

The raw CSV was not modified.

## Generated artifacts

Under
`results/july31_biosmb_schedule_20260731_205921/tables/`:

- `acid_sodium_actual_flow_4_second.csv`
- `acid_sodium_actual_flow_one_minute.csv`

Each row contains synchronized timestamps and separate acid and sodium-acetate
values for:

- starting mass
- ending mass
- mass loss
- actual flow
- commanded flow at interval start
- commanded flow at interval end
- command-change flag

## Quantitative result

| Stream | One-minute intervals | Mean actual flow |
|---|---:|---:|
| Acetic acid | 141 | 4.3240 mL/min |
| Sodium acetate | 141 | 3.8914 mL/min |

These are run-wide averages across changing commands. The CSV tables contain
the actual value for every individual interval.

The four-second table contains 2,127 intervals with an average duration of
4.0002 seconds. The one-minute table contains 141 intervals.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_mass_derived_flows.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_mass_derived_flows.py' `
  --output-dir `
  'results/july31_biosmb_schedule_20260731_205921'
```

Results:

- Python compilation passed.
- The four-second export has 2,127 rows and 22 columns.
- The one-minute export has 141 rows and 22 columns.
- Both exports contain zero missing values.
- Acid and sodium interval metadata match exactly.
- Water is absent from both validated actual-flow exports.

## Limitations

- The values are interval-average reservoir-out flows, not instantaneous
  flowmeter readings.
- Four-second values remain sensitive to scale quantization and asynchronous
  scale updates.
- The one-minute values are the more reliable estimates.
- Density should be replaced with measured solution density for calibrated
  accuracy.
- Reservoir-out flow does not include tubing transport delay to the mixer.

## Next experiment

Perform separate five-minute gravimetric holds for each pump at 1, 3, 5, 7,
and 10 mL/min. Use measured solution densities and fit actual flow against
commanded flow to quantify pump gain, bias, repeatability, and nonlinearity.
