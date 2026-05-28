# BioSMB Control Library Familiarization Report

This report explains the local `BIOSMBControlLibrary` folder as an experiment-facing interface for the BioSMB hardware. The immediate purpose is not to add MPC, RL, or autonomous feedback control. The safer next use is supervised and open-loop pH experiment design that produces cleaner dynamic identification data for the inline acetate-buffer system.

The experiment design in this report should be built around the current main chemistry model:

```text
equilibrium charge balance + empirical PH_2 calibration
```

The older ideal Henderson-Hasselbalch ratio is useful only as intuition for choosing acid/acetate steps. It should not be treated as the main plant model.

The relevant local library folder is:

```text
BIOSMBControlLibrary/
```

The library is a thin Python wrapper around OPC-UA nodes. It can open and close valves, set pump flowrates, enable pumps, read sensors, and print the current valve/pump layout. Because these calls can move real hardware when pointed at the lab OPC endpoint, the scripts should be treated as hardware-facing experiment tools, not ordinary offline analysis scripts.

## Source Files Inspected

| File | Role |
| --- | --- |
| [`BIOSMBControlLibrary/biosmb_interface/manager.py`](../BIOSMBControlLibrary/biosmb_interface/manager.py) | Main `BioSMBManager` API for valves, pumps, and sensors |
| [`BIOSMBControlLibrary/biosmb_interface/enum.py`](../BIOSMBControlLibrary/biosmb_interface/enum.py) | `ValveState` and `PumpEnabledState` enumerations |
| [`BIOSMBControlLibrary/biosmb_interface/utility.py`](../BIOSMBControlLibrary/biosmb_interface/utility.py) | Text status rendering for valves, inlet labels, outlet labels, and flows |
| [`BIOSMBControlLibrary/settings.json`](../BIOSMBControlLibrary/settings.json) | OPC-UA node-id map for the real BioSMB-facing configuration |
| [`BIOSMBControlLibrary/quick_test.py`](../BIOSMBControlLibrary/quick_test.py) | Short real-hardware test script using one pump, three valves, and a UV read |
| [`BIOSMBControlLibrary/demo_script.py`](../BIOSMBControlLibrary/demo_script.py) | Emulator-oriented chromatography breakthrough script |
| [`BIOSMBControlLibrary/5_21_2026_demo.py`](../BIOSMBControlLibrary/5_21_2026_demo.py) | pH read-loop sketch for the 2026 pH experiment |
| [`BIOSMBControlLibrary/2024_09_17_UVIntegration.py`](../BIOSMBControlLibrary/2024_09_17_UVIntegration.py) | Periodic BioSMB and UV-spectrum logging to MongoDB |
| [`BIOSMBControlLibrary/opc_emulator/`](../BIOSMBControlLibrary/opc_emulator/) | OPC-UA emulator used for non-hardware testing |
| [`BIOSMBControlLibrary/docs/`](../BIOSMBControlLibrary/docs/) | Sphinx docs generated from the package docstrings |
| [`BIOSMBControlLibrary/Presentation.pptx`](../BIOSMBControlLibrary/Presentation.pptx) | Small deck. The visible text indicates the pH setup streams: acetic, Na acetate, and water |
| [`simulation/equilibrium_charge_balance_model.py`](../simulation/equilibrium_charge_balance_model.py) | Main first-principles chemistry core for the pH project |
| [`reports/equilibrium_charge_balance_main_model_report.md`](equilibrium_charge_balance_main_model_report.md) | Current evidence and generated data for the equilibrium main model |

## What The Library Is Doing

The main object is `BioSMBManager`. It is constructed from an already-open synchronous OPC-UA client:

```python
from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager

with Client(url="opc.tcp://192.168.0.2:4840") as client:
    biosmb = BioSMBManager(client)
```

This manager does not own the connection lifecycle. The calling script opens the OPC-UA connection with `asyncua.sync.Client`, creates `BioSMBManager`, performs hardware reads or writes, and then exits the client context.

The library has four conceptual layers:

1. OPC-UA connection: created by `asyncua.sync.Client`.
2. Node-id configuration: loaded from `settings.json`.
3. Hardware wrapper: `BioSMBManager` maps friendly methods onto OPC reads and writes.
4. User scripts: experiment scripts choose valve paths, pump flows, sensor polling, and logging.

The current implementation is intentionally direct. It does not include experiment scheduling, safety interlocks, flow bounds, automatic cleanup, database schemas, model prediction, or feedback-control logic.

## Configuration And Hardware Map

`settings.json` maps named BioSMB signals to OPC-UA node ids:

| Signal group | Node mapping |
| --- | --- |
| Valve byte arrays | `YV_AD_1`, `YV_EH_1`, `YV_IL_1`, `YV_MP_1` |
| Pump flows | `FLOW` mapped to `.PUMP.FLOW` |
| Pump enables | `EN` mapped to `.PUMP.EN` |
| Pressures | `P_1` through `P_7` |
| pH sensors | `PH_1`, `PH_2` |
| Conductivity | `COND_1` through `COND_4` |
| UV channels | `UV_1A` through `UV_4C` through nested `A`, `B`, `C` keys |

For this pH project, the existing data-analysis convention says:

- `PH_2` is the reliable measured outlet pH.
- `PH_1` should not be used for model-validation metrics unless the hardware state has changed and is explicitly verified.
- The project data mapping treats flow channel 1 as acetic acid, flow channel 2 as sodium acetate, and flow channel 3 as water. In this live library, the pump-to-stream mapping must still be confirmed against the actual plumbing before any experiment script assumes it.

Current live pH setup clarification, as of May 28, 2026:

- Pump 1 should not be used because it is reported not working.
- The working inlet pumps are pump 2 for acetic acid, pump 3 for sodium acetate,
  and pump 4 for Arium water.
- The outlet pH measurement should use `current_ph = biosmb.get_ph(2)`, i.e.,
  pH sensor `PH_2`.
- The valve grid is addressed as column letter plus row number. Columns run
  left-to-right from `A` through `P`, so the expert sketch's `P2`, `P3`, and
  `P4` commands open the far-right `P` column on the three pH inlet rows.
- The physical outlet tubing or valve path is still not fully verified by the
  presentation or the demo sketch, so scripts should log the open valves and
  keep the outlet path marked unverified until the hardware route is confirmed.

The current lab CSV confirms the same active flow channels:

| Project variable | Physical stream | CSV column | BioSMB flow channel |
| --- | --- | --- | --- |
| `acid_flow` | acetic acid, 100 mM | `observation.biosmb-flows[0]` | pump/flow 1 |
| `acetate_flow` | sodium acetate, 100 mM | `observation.biosmb-flows[1]` | pump/flow 2 |
| `water_flow` | Arium water | `observation.biosmb-flows[2]` | pump/flow 3 |
| `PH_2` | outlet pH after the routed mixing path | `observation.biosmb-sensors.PH_2` | pH sensor 2 |

Flow channels `observation.biosmb-flows[3]` through `observation.biosmb-flows[6]` are zero in the current CSV and are not part of the pH mixing model. The dataset does not contain a separate outlet-flow column, so outlet behavior is represented by the valve path and the reliable outlet pH measurement `PH_2`.

The manager default is `settings_file="settings.json"`. That means scripts are sensitive to the working directory. If a script is launched from the repository root instead of from `BIOSMBControlLibrary/`, the default settings path may not resolve unless the script passes:

```python
BioSMBManager(client, settings_file="BIOSMBControlLibrary/settings.json")
```

## Valve API

The BioSMB valve block is addressed by friendly names such as `A2`, `P15`, or `D11`.

The implementation creates a map over:

$$
16 \text{ columns} \times 15 \text{ rows} = 240 \text{ valves}
$$

Columns are letters `A` through `P`. Rows are numbered `1` through `15`, matching the physical row labels rather than zero-based Python indexing.

Internally, valves are stored in four OPC byte-array nodes. Each valve maps to:

- one OPC node id,
- one byte-array index,
- one bit inside that byte.

The key methods are:

| Method | Meaning |
| --- | --- |
| `get_valve(valve_name)` | Read one valve state |
| `set_valve(valve_name, ValveState.OPEN/CLOSED)` | Write one valve state |
| `open_valve(valve_name)` | Convenience wrapper for opening one valve |
| `close_valve(valve_name)` | Convenience wrapper for closing one valve |
| `get_all_valves()` | Efficiently read all 240 valve states |
| `close_all_valves()` | Write zeros to all four valve byte arrays |

Important implementation detail: `get_all_valves()` minimizes network calls by reading the four byte arrays once and then decoding all 240 valve bits locally. This is better than calling `get_valve()` in a loop during a status update.

There is no explicit validation for invalid names such as `Q1`, `A0`, or `A16`. Invalid names will fail through dictionary lookup or lower-level indexing. Experiment scripts should validate valve names before touching hardware.

## Pump API

The pump API is one-indexed. Pump numbers are `1` through `7`, not `0` through `6`.

The main methods are:

| Method | Meaning |
| --- | --- |
| `get_flow(pump_number)` | Read one pump flow setpoint in mL/min |
| `set_flow(pump_number, flow_rate)` | Write one pump flow setpoint in mL/min |
| `set_all_flows(flow_values)` | Write all seven pump flow setpoints |
| `get_all_flows()` | Read all seven pump flow setpoints |
| `zero_all_flows()` | Set all seven flow setpoints to `0.0` |
| `get_pump_enabled(pump_number)` | Read whether one pump is enabled |
| `set_pump_enabled(pump_number, state)` | Write one pump enable state |
| `enable_pump(pump_number)` | Enable one pump |
| `disable_pump(pump_number)` | Disable one pump |
| `enable_all_pumps()` | Enable all seven pumps |
| `disable_all_pumps()` | Disable all seven pumps |

The code writes flow values to a float array and enable values to a boolean array. The documentation notes that pumps must be enabled to actually run.

For pH experiments, pump flow should be treated as the manipulated input:

$$
u_k =
\begin{bmatrix}
F_H(k) \\
F_A(k) \\
F_W(k)
\end{bmatrix}
$$

where:

- \(F_H\) is acetic acid flow,
- \(F_A\) is sodium acetate flow,
- \(F_W\) is water flow.

The current nominal project bounds are:

$$
1 \le F_H, F_A, F_W \le 10 \quad \text{mL/min}
$$

The library itself does not enforce these bounds. A pH experiment runner should enforce them before calling `set_flow()` or `set_all_flows()`.

## Sensor API

The sensor API is also one-indexed:

| Method | Meaning |
| --- | --- |
| `get_pressure(sensor_number)` | Read pressure sensor `P_1` through `P_7` |
| `get_ph(sensor_number)` | Read pH sensor `PH_1` or `PH_2` |
| `get_conductivity(sensor_number)` | Read conductivity sensor `COND_1` through `COND_4` |
| `get_uv(sensor_number)` | Read one UV sensor as `{"A": value, "B": value, "C": value}` |
| `get_all_sensors()` | Read all pressure, pH, conductivity, and UV values into one dictionary |

For this project, the output of interest is:

$$
y_k = PH_2(k)
$$

The standard input-output record for future pH identification should include at least:

```text
utc_time
elapsed_s
acid_flow
acetate_flow
water_flow
total_flow
PH_2
PH_1
conductivity channels
pressure channels
valve path
experiment_step_id
operator notes
```

`PH_1` can still be logged as a diagnostic, but it should not be used as the reliable model output unless the physical sensor state is revalidated.

## Status Printing

`utility.py` turns valve states and flow values into a text layout. `BioSMBManager.print_status()` calls:

```python
valve_state = self.get_all_valves()
flows = self.get_all_flows()
print_status_text(valve_state, flows, self.inlet_names, self.outlet_names)
```

The optional `inlet_names` and `outlet_names` are display labels only. They do not change any hardware mapping.

For a pH experiment, a useful label set would be:

```python
inlet_names = [
    "Acetic acid",
    "Sodium acetate",
    "Water",
    "",
    "",
    "",
    "",
]
```

Only use these labels if they match the actual pump tubing.

## OPC Emulator

The `opc_emulator/` folder contains an async OPC-UA server that simulates:

- four valve byte arrays,
- seven pump flow setpoints,
- seven pump enables,
- seven pressures,
- four conductivity readings,
- two pH readings,
- four UV sensors with three channels each.

It updates fake sensor values every second with random values. This is useful for testing whether a script can connect, write valves, write flows, read sensors, and print status without touching hardware.

Important limitation: the emulator is not a pH process model. It does not simulate acid-base chemistry, mixing, tubing delay, pH probe response, or flow-dependent dynamics. It is an interface emulator, not a plant emulator.

There is also a likely node-id mismatch between the emulator and the default `settings.json`:

- `settings.json` uses namespace `ns=4` and valve ids with leading dots such as `.Discrete_Out.YV_AD_1`.
- The emulator constructs ids using its registered namespace and includes a space in strings like `ns={id}; s=PUMP.FLOW`.
- `settings.json` uses UV tags such as `UA_1A`, while the emulator creates `UV_1A`.

Because of this, `demo_script.py` may not work against the emulator without a dedicated emulator settings file or corrected emulator node ids.

## Demo Script Walkthroughs

### `quick_test.py`

`quick_test.py` connects to the real BioSMB endpoint:

```text
opc.tcp://192.168.0.2:4840
```

It chooses column `A`, opens valves `A2`, `A9`, and `A15`, prints status, enables pump 1, sets pump 1 to `2.5 mL/min`, reads UV sensor 1, waits 15 seconds, then zeros flows and closes all valves.

This script is a compact hardware smoke test. It shows the basic usage pattern:

1. connect to OPC-UA,
2. construct `BioSMBManager`,
3. open valves,
4. enable pump,
5. set flow,
6. read sensor,
7. stop flow,
8. close valves.

Risk: it does not use `try/finally`. If an exception happens after the pump is enabled or after flow is set, cleanup may not run. For hardware-facing scripts, cleanup should be guaranteed.

### `demo_script.py`

`demo_script.py` connects to:

```text
opc.tcp://localhost:4842
```

This is intended for the local OPC emulator. It labels inlets and outlets, resets flows and valves, opens valves `A5` and `A11`, enables all pumps, starts pump 4 at `2.5 mL/min`, and waits until UV sensor 1 channel `A` exceeds `2.9`. Then it stops pump 4, changes the valve path, starts pump 3, prints status, and waits.

This is a chromatography-style breakthrough example, not a pH experiment. The control logic is event-based:

$$
\text{advance step when } UV_{1A} > 2.9
$$

Risk: the loop can run forever if the UV threshold is never reached. It also has no final cleanup and enables all pumps even though only pump 4 and then pump 3 are used.

### `5_21_2026_demo.py`

This file appears to be the first pH-control experiment sketch. It connects to the real BioSMB endpoint, creates `BioSMBManager`, enables all pumps, opens valves `P2`, `P3`, and `P4`, sets pump 1 and pump 2 to `2.0 mL/min`, and then reads `PH_2` every 15 seconds.

Conceptually, this script is pointing in the right direction for pH work because it reads:

```python
current_ph = biosmb.get_ph(2)
```

For the current live pH setup, this `get_ph(2)` line should be treated as the
outlet pH measurement. The pump writes in the sketch should not be copied
directly because pump 1 is reported not working and the intended pH inlets are
pumps 2, 3, and 4 in the order acetic acid, sodium acetate, and water.
The valve commands are more useful: because columns run left-to-right from
`A` to `P`, `P2`, `P3`, and `P4` select the far-right `P` column on the three
pH inlet rows.

However, it is not safe or runnable as written:

- `inlet_names` is undefined.
- `outlet_names` is undefined.
- `time` is not imported.
- there is no `if __name__ == "__main__":` guard.
- it enables all pumps, not only the pumps required for the experiment.
- it has an infinite loop.
- it has no timeout.
- it has no `try/finally` cleanup.
- it does not zero flows, disable pumps, or close valves at exit.
- it does not log data to a file or database.

This file should be treated as a sketch, not a lab-ready experiment runner.

### `2024_09_17_UVIntegration.py`

This script connects to two OPC-UA servers:

- BioSMB at `opc.tcp://192.168.0.2:4840`
- UV server at `opc.tcp://192.168.0.162:4841`

Every 10 seconds, it reads all BioSMB sensors, all BioSMB flows, UV time, and UV spectrum, then inserts an observation into MongoDB:

```text
mongodb://localhost:27017/
database: UVTest
collection: observations
```

This is the closest existing pattern for structured data logging. For pH work, the same idea should be adapted to a pH experiment table or collection with explicit metadata:

- valve path,
- pump-to-stream map,
- flow command,
- sample time,
- target step label if any,
- measured `PH_2`,
- cleanup status.

Risk: it repeatedly opens OPC clients and MongoDB clients inside an infinite loop. A future experiment runner should preferably open long-lived connections once, log inside the loop, and close cleanly at the end.

## Equilibrium Model Interpretation For pH Experiments

For the inline acetate-buffer system, the manipulated inputs are the three inlet flowrates:

$$
u(t) =
\begin{bmatrix}
F_H(t) \\
F_A(t) \\
F_W(t)
\end{bmatrix}
$$

The reliable measured output is:

$$
y(t) = PH_2(t)
$$

The main first-principles chemistry coordinate is the equilibrium charge-balance pH:

$$
pH_{eq}(t) = -\log_{10}(H(t))
$$

where \(H(t)\) is found by solving an electroneutrality equation after mixing the three inlet streams.

The total flow is:

$$
F_T(t) = F_H(t) + F_A(t) + F_W(t)
$$

With 100 mM acetic acid stock and 100 mM sodium acetate stock, the mixed analytical concentrations are:

$$
C_H(t) = C_{H,0}\frac{F_H(t)}{F_T(t)}
$$

$$
C_A(t) = C_{A,0}\frac{F_A(t)}{F_T(t)}
$$

The total acetate-family concentration is:

$$
C_T(t) = C_H(t) + C_A(t)
$$

The sodium concentration contributed by sodium acetate is:

$$
C_{Na}(t) = C_A(t)
$$

For acetic acid:

$$
K_a = 10^{-pK_a}
$$

The acetate concentration implied by acid-base equilibrium is:

$$
A^{-}(t) = \frac{C_T(t)K_a}{K_a + H(t)}
$$

Water self-ionization contributes:

$$
OH^{-}(t) = \frac{K_w}{H(t)}
$$

The charge-balance residual is:

$$
f(H(t)) =
H(t) + C_{Na}(t)
- \frac{C_T(t)K_a}{K_a + H(t)}
- \frac{K_w}{H(t)}
$$

The model solves:

$$
f(H(t)) = 0
$$

and then maps the raw equilibrium pH to the observed `PH_2` scale using the current empirical calibration:

$$
\widehat{PH}_2(t) =
0.6567 + 0.7909\,pH_{eq}(t)
$$

This calibration is based on the current lab CSV and should be rechecked after new tubing, sensor calibration, valve routing, or reagent changes.

The ideal Henderson-Hasselbalch expression:

$$
pH_{HH}(t) =
pK_a + \log_{10}\left(\frac{F_A(t)}{F_H(t)}\right)
$$

is still useful as a simple way to choose acid/acetate ratios during step-test design. It is not the main model. The main model is the charge-balance calculation because it keeps water, dilution, total buffer concentration, sodium charge, and total flow explicitly in the chemistry coordinate.

A physical delay model would have the form:

$$
\theta(t) \approx 60\frac{V_{tube}}{F_T(t)}
$$

where \(\theta(t)\) is in seconds if \(V_{tube}\) is in mL and \(F_T(t)\) is in mL/min.

The existing lab-data analysis found that the current CSV does not identify a trustworthy nonzero transport volume at the logged sample rate. Therefore, the next use of this library should be to create a cleaner open-loop dataset that can separate equilibrium chemistry, affine `PH_2` calibration, transport delay, mixing dynamics, and sensor response.

## Safe pH Experiment Pattern

A pH experiment script should use this sequence:

1. Connect to the BioSMB OPC-UA server.
2. Construct `BioSMBManager` with an explicit `settings_file`.
3. Confirm pump-to-stream mapping and valve path before writing any values.
4. Reset hardware state:
   - `zero_all_flows()`
   - `disable_all_pumps()`
   - `close_all_valves()`
5. Configure the intended valve path.
6. Enable only the required pumps.
7. Apply bounded flow setpoints.
8. Compute and log the raw equilibrium prediction and calibrated equilibrium prediction for the commanded flows.
9. Poll sensors at a fixed sampling period.
10. Log timestamped observations.
11. Always clean up in `finally`.

The cleanup block should be treated as mandatory:

```python
try:
    # configure valves, enable selected pumps, set bounded flows,
    # compute equilibrium predictions, and log PH_2
    ...
finally:
    biosmb.zero_all_flows()
    biosmb.disable_all_pumps()
    biosmb.close_all_valves()
```

The pH project should avoid autonomous control at this stage. A human-supervised script can step through planned flow commands and log responses. That creates data suitable for identifying delay, mixing/residence-time, and sensor-response parameters.

## Proposed First pH Experiment

The next experiment should be open-loop dynamic identification.

Purpose:

```text
Estimate the relationship from acid, acetate, and water flow commands to PH_2,
including delay, mixing dynamics, and sensor response.
```

Use two kinds of steps.

First, equilibrium-coordinate steps at fixed total flow. Practically, this means changing the acid/acetate ratio while keeping total flow approximately constant:

$$
\frac{F_A}{F_H} \text{ changes}, \quad F_T \text{ approximately constant}
$$

This excites the equilibrium pH coordinate while reducing confounding from total residence time.

Second, total-flow or water-flow steps at fixed acid/acetate ratio:

$$
\frac{F_A}{F_H} \text{ approximately constant}, \quad F_T \text{ changes}
$$

This tests whether water and total flow affect delay, flushing, dilution sensitivity, or sensor dynamics.

Recommended data to log at each sample:

| Field | Reason |
| --- | --- |
| absolute timestamp | aligns OPC reads and later CSV analysis |
| elapsed time | supports dynamic model fitting |
| commanded acid flow | model input |
| commanded acetate flow | model input |
| commanded water flow | model input |
| total flow | dilution and residence-time coordinate |
| raw `pH_eq` | first-principles equilibrium chemistry coordinate |
| calibrated equilibrium `PH_2` prediction | current empirical expected `PH_2` before dynamics |
| measured all flows | detects command/readback mismatch if available |
| `PH_2` | reliable pH output |
| `PH_1` | diagnostic only |
| conductivity channels | dilution and stream-change diagnostic |
| pressure channels | blockage or flow-path diagnostic |
| valve states or valve path label | reproducibility |
| step id and step target | segmentation |
| operator notes | captures calibration, tubing, or routing changes |

Hold each step long enough for `PH_2` to visibly settle. The previous CSV sampling was mostly about 69 seconds in later runs and about 141 seconds in early runs. For dynamic identification, faster sampling would be better if the hardware and logging stack allow it, especially because the previous transport-delay fit found only second-scale apparent delay values.

## Safety Checklist Before Real Hardware Runs

Before running any script against:

```text
opc.tcp://192.168.0.2:4840
```

verify:

- the valve path is physically correct,
- the pump-to-stream map is physically correct,
- `PH_2` is connected and calibrated,
- waste/product routing is correct,
- pump bounds are enforced in code,
- total flow is acceptable for the tubing and probe,
- the script has a finite duration or operator stop condition,
- the script has `try/finally` cleanup,
- cleanup zeros flows, disables pumps, and closes valves,
- data logging starts before the first flow step,
- the operator can stop the run manually.

## Implementation Gaps To Fix Later

The library is usable as a low-level interface, but future experiment scripts should not directly copy the current demos. A safer pH experiment layer should add:

- explicit `settings_file` paths,
- pump number validation,
- flow bounds,
- valve-name validation,
- finite-duration step schedules,
- timeouts for threshold waits,
- structured CSV or database logging,
- `try/finally` cleanup,
- hardware endpoint versus emulator endpoint selection,
- a dry-run or confirmation mode for printing planned actions before writing them.

These additions should be made before closed-loop control. They can be implemented as a new experiment runner around `BioSMBManager` without modifying the low-level library.

## What Can Be Used Immediately

Useful now:

- `BioSMBManager` for direct OPC-UA reads and writes.
- `get_ph(2)` as the live `PH_2` read.
- `get_all_sensors()` and `get_all_flows()` for logging.
- `print_status()` for quick visual checks of valves and pump setpoints.
- `close_all_valves()`, `zero_all_flows()`, and `disable_all_pumps()` as cleanup primitives.
- `2024_09_17_UVIntegration.py` as a rough model for periodic observation logging.

Not ready as-is:

- `5_21_2026_demo.py` for lab execution.
- `demo_script.py` as an emulator test unless node-id mapping is fixed.
- any autonomous pH controller built directly on the current demos.

## Recommended Next Engineering Step

Create a new script, for example:

```text
run_open_loop_ph_identification_experiment.py
```

This script should not implement feedback control. It should:

- load an explicit step schedule,
- validate each pump command against `1-10 mL/min`,
- reset the system,
- configure a verified valve path,
- execute finite-duration open-loop steps,
- compute `pH_eq` from the equilibrium charge-balance model for each commanded flow tuple,
- log `PH_2`, diagnostic sensors, flows, equilibrium predictions, and metadata,
- clean up in `finally`.

Success would be a timestamped CSV with enough excitation to fit:

$$
\widehat{PH}_2(t) =
G\left(
0.6567 + 0.7909\,pH_{eq}(F_H(t), F_A(t), F_W(t)),
\theta,
\tau_{mix},
\tau_s
\right)
$$

where \(\theta\) is transport delay, \(\tau_{mix}\) is mixing/residence-time behavior, and \(\tau_s\) is pH sensor response. This is the right bridge between the current library and later safe controller design.
