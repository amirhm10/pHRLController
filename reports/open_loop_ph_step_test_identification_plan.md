# Open-Loop pH Step-Test Identification Plan

This report defines the next experiment for identifying an input-output model
from BioSMB pump flow commands to the reliable outlet pH measurement, `PH_2`.
It is a planning report for a new dataset and model-identification workflow. It
does not add MPC, RL, reward functions, policies, or autonomous feedback
control.

The experiment should be built around the current project stage:

```text
equilibrium charge balance + empirical PH_2 calibration
```

The current calibrated static chemistry relation is:

$$
\widehat{PH}_{2,static}
= 0.6567 + 0.7909\,pH_{eq}
$$

where \(pH_{eq}\) is computed from the three inlet flows using the equilibrium
charge-balance model. The new experiment should identify the dynamic wrapper
around this static chemistry coordinate.

## Source Context

This plan is based on:

- [BioSMB control library familiarization report](biosmb_control_library_familiarization.md),
- [Equilibrium charge-balance main model report](equilibrium_charge_balance_main_model_report.md),
- [Dynamic model identification report](dynamic_model_identification_report.md),
- [lab data preprocessing helper](../helpers/lab_data.py),
- [pH process configuration](../simulation/config.py),
- [BioSMB manager API](../BIOSMBControlLibrary/biosmb_interface/manager.py),
- [pH expert sketch](../BIOSMBControlLibrary/5_21_2026_demo.py),
- [BioSMB pH presentation](../BIOSMBControlLibrary/Presentation.pptx),
- [current treated lab CSV](../Data/dsp_db.biosmb-rl-controller-treated-dataset.csv).

## Why This Experiment Is Needed

The current lab CSV is useful, but it was not designed for dynamic
identification. The existing reports show:

- raw equilibrium test RMSE is about `0.4412 pH`,
- affine-calibrated equilibrium test RMSE is about `0.0975 pH`,
- integer lag and first-order dynamic wrappers do not improve the held-out
  result,
- the full transport-delay search gives \(V_{tube}^{*} = 0.000\ \mathrm{mL}\),
- regime-specific transport-delay searches find only tiny apparent volumes,
  `0.467 mL` and `1.012 mL`, with no meaningful held-out improvement.

The correct interpretation is not that the hardware has no delay. The safer
interpretation is that the old closed-loop, coarse-sampled dataset cannot
separate static chemistry, delay, mixing, sensor response, session drift, and
operator or controller timing.

The next dataset must therefore be open-loop, supervised, explicitly scheduled,
faster sampled, and long enough for `PH_2` to settle after each step.

## Fixed Project Conventions

Use these names consistently in new code, CSV files, reports, and figures.

| Concept | Recommended variable name | Unit or meaning |
| --- | --- | --- |
| acetic acid command | `acid_flow_cmd_ml_min` | mL/min |
| sodium acetate command | `acetate_flow_cmd_ml_min` | mL/min |
| Arium water command | `water_flow_cmd_ml_min` | mL/min |
| acetic acid pump number | `acid_pump_number` | live pH default: pump 2 |
| sodium acetate pump number | `acetate_pump_number` | live pH default: pump 3 |
| Arium water pump number | `water_pump_number` | live pH default: pump 4 |
| acetic acid readback | `acid_flow_meas_ml_min` | mL/min, from the mapped acid pump |
| sodium acetate readback | `acetate_flow_meas_ml_min` | mL/min, from the mapped acetate pump |
| Arium water readback | `water_flow_meas_ml_min` | mL/min, from the mapped water pump |
| total commanded flow | `total_flow_cmd_ml_min` | sum of three commanded flows |
| total measured flow | `total_flow_meas_ml_min` | sum of three measured/readback flows |
| acid plus acetate flow | `buffer_flow_sum_ml_min` | \(F_H + F_A\) |
| acetate-to-acid ratio | `flow_ratio_acetate_acid` | \(F_A/F_H\) |
| log ratio | `log10_flow_ratio_acetate_acid` | \(\log_{10}(F_A/F_H)\) |
| water fraction | `water_fraction` | \(F_W/F_T\) |
| static chemistry coordinate | `ph_equilibrium_charge_balance` | raw equilibrium pH |
| calibrated static output | `ph_equilibrium_affine` | current empirical `PH_2` prediction |
| reliable measured output | `ph_measured` | output pH from `biosmb.get_ph(2)` |
| outlet pH sensor number | `outlet_ph_sensor_number` | live pH default: `2` |
| outlet pH sensor name | `outlet_ph_sensor_name` | live pH default: `PH_2` |
| raw reliable pH sensor | `PH_2` | BioSMB pH sensor 2 |
| diagnostic pH sensor | `PH_1` | log only, not validation output |
| experiment block | `block_id` | e.g. `ratio_fixed_total`, `total_fixed_composition` |
| step id | `step_id` | integer or short string |
| step type | `step_type` | purpose of the step |
| valve path label | `valve_path_id` | operator-confirmed flow path |
| open valves | `open_valves` | actual valves commanded open |
| outlet verification flag | `outlet_path_verified` | `true` only after physical confirmation |
| sample index | `sample_index` | monotonically increasing integer |
| elapsed time | `elapsed_s` | seconds since run start |
| hold time | `hold_elapsed_s` | seconds since current step start |

Live pH plumbing note, as of May 28, 2026:

- Pump 1 should not be used for this pH experiment because it is reported not
  working.
- The working pH inlet pumps should start at pump 2 and proceed through pump 4:
  pump 2 is acetic acid, pump 3 is sodium acetate, and pump 4 is Arium water.
- The PowerPoint slide visibly lists the pH streams as acetic, sodium acetate,
  and water. The visible `2` extracted from that slide is the slide-number
  placeholder, not an outlet label.
- The expert sketch `5_21_2026_demo.py` opens valves `P2`, `P3`, and `P4`, and
  reads `current_ph = biosmb.get_ph(2)`. This supports `PH_2` as the outlet pH
  measurement and `P2/P3/P4` as a pH-case routing clue, but it does not confirm
  the physical outlet tubing or valve path.
- The valve drawing and BioSMB valve map use lettered columns left-to-right:
  `A, B, ..., P`. Therefore `P2`, `P3`, and `P4` mean the far-right `P` column
  on rows 2, 3, and 4. This is why those valve labels align with the three pH
  inlet rows.
- The outlet path remains unverified. New logs should record the valve path and
  keep `outlet_path_verified = false` until the physical outlet is confirmed.

The historical lab CSV still uses the old recorded columns
`observation.biosmb-flows[0]`, `[1]`, and `[2]` for acid, acetate, and water in
that dataset. Do not reinterpret historical CSV columns as the new live pump
numbers without checking the acquisition mapping for that run.

For compatibility with the existing preprocessing tools, processed analysis
tables can still expose the compact project names:

```text
acid_flow
acetate_flow
water_flow
total_flow
ph_measured
```

Those compact names should be created deliberately from either command values
or measured/readback values. The report or metadata must state which source was
used for model fitting.

## Bounds And Existing Data Ranges

Current configuration:

| Quantity | Value |
| --- | ---: |
| acetic acid stock | `100 mM` |
| sodium acetate stock | `100 mM` |
| acid pump bound | `1-10 mL/min` |
| acetate pump bound | `1-10 mL/min` |
| water pump bound | `1-10 mL/min` |
| useful buffer pH range | about `3.76-5.76` |
| default water flow | `5 mL/min` |
| default acid plus acetate flow | `10 mL/min` |

Observed valid rows in the current CSV have approximately:

| Quantity | Min | Median | Max |
| --- | ---: | ---: | ---: |
| `acid_flow` | `1.0000` | `5.5308` | `9.9710` |
| `acetate_flow` | `1.0000` | `6.0012` | `9.9939` |
| `water_flow` | `1.0000` | `4.8733` | `9.9697` |
| `total_flow` | `3.0000` | `16.3606` | `28.7355` |
| `PH_2` | `3.5717` | `4.4312` | `5.2186` |
| `log10_flow_ratio_acetate_acid` | `-0.9387` | `0.0200` | `0.9417` |

The old data were mostly sampled around `69-70 s` in later runs and
`140-142 s` in early runs. That is too slow to identify second-scale or
tens-of-seconds delay. A new run should target a fixed sample period of
`2-5 s` if the hardware and logging stack allow it. If that is too aggressive,
`10 s` is still much more useful than one-minute sampling.

## Experimental Approach

The experiment should be a supervised open-loop step test. The operator or
script applies a finite schedule of flow commands. No control feedback is used
to choose the next command.

Use four blocks.

### Block 0: One-Pump-At-A-Time Local Steps

This is the simple experiment idea:

```text
start at [3, 3, 3], step one pump to 6, return to [3, 3, 3], then repeat for the next pump
```

It is a good first block because it gives a clean local input-output response
for each manipulated variable near one operating point.

Use:

$$
u_0 =
\begin{bmatrix}
3 \\
3 \\
3
\end{bmatrix}
\ \mathrm{mL/min}
$$

where the vector order is:

$$
u =
\begin{bmatrix}
F_H \\
F_A \\
F_W
\end{bmatrix}
$$

A practical sequence is:

| Step | `step_type` | `acid_flow_cmd_ml_min` | `acetate_flow_cmd_ml_min` | `water_flow_cmd_ml_min` | `total_flow_cmd_ml_min` | Main information |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | `baseline` | `3.00` | `3.00` | `3.00` | `9.00` | initial steady condition |
| 1 | `acid_positive_step` | `6.00` | `3.00` | `3.00` | `12.00` | acid effect plus throughput change |
| 2 | `baseline_return` | `3.00` | `3.00` | `3.00` | `9.00` | recovery and hysteresis check |
| 3 | `acetate_positive_step` | `3.00` | `6.00` | `3.00` | `12.00` | acetate effect plus throughput change |
| 4 | `baseline_return` | `3.00` | `3.00` | `3.00` | `9.00` | recovery and hysteresis check |
| 5 | `water_positive_step` | `3.00` | `3.00` | `6.00` | `12.00` | water, dilution, and residence-time effect |
| 6 | `baseline_return` | `3.00` | `3.00` | `3.00` | `9.00` | final repeat of baseline |

Repeat this block at least twice if lab time allows. Repetition is important
because one pass cannot distinguish true dynamics from drift, slow flushing, or
probe conditioning.

This block supports a local empirical model around \(u_0\):

$$
\Delta y_k =
G_H(q^{-1})\Delta F_{H,k}
+ G_A(q^{-1})\Delta F_{A,k}
+ G_W(q^{-1})\Delta F_{W,k}
+ e_k
$$

where:

$$
\Delta y_k = PH_{2,k} - PH_{2,baseline}
$$

and:

$$
\Delta u_k = u_k - u_0
$$

It also supports the chemistry-aware model because each step changes
\(pH_{eq}\), \(F_T\), or both.

Important limitation:

```text
stepping one pump from 3 to 6 changes both composition and total flow
```

For example, `[6, 3, 3]` changes the acid/acetate ratio and total flow. That is
useful for a local empirical model, but it does not fully separate pH chemistry
from residence-time effects. That is why the following blocks are still needed.

### Block A: pH-Coordinate Steps At Fixed Total Flow

Purpose:

```text
Excite the static chemistry coordinate while keeping total flow approximately constant.
```

Use:

$$
F_H + F_A = 10\ \mathrm{mL/min}
$$

$$
F_W = 5\ \mathrm{mL/min}
$$

so:

$$
F_T = 15\ \mathrm{mL/min}
$$

Choose flow pairs from a desired equilibrium coordinate, not from the logged
controller field `target_ph`. Use the name `design_ph_eq` for the planned
chemistry coordinate:

$$
r = 10^{design\_ph\_eq - pK_a}
$$

$$
F_H = \frac{10}{1+r}
$$

$$
F_A = \frac{10r}{1+r}
$$

A practical within-bounds schedule is:

| `design_ph_eq` | `flow_ratio_acetate_acid` | `acid_flow_cmd_ml_min` | `acetate_flow_cmd_ml_min` | `water_flow_cmd_ml_min` | `total_flow_cmd_ml_min` |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `3.85` | `0.123` | `8.90` | `1.10` | `5.00` | `15.00` |
| `4.15` | `0.245` | `8.03` | `1.97` | `5.00` | `15.00` |
| `4.45` | `0.490` | `6.71` | `3.29` | `5.00` | `15.00` |
| `4.76` | `1.000` | `5.00` | `5.00` | `5.00` | `15.00` |
| `5.07` | `2.042` | `3.29` | `6.71` | `5.00` | `15.00` |
| `5.37` | `4.074` | `1.97` | `8.03` | `5.00` | `15.00` |
| `5.67` | `8.128` | `1.10` | `8.90` | `5.00` | `15.00` |

Run this block in an order that includes both upward and downward changes.
For example:

```text
4.76 -> 4.15 -> 5.07 -> 3.85 -> 5.67 -> 4.45 -> 5.37 -> 4.76
```

This prevents the entire run from being a single monotonic pH drift.

### Block B: Total-Flow Steps At Fixed Composition

Purpose:

```text
Excite residence-time and flushing effects while keeping composition approximately constant.
```

Use equal acid, acetate, and water flows:

| Step | `acid_flow_cmd_ml_min` | `acetate_flow_cmd_ml_min` | `water_flow_cmd_ml_min` | `total_flow_cmd_ml_min` |
| --- | ---: | ---: | ---: | ---: |
| low throughput | `3.00` | `3.00` | `3.00` | `9.00` |
| middle throughput | `5.00` | `5.00` | `5.00` | `15.00` |
| high throughput | `8.00` | `8.00` | `8.00` | `24.00` |

The chemistry ratio stays near `1`, but total flow changes strongly. If the
delay or mixing time scales with transported volume, the response speed should
change with \(F_T\).

### Block C: Water-Fraction Steps At Fixed Acid/Acetate Ratio

Purpose:

```text
Separate pH-ratio chemistry from dilution, ionic strength, conductivity, and throughput.
```

Use fixed acid and acetate flows:

| Step | `acid_flow_cmd_ml_min` | `acetate_flow_cmd_ml_min` | `water_flow_cmd_ml_min` | `total_flow_cmd_ml_min` |
| --- | ---: | ---: | ---: | ---: |
| low water | `5.00` | `5.00` | `1.00` | `11.00` |
| middle water | `5.00` | `5.00` | `5.00` | `15.00` |
| high water | `5.00` | `5.00` | `10.00` | `20.00` |

In ideal equal-stock Henderson-Hasselbalch chemistry, these steps should not
strongly change the acid/acetate pH ratio. In the real hardware, they may
change buffer strength, conductivity, residence time, flushing, and sensor
behavior.

## Hold Time And Sampling

Each step should have:

- a minimum hold time, such as `10 min`,
- a slope-based settling check, such as \(|d PH_2 / dt| < 0.005\ \mathrm{pH/min}\)
  over the last `3-5 min`,
- a maximum hold time, such as `20 min`, so the experiment is finite,
- a fixed sample period, ideally `2-5 s`,
- no closed-loop adjustment of flows during the hold.

The first few samples after a command change are especially important. The
previous dataset could not resolve delay because one logged sample was often
about one minute apart. The new dataset should capture enough samples inside
the first minute after each step.

## Logging Schema

The new raw experiment log should be immutable. Save it as a timestamped CSV
under `Data/`, and save processed tables and figures under a timestamped
`results/open_loop_ph_identification_<YYYYMMDD_HHMMSS>/` folder.

Required raw fields:

| Field | Why it is needed |
| --- | --- |
| `utc_time` | absolute alignment and reproducibility |
| `sample_index` | monotonic order check |
| `elapsed_s` | dynamic model fitting |
| `session_id` | session-level calibration or drift grouping |
| `block_id` | separates ratio, throughput, and water-fraction tests |
| `step_id` | segmentation for step-response fitting |
| `step_type` | documents the intended excitation |
| `hold_elapsed_s` | time since current step started |
| `acid_pump_number` | BioSMB pump number for acetic acid, live default 2 |
| `acetate_pump_number` | BioSMB pump number for sodium acetate, live default 3 |
| `water_pump_number` | BioSMB pump number for Arium water, live default 4 |
| `acid_inlet_row` | operator-confirmed inlet row or tube label, if available |
| `acetate_inlet_row` | operator-confirmed inlet row or tube label, if available |
| `water_inlet_row` | operator-confirmed inlet row or tube label, if available |
| `acid_flow_cmd_ml_min` | commanded acid input |
| `acetate_flow_cmd_ml_min` | commanded acetate input |
| `water_flow_cmd_ml_min` | commanded water input |
| `acid_flow_meas_ml_min` | readback or measured acid input |
| `acetate_flow_meas_ml_min` | readback or measured acetate input |
| `water_flow_meas_ml_min` | readback or measured water input |
| `total_flow_cmd_ml_min` | residence-time coordinate |
| `total_flow_meas_ml_min` | readback residence-time coordinate |
| `buffer_flow_sum_ml_min` | acid plus acetate scale |
| `flow_ratio_acetate_acid` | main pH-ratio coordinate |
| `log10_flow_ratio_acetate_acid` | linearized ratio coordinate |
| `water_fraction` | dilution coordinate |
| `ph_equilibrium_charge_balance` | raw chemistry coordinate |
| `ph_equilibrium_affine` | current calibrated static prediction |
| `ph_measured` | outlet pH value read with `biosmb.get_ph(2)` |
| `outlet_ph_sensor_number` | pH sensor number used for `ph_measured`, default 2 |
| `outlet_ph_sensor_name` | pH sensor name used for `ph_measured`, default `PH_2` |
| `PH_2` | reliable pH sensor |
| `PH_1` | diagnostic pH sensor only |
| `COND_1` through `COND_4` | dilution and stream-change diagnostics |
| `P_1` through `P_7` | pressure and blockage diagnostics |
| `valve_path_id` | reproducibility of routing |
| `open_valves` | audit of actual route |
| `outlet_path_verified` | whether the outlet path has been physically confirmed |
| `settings_file` | OPC node mapping used |
| `operator_note` | calibration, tubing, or routing notes |

The processed analysis table should map:

```text
biosmb.get_ph(2) or PH_2 -> ph_measured
acid_flow_meas_ml_min or acid_flow_cmd_ml_min -> acid_flow
acetate_flow_meas_ml_min or acetate_flow_cmd_ml_min -> acetate_flow
water_flow_meas_ml_min or water_flow_cmd_ml_min -> water_flow
```

Prefer measured/readback flows if they are reliable and synchronized. Use
commanded flows only if readback is unavailable or demonstrably less reliable.

## Mathematical Identification Model

The manipulated input vector is:

$$
u(t) =
\begin{bmatrix}
F_H(t) \\
F_A(t) \\
F_W(t)
\end{bmatrix}
$$

The reliable output is:

$$
y(t) = PH_2(t)
$$

The static chemistry coordinate is:

$$
pH_{eq}(t) =
f_{eq}(F_H(t), F_A(t), F_W(t))
$$

where \(f_{eq}\) is the equilibrium charge-balance root solve.

The current static measurement map is:

$$
y_{static}(t) =
b_0 + b_1pH_{eq}(t)
$$

with current CSV values:

$$
b_0 = 0.6567
$$

$$
b_1 = 0.7909
$$

For new data, \(b_0\) and \(b_1\) should be refit first. The old values should
be logged as a reference, not treated as permanent hardware constants.

The first dynamic model to identify should be a first-order-plus-dead-time
wrapper:

$$
\tau_{eff}\frac{d\hat{y}}{dt}
= y_{static}(t-\theta) - \hat{y}(t)
$$

A more physical volume-based version should be tested after that:

$$
\theta(t) = 60\frac{V_{delay}}{F_T(t)}
$$

$$
\tau_{mix}(t) = 60\frac{V_{mix}}{F_T(t)}
$$

where \(V_{delay}\) and \(V_{mix}\) are in mL, \(F_T\) is in mL/min, and the
resulting time constants are in seconds.

A two-stage dynamic wrapper can then separate mixing from probe response:

$$
\tau_{mix}(t)\frac{dx_{mix}}{dt}
= y_{static}(t-\theta(t)) - x_{mix}(t)
$$

$$
\tau_s\frac{d\hat{y}}{dt}
= x_{mix}(t) - \hat{y}(t)
$$

where \(\tau_s\) is the pH sensor response time. If the data cannot separate
\(\tau_{mix}\) and \(\tau_s\), use a single aggregate \(\tau_{eff}\) and state
that separation is not identifiable.

## What The Simulation Should Account For

The simulation model should be an input-output process model, not a controller.
It should live under `simulation/` and expose a deterministic prediction from a
flow schedule to `PH_2`.

Minimum simulation components:

1. Flow input validation and clipping using `PHProcessConfig`.
2. Static equilibrium charge-balance chemistry.
3. Refit affine measurement calibration for the new open-loop data.
4. Variable transport delay based on total flow and transported volume.
5. Mixing or residence-time lag based on total flow.
6. pH sensor first-order response.
7. Optional session-level pH bias term if repeated center steps show drift.
8. Optional measurement noise model estimated from steady holds.
9. Explicit sample time handling for irregular or missing samples.
10. Clear distinction between command values and measured/readback values.

Recommended model class names:

```text
DynamicPHProcessModel
EquilibriumPHStaticMap
TransportDelayBuffer
FirstOrderPHResponse
OpenLoopPHStepSchedule
```

Recommended module names:

```text
simulation/dynamic_ph_process_model.py
helpers/open_loop_ph_data.py
helpers/open_loop_ph_identification.py
helpers/open_loop_ph_plotting.py
run_open_loop_ph_identification_analysis.py
```

Do not put hardware writes in `simulation/`. Hardware execution should remain
in a separate runner that wraps `BioSMBManager`.

## Hardware Runner Approach

Create a separate script only after the schedule is reviewed:

```text
run_open_loop_ph_identification_experiment.py
```

It should:

1. Load a reviewed step schedule from CSV or YAML.
2. Require an explicit `settings_file`.
3. Require an explicit endpoint, with emulator and hardware modes clearly
   separated.
4. Print the full planned schedule before any hardware write.
5. Confirm pump-to-stream mapping before the run.
6. Reset the system with `zero_all_flows()`, `disable_all_pumps()`, and
   `close_all_valves()`.
7. Configure the verified valve path. The pH expert sketch used `P2`, `P3`,
   and `P4`, meaning the far-right `P` column on stream rows 2, 3, and 4, but
   the physical outlet tubing still needs confirmation.
8. Enable only pumps 2, 3, and 4 by default because pump 1 is reported not
   working for this pH setup.
9. Apply bounded flow commands using `set_flow()`.
10. Poll `get_all_sensors()` and `get_all_flows()` at the requested sample
    period.
11. Compute and log `ph_equilibrium_charge_balance` and
    `ph_equilibrium_affine` for each command or readback.
12. Always clean up in `finally`.

The low-level BioSMB methods already available are:

```text
open_valve()
close_valve()
get_all_valves()
set_flow()
get_all_flows()
zero_all_flows()
enable_pump()
disable_pump()
disable_all_pumps()
get_ph(2)
get_all_sensors()
print_status()
```

The existing `5_21_2026_demo.py` should not be used directly for this
experiment. It is useful as a sketch only.

## Analysis Workflow After The Experiment

After collecting the new CSV:

1. Copy the raw CSV into `Data/` and do not edit it.
2. Load and normalize names with a new helper, for example
   `helpers/open_loop_ph_data.py`.
3. Save preprocessed tables in
   `results/open_loop_ph_identification_<YYYYMMDD_HHMMSS>/tables/`.
4. Recompute \(pH_{eq}\), \(y_{static}\), and derived flow coordinates.
5. Split by step or repeated transition, not by individual adjacent samples.
6. Fit static calibration on training steps.
7. Fit delay and dynamic parameters on training steps.
8. Validate on held-out steps and repeated reverse-direction transitions.
9. Save metrics by split, block, step type, and pH range.
10. Save figures in
    `results/open_loop_ph_identification_<YYYYMMDD_HHMMSS>/figures/`.
11. Write a scientific report with equations, figures, metrics, limitations,
    and next actions.

Minimum metrics:

| Metric | Purpose |
| --- | --- |
| RMSE, MAE, mean error, max absolute error | overall prediction accuracy |
| step final offset | checks steady-state calibration |
| time-to-90-percent response | response speed |
| settling time | whether holds are long enough |
| overshoot or undershoot | sensor or mixing dynamics |
| residual by step type | identifies missing mechanisms |
| residual by total flow | tests volume-based dynamics |
| residual by water fraction | tests dilution or sensor effects |
| delay RMSE search curve | checks identifiability of \(V_{delay}\) |

Minimum figures:

- command and readback flow trajectories,
- `PH_2`, `ph_equilibrium_charge_balance`, and `ph_equilibrium_affine` over
  time,
- one panel per step block with command changes marked,
- measured versus predicted scatter for static and dynamic models,
- residual time plot with step labels,
- residual histogram by model stage,
- delay or volume search curve,
- response-speed summary versus total flow,
- repeated center-condition drift plot.

## Decision Criteria

The new dynamic model is useful only if it improves more than the current
static calibrated baseline and behaves physically.

Minimum success criteria:

- dynamic test RMSE improves by at least `0.02 pH` over static calibration, or
  by at least `20%` relative RMSE,
- held-out step final offsets are mostly within `0.05-0.10 pH`,
- fitted delay or mixing parameters are stable across repeated transitions,
- response speed changes sensibly with total flow,
- residuals do not show a systematic bias by pH range, total flow, or water
  fraction,
- `PH_2` visibly settles during most holds.

If these criteria are not met, the model should remain a diagnostic tool, not a
plant simulator for controller design.

## Total Work Plan

Recommended implementation sequence:

1. Create `experiments/open_loop_ph_step_schedule.csv` with the reviewed flow
   schedule.
2. Create `run_open_loop_ph_identification_experiment.py` as a hardware-facing
   runner with dry-run mode, endpoint selection, bounds checks, logging, and
   cleanup.
3. Create `helpers/open_loop_ph_data.py` for loading and normalizing the new
   CSV.
4. Create `simulation/dynamic_ph_process_model.py` for static chemistry plus
   delay, mixing, and sensor response.
5. Create `helpers/open_loop_ph_identification.py` for fitting static,
   transport-delay, and first-order parameters.
6. Create `helpers/open_loop_ph_plotting.py` for standard figures.
7. Create `run_open_loop_ph_identification_analysis.py` for reproducible
   post-experiment analysis.
8. Save all generated outputs under timestamped `results/` folders.
9. Write a follow-up report comparing static, delay, and dynamic models.
10. Consider feedback control only after this model predicts `PH_2` reliably
    on held-out open-loop steps.

## Risks And Controls

Main risks:

- pump-to-stream mapping mismatch,
- wrong valve path,
- using `PH_1` as a validation output,
- sampling too slowly,
- holds too short for settling,
- calibration drift during the run,
- command values not matching flow readbacks,
- dynamic parameters fitting noise rather than transport physics,
- accidentally turning a step-test script into a feedback controller.

Controls:

- verify pump and valve mapping before the run,
- log both commands and readbacks,
- keep `PH_1` diagnostic only,
- force a fixed sample period,
- include repeated center steps,
- include both upward and downward pH-coordinate steps,
- save operator notes and physical tubing metadata,
- use held-out steps for validation,
- keep the experiment finite and supervised,
- use `try/finally` cleanup for every hardware run.

## Bottom Line

The next experiment should not try to control pH. It should create the first
clean open-loop dynamic dataset for the inline acetate-buffer system. The
central model coordinate is still the equilibrium charge-balance pH, corrected
to the `PH_2` scale. The experiment should identify what happens between that
static chemistry coordinate and the measured sensor:

```text
flow commands -> equilibrium chemistry -> delay -> mixing -> pH sensor -> PH_2
```

That is the missing bridge between the current static model evidence and any
future safe controller design.
