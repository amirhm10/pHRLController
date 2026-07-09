# BioSMB Online TD3 Integration Code Review And Roadmap

**Review date:** 2026-07-09

**Scope:** `Biosmb-interact`, `Biosmb-run-online`, and the current pH TD3 stack

**Change type:** review and planning only

**Implementation status:** no controller, hardware, configuration, or runtime code was changed

## Executive Decision

The present code is **not ready for active TD3 control of the BioSMB hardware**.
It is suitable as source material for a staged integration.

The recommended division of responsibility is:

- `Biosmb-interact` remains a read-only acquisition and historian service.
- `Biosmb-run-online` becomes the only future owner of control commands.
- The current SAC checkpoint and SAC state/action contract are retired from the
  TD3 path rather than adapted implicitly.
- A frozen TD3 actor is added only through an explicit policy contract, exact
  action mapper, safety supervisor, command/readback adapter, and finite
  deployment state machine.
- Live work begins in read-only shadow mode. Active control is allowed only
  after physical mapping, dynamic-model, policy-evaluation, software safety,
  and supervised hardware gates pass.

There are five immediate no-go blockers:

1. The online script's configured control-mode string is invalid, and the same
   mismatch prevents its exception handler from performing shutdown cleanup.
2. The online script assumes physical pumps 1, 2, and 3, while the latest local
   plumbing review says the live pH setup may use pumps 2, 3, and 4 and reports
   pump 1 as unavailable.
3. The online code expects a Stable-Baselines3 SAC policy with a different
   state and action meaning from the custom TD3 policy.
4. The completed current-default 500000-step TD3 result did not save a policy
   checkpoint, performed worse than the earlier 200000-step result on several
   saved metrics, and has not passed a full frozen-policy setpoint sweep or
   multi-seed evaluation.
5. The TD3 plant is an instantaneous ideal Henderson-Hasselbalch simulator.
   The real delay, mixing, residence-time, and `PH_2` sensor dynamics remain
   unvalidated.

The correct first experiment remains the supervised open-loop dynamic
identification experiment already planned in this repository.

For a quick first reading, use the Executive Decision, Sections 4, 7, 9, 12,
15, and 17. The remaining sections provide the code evidence, equations, test
matrix, and unresolved physical questions behind those decisions.

## 1. Objective And Review Boundaries

The objective of this review is to answer four questions without implementing
anything:

1. What do the two added BioSMB codebases currently do?
2. Where can the pH TD3 controller eventually connect?
3. What scientific and software gaps make a direct connection unsafe or
   invalid today?
4. What ordered roadmap gets from the present code to a limited, supervised,
   evidence-backed deployment?

This report does not authorize hardware writes. It does not treat a working
Python call as evidence that a control experiment is safe. It also does not
assume that historical CSV column positions are the same as current physical
pump numbers.

## 2. Files And Evidence Inspected

### Added BioSMB code

| Area | Files reviewed | Main purpose |
| --- | --- | --- |
| Read-only interaction service | [`Biosmb-interact/Biosmb-interact/main.py`](../Biosmb-interact/Biosmb-interact/main.py) | Poll BioSMB and MFCS, then write observations to MongoDB |
| Existing online runner | [`Biosmb-run-online/Biosmb-run-online/main.py`](../Biosmb-run-online/Biosmb-run-online/main.py) | Load an SAC model, build a live state, propose flows, write pumps, and log a deployment step |
| Hardware wrapper | both copies of `biosmb_interface/manager.py` | Read and write OPC-UA valve, pump, and sensor nodes |
| Node configuration | both copies of `settings.json` | Map BioSMB OPC-UA nodes, including `PH_1` and `PH_2` |
| Container definitions | both Dockerfiles and the online `docker-compose.yml` | Package and restart the services |
| Supplied online model | SAC checkpoint ZIP and replay-buffer pickle | Historical SAC artifact, not the current TD3 policy |

The two `manager.py` files are byte-identical, as are the two `settings.json`
files. This duplication is useful for comparison but creates future drift risk.
There is no README, automated test suite, deployment runbook, or fault-injection
suite in either added directory.

### Current TD3 and process evidence

| Evidence | Why it matters |
| --- | --- |
| [`simulation/ph_environment.py`](../simulation/ph_environment.py) | Defines the current TD3 state, normalized action, action-to-flow transform, fixed-water assumption, and ideal static plant |
| [`run_offline_ph_td3_training.py`](../run_offline_ph_td3_training.py) | Shows that transitions are generated interactively in simulation and that checkpoint saving is optional |
| [`TD3Agent/agent.py`](../TD3Agent/agent.py) | Defines deterministic actor inference and the current pickle-based checkpoint format |
| [`reports/offline_ph_td3_method_report.md`](offline_ph_td3_method_report.md) | Documents the method, the older 200000-step result, limitations, and missing frozen-policy sweep |
| [`reports/offline_ph_td3_training_result_analysis.md`](offline_ph_td3_training_result_analysis.md) | Documents earlier edge-target weakness and checkpoint limitations. It predates the completed 500000-step run |
| [`reports/dynamic_model_identification_report.md`](dynamic_model_identification_report.md) | Shows that the existing coarse lab CSV did not identify useful physical dynamics |
| [`reports/open_loop_ph_step_test_identification_plan.md`](open_loop_ph_step_test_identification_plan.md) | Defines the next safe experiment and its dynamic-model acceptance criteria |
| [`reports/biosmb_ph_plumbing_smoke_test_report.md`](biosmb_ph_plumbing_smoke_test_report.md) | Records the current pump and valve interpretation and its unresolved physical checks |
| `results/offline_ph_td3_training_20260709_030431/` | Supplies the completed current-default 500000-step trajectory, configuration, metrics, and figures |
| `results/offline_ph_td3_training_20260709_001341/` | Supplies the earlier 200000-step comparison result used by the current method report |

The SAC archive was inspected as an archive only. It was not deserialized or
executed. Its metadata identifies an SB3 SAC policy with observation dimension
5, action dimension 3, physical action bounds of 1 to 10, 400 training
timesteps, and 12 episodes.

## 3. What The Current Code Is Doing

### 3.1 `Biosmb-interact`

The interaction service is a telemetry collector, not a controller. Its loop
does the following in [`main.py`](../Biosmb-interact/Biosmb-interact/main.py):28-78:

1. Create a timestamp using `datetime.now()`.
2. Open a BioSMB OPC-UA connection.
3. Read all sensors and all seven flow values.
4. Close the BioSMB connection.
5. Open an MFCS OPC-UA connection.
6. Read two mass values.
7. Close the MFCS connection and sleep for one second.
8. Read an experiment name from Redis.
9. Insert the observation into MongoDB.
10. Repeat indefinitely.

This is a reasonable starting point for a raw historian. It does not provide a
fixed sampling period, synchronized pH and flow timestamps, OPC quality flags,
stale-data detection, retries, or a health interface. The one-second sleep is
added after network work, so it is not a one-second sampling deadline.

The file also contains an unused empty `get_biosmb_data()` function at lines
11-23. The MFCS mapping logs water and acid only at lines 41-56, while the
online runner uses a different three-mass mapping. Those two mappings must not
be assumed equivalent.

### 3.2 `Biosmb-run-online`

The online service is a monolithic frozen-SAC inference loop. It currently:

1. Loads an SB3 SAC checkpoint.
2. Connects to Redis, MongoDB, BioSMB OPC-UA, and MFCS OPC-UA.
3. Samples observations for a nominal 60-second warm-up.
4. Reads a target from Redis or uses `4.7` pH.
5. Builds a five-element SAC state.
6. Predicts three direct physical flowrates.
7. checks finite values, individual bounds, and total flow.
8. Repeats the previous action when the proposal is invalid.
9. Writes three pump values sequentially.
10. Samples and checks vessel masses for a nominal 60-second interval.
11. Logs the completed interval to MongoDB.
12. Repeats indefinitely.

The code correctly selects `PH_2` as the controller measurement at lines
49 and 230-233. `PH_1` is present only in the raw sensor dictionary and must
remain diagnostic-only.

Despite names containing `online`, the runner does not update the actor or
critic. It performs frozen inference. The supplied replay buffer is not loaded.

### 3.3 The current pH TD3 workflow

The current TD3 runner interacts with the ideal simulator, appends the newly
generated transitions to replay, and updates the agent inside the same rollout
loop at [`run_offline_ph_td3_training.py`](../run_offline_ph_td3_training.py):506-557.
It is therefore best described as **simulation-trained off-policy TD3**, not
strict batch offline RL.

The laboratory CSV supplies the desired setpoint range. Its transitions do not
train the TD3 policy. This distinction matters because the actor has not learned
the observed `PH_2` calibration shift, transport behavior, mixing response, or
sensor lag from laboratory data.

## 4. The SAC And TD3 Contracts Are Not Compatible

The two policies both use a five-element input, which creates a silent
compatibility hazard. The dimensions match while the meanings do not.

| Contract item | Existing online SAC | Current pH TD3 |
| --- | --- | --- |
| Loader | `stable_baselines3.SAC.load()` | custom `TD3Agent` construction plus load |
| State dimension | 5 | 5 |
| State meaning | `PH_2`, target, previous acid, previous acetate, previous water | `PH_2`, target, error, previous normalized ratio action, previous normalized sum action |
| Action dimension | 3 | 2 |
| Action meaning | three direct physical flowrates | normalized log-ratio coordinate and normalized acid-plus-acetate sum |
| Action bounds | `[1,10]^3` mL/min | `[-1,1]^2` |
| Water | actor-controlled | fixed at 5 mL/min |
| Training plant | historical SAC environment is not included | ideal instantaneous Henderson-Hasselbalch model |
| Current artifact | 400-step SAC checkpoint | completed 500000-step TD3 result saved no checkpoint |

A naive replacement of `SAC.load()` with the TD3 actor can accept a
five-element vector without raising a dimension error, while feeding physical
flows into positions where the TD3 actor expects an error and normalized
action coordinates. The two-output TD3 action also cannot be interpreted by
the current three-flow mapper.

No model substitution should happen until a versioned policy contract and
golden input-output tests exist.

The newer result also changes the readiness conclusion. The completed
`offline_ph_td3_training_20260709_030431` run used the current 500000-step,
128-by-128 network, batch-size 64 defaults. Its all-step MAE was 0.07237 pH,
RMSE was 0.13754 pH, and its single-target evaluation MAE was 0.02477 pH. The
evaluation tail-50 MAE was 0.02468 pH, with zero evaluation samples inside the
offline 0.02 pH tolerance. Its final target was 5.08965 pH and the acetate flow
was saturated at 10 mL/min.

Mean action saturation was 15.23 percent. The saved trajectory reached
one-step acid and acetate changes of 9 mL/min and an acid-plus-acetate sum
change of 17.92 mL/min. Flow bounds were enforced and the ideal HH calculation
was internally consistent, but these results expose policy, action-geometry,
and slew-readiness problems. They do not support hardware transfer.

The older 200000-step run had a lower single-target evaluation MAE of 0.01838
pH. This is not a controlled causal comparison because rollout length, batch
size, and network width changed together. It is sufficient evidence that the
new defaults are not yet a validated improvement. The active method and result
reports should be updated separately before their next scientific use.

## 5. Mathematical Integration Contract

### 5.1 Physical variables

Use the project conventions:

$$
y_k = PH_2(k)
$$

and

$$
u_k =
\begin{bmatrix}
F_{H,k} & F_{A,k} & F_{W,k}
\end{bmatrix}^{T},
$$

where (F_H) is acetic acid, (F_A) is sodium acetate, and (F_W) is
Arium water in mL/min.

The current TD3 actor expects

$$
s_k =
\begin{bmatrix}
y_k \\
r_k \\
y_k-r_k \\
a^{\rho}_{k-1} \\
a^{S}_{k-1}
\end{bmatrix},
\qquad
a_k =
\begin{bmatrix}
a^{\rho}_k \\
a^{S}_k
\end{bmatrix}
\in [-1,1]^2.
$$

The previous normalized action must be reconstructed from the last verified
physical flow readback. It must not be initialized from an assumed local
dictionary after a process restart.

### 5.2 Exact TD3 action mapping

The acid-plus-acetate sum is

$$
S_k = S_{\min}+
\frac{a^S_k+1}{2}(S_{\max}-S_{\min}).
$$

For this selected sum, the existing environment derives a feasible log-ratio
interval. The ratio coordinate is

$$
\ell_k = \ell_{\min}(S_k)+
\frac{a^{\rho}_k+1}{2}
\left[\ell_{\max}(S_k)-\ell_{\min}(S_k)\right].
$$

Then

$$
R_k=10^{\ell_k},
\qquad
F_{H,k}=\frac{S_k}{1+R_k},
\qquad
F_{A,k}=S_k-F_{H,k},
\qquad
F_{W,k}=5.
$$

The authoritative implementation is currently at
[`simulation/ph_environment.py`](../simulation/ph_environment.py):533-603.
Future deployment code should call one shared pure mapper or a versioned copy
with equivalence tests. Reimplementing these equations independently in the
online script would create an avoidable simulation-to-hardware mismatch.

If water becomes an actor-controlled variable after dynamic identification,
the action dimension and learned policy must change. The existing actor cannot
be reinterpreted silently.

In the ideal HH simulator, pH depends on the acid/acetate ratio and not on the
absolute acid-plus-acetate sum. The current reward penalizes movement of that
sum but has no steady reagent-use or preferred-throughput term. Many steady
sum values can therefore produce the same ideal pH, while different sums alter
ratio feasibility at the individual pump bounds. The dynamic experiment and
process requirements must determine whether sum should remain an RL action, be
set by a separate throughput policy, or be fixed before the deployment policy
is retrained.

### 5.3 Dynamic plant needed before active use

The real process is closer to

$$
pH_{eq}(t)=f_{chem}\left(F_H(t),F_A(t),F_W(t)\right),
$$

$$
\theta(t) \approx \frac{V_{tube}}{F_H(t)+F_A(t)+F_W(t)},
$$

$$
\tau_{mix}(t)\frac{d pH_{mix}}{dt}
=pH_{eq}(t-\theta)-pH_{mix}(t),
$$

and

$$
\tau_s\frac{d y}{dt}=pH_{mix}(t)-y(t).
$$

The best current empirical calibration was

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq},
$$

with held-out RMSE 0.0975 pH and mean error -0.0805 pH. As an illustration,
an ideal equilibrium coordinate of 4.7 maps to about 4.37 on that fitted scale.
This is not a deployment prediction because the calibration itself is not a
validated dynamic model. It shows that the observed mismatch is much larger
than the offline 0.02 pH success band and cannot be ignored by an adapter.

The present TD3 environment replaces all of this with an instantaneous static
map. The current five-element observation may therefore be non-Markov on the
real plant. Dynamic identification may require a state estimator, delayed flow
history, elapsed time, pH slope, or another observation design. Any state
change requires retraining the actor.

The simulator also has no safety-fault termination. `terminated` is always
false and only the final runner transition is marked done. The actor has not
learned responses to stale sensors, out-of-envelope pH, pressure faults,
inventory faults, write failures, or watchdog events. Those conditions belong
in a trusted runtime supervisor even if some are later represented during
robust training.

### 5.4 Safety supervisor contract

The learned actor should propose an action. It should never own the final
hardware command. A trusted supervisor should produce

$$
u_k^{cmd} = \mathcal{S}
\left(
u_k^{TD3},
y_k,
u_{k-1}^{verified},
z_k,
\mathcal{E}
\right),
$$

where $z_k$ contains sensor, pressure, inventory, communication, timing, and
readback health and where $\mathcal{E}$ is the operator-approved operating
envelope.

At minimum the supervisor must enforce:

- finite state and action values
- logical-stream and physical-pump mapping
- individual flow bounds
- acid-plus-acetate sum bounds
- fixed-water tolerance for the present policy
- total-flow and chemical-volume limits
- flow slew and composition-ratio limits
- hard `PH_2` envelope and pH rate checks
- pressure and inventory limits
- observation freshness and acquisition deadline
- command ownership and write/readback agreement
- a finite rejection budget
- an operator-defined fallback and independent watchdog

Repeating the previous action forever is not a complete fallback policy.

## 6. Recommended Target Architecture

```text
                    operator and independent interlocks
                                  |
                                  v
Redis target --> target validator and target latch
                                  |
BioSMB PH_2 ----> observation ----+----> dynamic state builder
BioSMB flows ---> adapter         |                |
MFCS masses ----> + health -------+                v
                                             frozen TD3 actor
                                                   |
                                                   v
                                           exact action mapper
                                                   |
                                                   v
                                            safety supervisor
                                              |           |
                                      shadow log      command arbiter
                                                          |
                                                          v
                                                 BioSMB command writer
                                                          |
                                                          v
                                                   readback verifier

All measurements, targets, decisions, rejections, commands, readbacks,
latencies, versions, and shutdown events go to an append-only deployment log.
```

The actor is deliberately inside a larger runtime-assurance boundary. The
operator, watchdog, and safety supervisor must be able to prevent or replace a
learned action without calling the actor or critic.

### Service responsibilities

`Biosmb-interact` should:

- remain read-only
- maintain persistent OPC sessions
- emit named, quality-checked, timestamped observations
- log `PH_2` as the controlled output and `PH_1` as diagnostic-only
- provide health and sampling diagnostics
- avoid becoming the command writer

`Biosmb-run-online` should eventually:

- be the single command owner
- load one frozen, approved, actor-only artifact
- build the exact versioned TD3 state
- map actions through the exact tested transform
- run the independent safety supervisor
- write a finite command session
- verify physical readback
- latch faults and require deliberate re-arming
- never train online in the initial deployment

MongoDB should be the historian, not a dependency that can delay or determine a
control decision. Logging failure should be handled according to an explicit
policy, with an in-memory or local durable queue if the run is allowed to
continue.

## 7. Findings Ordered By Severity

### 7.1 Critical software and physical blockers

| Finding | Evidence | Why it matters | Required disposition |
| --- | --- | --- | --- |
| Invalid active-control string | online `main.py`:23 uses `"active control"`, while lines 391-406 and 767-786 require `"active_control"` | The first write attempt crashes and the exception path does not call shutdown cleanup | Keep active mode disabled until a tested mode state machine replaces this string switch |
| Live pump mapping conflict | online `main.py`:33-39 and 398-402 assume pumps 1-3. The open-loop plan lines 70-75 and 99-122 describe possible pumps 2-4 and a failed pump 1 | A valid logical action can be sent to the wrong physical stream | Commission and sign the logical-stream-to-pump and MFCS mapping |
| Valve and outlet path unresolved | plumbing report and open-loop plan record `P2/P3/P4` as a clue, not a fully verified outlet route | Correct pump commands do not guarantee the mixture reaches `PH_2` or the intended outlet | Verify and log the valve path before any flow-write experiment |
| Policy contract mismatch | online `main.py`:236-330 versus `ph_environment.py`:632-638 and 533-603 | Matching state dimension can hide wrong feature semantics | Define a manifest, schema validation, and golden-vector tests |
| No deployable TD3 artifact | the 500000-step config has `save_checkpoint: false`. Runner lines 668-669 save only when requested | The analyzed policy cannot be reproduced or deployed from its result folder | Train, evaluate, and export a new approved actor bundle |
| No validated dynamic plant | dynamic report lines 929-948 and 1026-1060 | Static-simulator success is not laboratory control evidence | Complete the designed open-loop identification gate |

### 7.2 Major runtime safety gaps

#### Startup state is assumed, not reconciled

The online runner initializes previous flows as `[1,1,1]` at lines 264-290 and
584. Warm-up observes pH but does not replace that assumption with verified
current flows. It does not verify pump-enable states, valve routing, or whether
the `FLOW` array is a command setpoint or a true measured flow.

Startup must enter a `DISARMED` state, acquire and validate the current plant
configuration, reconstruct the previous normalized TD3 action from verified
flows, and require operator arming.

#### Pump writes are sequential and non-atomic

The runner calls `set_flow()` three times at lines 398-403. Each call reads the
whole seven-value array, changes one entry, and writes the whole array in
`manager.py`:201-216. A partial failure can leave an unintended composition.
Another writer can also be overwritten.

The future adapter needs exclusive write ownership, one reviewed array update
where the PLC supports it, preservation of unrelated channels, and immediate
readback verification. The behavior of all seven channels must be tested before
choosing between a scoped update and an all-array write.

#### Existing checks are necessary but incomplete

The current action checker verifies finite values, nonnegative values,
individual 1-10 mL/min bounds, and a 30 mL/min total. With three 10 mL/min
individual maxima, the total check adds no tighter envelope. There are no slew,
ratio, `PH_2`, pressure, stale-data, flow-readback, session-volume, deadline, or
watchdog constraints.

The training reward does not penalize the ratio action or individual pump
movement. It penalizes only movement of the acid-plus-acetate sum. This is
consistent with the 500000-step trajectory's 9 mL/min maximum one-step changes
for each buffer pump. A live slew envelope must be established experimentally,
enforced independently, and included during retraining so that the safety layer
does not continually replace the learned policy.

Mass checking is valuable, but the common 1200 g threshold and MFCS A/B/C
mapping need physical validation. Maximum waste capacity and delivered volume
also need limits.

#### Invalid actions repeat the previous command

At lines 368-381 an invalid proposal becomes the previous action. On the first
step this is an assumed default rather than the actual plant state. On later
steps the repeated action may itself be stale or unsafe. A future fallback
needs a finite retry count, fault latch, and an operator-approved response such
as scoped hold, known nominal flows, neutral flush, or scoped stop.

The correct fallback cannot be chosen from code review alone.

#### Shutdown affects the whole system

`zero_all_flows()` and `disable_all_pumps()` act on all seven pumps. A global
shutdown may interfere with unrelated equipment or may be the wrong response
for a pressurized or chemically loaded path. The future safety matrix must
define which pumps and valves are controlled by this experiment and what each
fault class should do.

### 7.3 Measurement, target, and timing gaps

- `get_all_sensors()` performs sequential OPC reads, followed by a separate
  flow read. This is not an atomic snapshot.
- OPC status codes and source/server timestamps are discarded.
- `datetime.now()` is stored under the name `utc_time`, even though it is a
  naive local timestamp created before acquisition.
- Each online sample opens a new MFCS connection and can perform a Mongo write.
- A nominal 60-second interval consists of 60 network acquisitions plus 60
  one-second sleeps, so its actual period is longer and variable.
- Redis targets are converted directly to float without finite, range,
  freshness, version, minimum-dwell, or source checks.
- A Redis failure silently selects `4.7`, which can be an unintended target
  change rather than a safe communications response.
- `target_ph_tolerance` is logged but does not define completion or safety.
- The online tolerance is 0.1 pH, while the offline environment success flag
  uses 0.02 pH. Neither value has yet been reconciled with `PH_2` repeatability,
  dynamic-model error, and the process requirement.
- An offline environment step has no physical duration. A 200-step training
  hold cannot be equated with 200 minutes merely because the current online
  runner uses a nominal 60-second decision interval.

The future scheduler must use a monotonic clock, deadline-based sampling,
target latching, explicit missed-deadline rules, and acquisition-span and
latency metrics.

### 7.4 Traceability, security, and container gaps

The deployment log is written only after the full action interval. A crash
after the hardware write can leave no deployment record of that command.
Required evidence includes:

- run and decision identifiers
- timezone-aware measurement, target, decision, write, and readback timestamps
- acquisition span and data age
- exact TD3 state vector and OOD flags
- raw normalized action
- mapped physical proposal
- safety-supervisor decision and reason
- executed command and verified readback
- inference and loop latency
- target source, version, and timestamp
- model manifest hash, source commit, image digest, and configuration hash
- fault, fallback, manual intervention, and shutdown events

The services embed endpoints and a database credential in source. These values
should be externalized, and any real exposed credential should be rotated
before the directories are committed or deployed. OPC security configuration,
timeouts, and endpoint identity checks are absent.

The online Compose file uses `restart: unless-stopped` and bind-mounts a live
`main.py`. An active controller must not automatically resume command authority
after a crash. A fault should latch across restart, and a new process should
return to `DISARMED` until an operator re-arms it. Production images should be
immutable and tied to a policy and configuration digest.

## 8. What Can Be Reused

| Existing component | Reuse decision | Conditions |
| --- | --- | --- |
| BioSMB OPC node configuration | Reuse after commissioning | Endpoint, namespace, sensor, pump, and valve mappings must match the live unit |
| `BioSMBManager` read methods | Reuse behind an adapter | Add status, timestamp, timeout, synchronization, and validation behavior |
| `BioSMBManager` write methods | Reuse only after command-adapter tests | Add ownership, bounds, scoped writes, readback, and fault handling |
| `PH_2` selection | Reuse | Keep `PH_1` out of policy state, validation metrics, and control decisions |
| TD3 actor architecture | Candidate for retraining | Do not reuse an unevaluated actor solely because the network loads |
| TD3 ratio/sum action design | Strong candidate | Retain exact mapper, fixed-water contract, and retrain on validated dynamics |
| `act_eval()` deterministic inference | Reuse in a policy adapter | Actor in evaluation mode with no exploration or online learning |
| Current SAC checkpoint | Do not use for TD3 integration | It is a separate 400-step historical artifact |
| Current Docker restart behavior | Do not reuse for active mode | Replace with a latched, explicitly armed lifecycle |
| Current Mongo schemas | Use as raw historical context | Add decision-level audit records and timing/version fields |

## 9. Phased Implementation And Application Roadmap

Each phase has an exit gate. Later phases do not begin because an earlier task
was merely coded. They begin after its evidence is reviewed and accepted.

### Phase 0: Freeze control authority and commission the physical map

**Purpose:** remove ambiguity about what the software can read and write.

Future work:

- Keep both added services write-disabled.
- Confirm acid, acetate, and water physical pump numbers.
- Confirm all MFCS mass channels, units, tare masses, and minimum inventories.
- Confirm the `P2/P3/P4` valve interpretation and the actual outlet path through
  `PH_2` to waste or collection.
- Determine whether the BioSMB `FLOW` values are commands, estimated flows, or
  independent measurements.
- Determine ownership of pumps 1-7 and the safe state for every fault class.
- Define pressure, pH, flow, slew, total-volume, waste, and session limits.
- Define who owns target changes and the manual emergency procedure.
- Remove and rotate embedded secrets before repository adoption.

**Exit gate:** a signed commissioning sheet maps every logical stream, pump,
valve, mass channel, pressure sensor, outlet, unit, and safe action. A read-only
hardware checkout reproduces that map.

### Phase 1: Acquire a dynamic identification dataset

**Purpose:** identify the missing bridge from flow commands to measured
`PH_2` before controller training.

Use the existing
[`open_loop_ph_step_test_identification_plan.md`](open_loop_ph_step_test_identification_plan.md):

- ratio steps at approximately fixed total flow
- total-flow steps at fixed acid/acetate composition
- water-fraction steps at fixed ratio
- repeated center points
- upward and downward transitions
- long holds until `PH_2` visibly settles
- a fixed 2-5 second sample period if the hardware and network support it
- command and readback timestamps
- physical tubing, mixer, flow-cell, and probe metadata

Fit static calibration, transport volume, mixing/residence response, and sensor
response on training trials. Validate on held-out trials and sessions.

Use the already proposed minimum scientific gate:

- dynamic test RMSE improves by at least 0.02 pH or 20 percent relative to the
  static calibrated baseline
- held-out final offsets are mostly within 0.05-0.10 pH
- fitted dynamic parameters are stable across repeated transitions
- response speed changes physically with total flow
- residuals have no strong systematic structure by pH, total flow, water
  fraction, direction, or session

**Exit gate:** an identified, held-out validated dynamic simulator. If this
gate fails, keep the model as a diagnostic and do not train an active TD3 policy
for this plant.

### Phase 2: Redesign, retrain, and evaluate the frozen TD3 policy

**Purpose:** create a policy whose observation and action contracts match the
validated plant and intended operating envelope.

Future work in the main repository:

- Add the validated dynamic plant without replacing raw laboratory data.
- Decide whether the current five-element state remains sufficiently Markov.
- Add state history or an estimator only when supported by identification.
- Preserve the ratio/sum action and fixed water unless a deliberate new action
  design is trained and evaluated.
- Train over validated delays, sensor lag, noise, calibration uncertainty,
  initial states, setpoints, and flow-dependent dynamics.
- Compare TD3 with a simple calibrated inverse-ratio or other reviewed baseline.
- Freeze learning before every evaluation.

Required evaluation:

- deterministic grid of at least 40 targets over the approved range
- repeated initial conditions and transitions in both directions
- at least five random seeds with identical evaluation scenarios
- central and edge targets
- model-parameter, sensor-noise, delay, and bias stress tests
- action saturation, pump-bound activity, slew, total volume, and chemical use
- IAE, RMSE, maximum absolute error, final offset, settling, and overshoot
- zero hard-constraint violations

Before using a dynamic plant, the actor should also pass a clean algorithm
check against the closed-form HH inverse on the ideal static simulator. A
useful promotion target is maximum final error and P95 tail error at or below
0.01 pH, zero flow-bound violations, no systematic edge bias, and less than
5 percent action saturation away from physically forced endpoints. The current
500000-step result does not meet the 0.02 pH evaluation tolerance and therefore
does not meet this stronger ideal-plant gate.

The existing local result proposes tail-50 MAE below 0.02 pH for most static
grid targets. That is an algorithm-development target, not by itself a live
deployment criterion. The active criterion must be reset after dynamic-model
validation and baseline comparison.

**Exit gate:** a frozen actor outperforms or justifiably complements the
baseline throughout the approved envelope, with no hard violations and
acceptable worst-case rather than only mean performance.

### Phase 3: Export a reproducible deployment bundle

**Purpose:** prevent state, action, network, and artifact ambiguity.

The bundle should contain only what frozen inference needs:

- actor weights in a weights-only format
- policy manifest in JSON
- network architecture and activation
- ordered feature names, units, bounds, and preprocessing
- ordered action names and bounds
- exact action-mapper version and fixed-water value
- training commit and result directory
- dependency versions
- approved operating envelope
- evaluation summary and promotion decision
- SHA-256 hashes
- golden input-state and expected actor-output vectors

The current `TD3Agent.save()` payload does not independently capture the full
network and deployment contract. It uses pickle and requires a correctly
constructed agent before loading. The deployment exporter should be separate
from a training-resume checkpoint and should reject missing or inconsistent
manifest fields.

**Exit gate:** a clean deployment environment reproduces all golden actor
outputs and action mappings exactly, using the recorded artifact hash and no
training code path.

### Phase 4: Build and fault-test a hardware-independent runtime

**Purpose:** prove the online logic before any OPC write is possible.

The future online core should separate observation, target, policy, mapping,
safety, actuation, logging, and lifecycle. A fake `BioSMBManager` should be used
for automated tests.

Required fault injections:

- missing, NaN, infinite, stale, stuck, noisy, or implausible `PH_2`
- accidental use of `PH_1`
- target missing, malformed, stale, out of range, or changing too quickly
- low mass, bad mass mapping, and exhausted session-volume budget
- high pressure and unavailable pressure data
- OPC read timeout, write timeout, disconnect, and partial write
- command/readback disagreement
- another writer holding the command lease
- actor NaN, action saturation, and state OOD
- missed control deadline and excessive inference latency
- MongoDB or Redis failure
- SIGINT, SIGTERM, process crash, and container restart
- watchdog heartbeat loss

**Exit gate:** deterministic unit, contract, trace-replay, emulator-interface,
and fault-injection tests pass with hardware writes structurally impossible.

### Phase 5: Live read-only shadow mode

**Purpose:** test the complete state-to-proposal path on the real timing and
measurement distribution without controlling the pumps.

Shadow mode must log:

- verified live state and data age
- raw TD3 action
- mapped physical proposal
- safety acceptance, projection, or rejection
- actual operator or baseline flows
- action disagreement and OOD status
- predicted and subsequently measured `PH_2`
- timing, deadlines, and all version hashes

The service must prove zero OPC writes by construction and audit, not merely by
a runtime string. Run across multiple sessions, targets, initial conditions,
and flow regimes.

**Exit gate:** reviewed sessions show no feature-order or mapping discrepancy,
no unexplained candidate actions, acceptable OOD and rejection rates, complete
logs, and no missed critical deadlines.

### Phase 6: Operator-approved one-action experiments

**Purpose:** validate the command and response path with one bounded candidate
at a time.

- Use an interior, dynamically validated pH region.
- Fix water at the policy value.
- Apply conservative flow and slew envelopes.
- Require explicit operator approval for each action.
- Verify command readback before starting the hold timer.
- Hold long enough to observe the identified response.
- Make every experiment finite and supervised.
- Require manual re-arming after every fault.

**Exit gate:** command/readback behavior is reliable, `PH_2` responses are
consistent with the validated model, and no safety or traceability failure
occurs across repeated independent trials.

### Phase 7: Short guarded closed-loop sessions

**Purpose:** allow limited autonomous control only inside the evidence-backed
envelope.

Initial sessions require:

- frozen actor and no online learning
- a narrow approved target and initial-condition range
- bounded target dwell and finite number of decisions
- hard flow, slew, ratio, pH, pressure, inventory, and volume limits
- command/readback verification
- independent watchdog and hardware or PLC interlocks where available
- operator presence and manual override
- an approved baseline or fallback controller
- a fault latch that survives process restart
- immutable image, policy, and configuration digests
- automatic end-of-session report

Do not begin with the full nominal 3.76-5.76 pH range. Expand one dimension of
the operating envelope at a time only after reviewed evidence.

**Exit gate:** repeated sessions meet tracking, settling, input-movement,
chemical-use, fallback, and safety metrics across different days and process
conditions. Any expansion requires a new reviewed promotion record.

## 10. Proposed Future Module Boundaries

This is a target layout, not an implementation made by this review.

```text
Biosmb-run-online/Biosmb-run-online/
  main.py                         thin orchestration only
  deployment_config.yaml         non-secret reviewed operating envelope
  controller/
    observation_adapter.py       PH_2, flows, mass, pressure, quality, time
    target_adapter.py            source, range, freshness, dwell, latch
    state_builder.py             exact manifest-validated TD3 state
    policy_adapter.py            actor-only deterministic inference
    action_mapper.py             normalized ratio/sum to physical flows
    safety_supervisor.py         constraints, OOD, watchdog, fallback
    command_adapter.py           ownership, write, acknowledgment, readback
    deployment_logger.py         decision and fault audit records
    session_state_machine.py     DISARMED, SHADOW, ARMED, RUNNING, FAULT
  models/
    approved_policy_manifest.json
    approved_actor_weights.*
  tests/
    test_policy_contract.py
    test_action_mapping.py
    test_safety_supervisor.py
    test_faults_and_shutdown.py
    test_shadow_has_zero_writes.py
```

`Biosmb-interact` can share a separately versioned hardware-interface package,
but it should not import the actor or safety supervisor. A single maintained
`biosmb_interface` package should eventually replace the two copied wrappers.

The deployment Docker build must include the approved policy runtime as a
package. The current online build context cannot import sibling main-repository
modules such as `TD3Agent` or `simulation` without explicit packaging or a
different build context.

## 11. Verification Matrix

| Layer | Verification | Minimum evidence |
| --- | --- | --- |
| Chemistry and dynamics | held-out step trials | bias, MAE, RMSE, max error, residual lag, parameter stability |
| Policy | frozen grid, seeds, initial states, uncertainty | IAE, RMSE, max error, offset, settling, saturation, violations |
| Policy contract | golden feature and actor vectors | exact state order, dtype, scaling, action, hash |
| Action mapper | boundary and round-trip tests | all flows finite, in bounds, correct ratio/sum, fixed water |
| Safety supervisor | unit and fault injection | every fault produces the specified accept, project, hold, or latch result |
| Hardware adapter | fake OPC, emulator interface, and supervised HIL | scoped write, acknowledgment, readback, timeout, ownership behavior |
| Scheduler | simulated slow and failed dependencies | bounded jitter, deadline tracking, no accidental catch-up burst |
| Shadow mode | live multi-session audit | zero writes, complete traces, OOD and rejection statistics |
| Guarded pilot | finite operator-supervised runs | control metrics, chemical use, fallback frequency, no hard violations |
| Recovery | crash, signal, network loss, and restart tests | safe transition, latched fault, explicit manual re-arm |

The existing OPC emulator is an interface emulator, not a pH plant model. It
can test node and failure behavior, but it cannot validate controller quality.
A process emulator or recorded-trace replay must supply the chemical response.

## 12. Go Or No-Go Checklist For The First Autonomous Run

Every item must be `yes`:

- Is the physical pump and MFCS mapping signed and current?
- Is the valve and outlet path through `PH_2` physically verified?
- Is `PH_2` calibrated, timestamped, fresh, and quality-checked?
- Are pressure, inventory, waste, and session limits approved?
- Is the safe response defined for every monitored fault?
- Is there exactly one command owner?
- Is the deployed policy bundle hashed and promoted from a reviewed result?
- Does the online state match the manifest and actor golden vectors?
- Does the action mapper match the training environment exactly?
- Has the dynamic model passed held-out validation?
- Has the frozen policy passed multi-target, multi-seed, and uncertainty tests?
- Have all negative and restart tests passed?
- Has shadow mode completed with zero writes and complete logs?
- Have operator-approved one-action experiments passed?
- Is an independent watchdog and manual override available?
- Is the run finite, with an operator present and a rollback plan?

Any `no` keeps the system in `DISARMED` or `SHADOW` mode.

## 13. Figures And Quantitative Evidence Used

No new figure was generated for this code-review task. The roadmap uses the
following existing evidence:

- The completed current-default 500000-step result's
  [`summary_metrics.csv`](../results/offline_ph_td3_training_20260709_030431/tables/summary_metrics.csv),
  [`flow_diagnostics.csv`](../results/offline_ph_td3_training_20260709_030431/tables/flow_diagnostics.csv),
  [`fig_setpoint_average_reward.png`](../results/offline_ph_td3_training_20260709_030431/figures/fig_setpoint_average_reward.png),
  and
  [`fig_last_25_setpoint_tracking.png`](../results/offline_ph_td3_training_20260709_030431/figures/fig_last_25_setpoint_tracking.png).
  This run had all-step MAE 0.07237 pH, one-target evaluation MAE 0.02477
  pH, 15.23 percent mean action saturation, and 9 mL/min maximum single-step
  movement for each buffer pump.
- The older 200000-step evidence documented in
  [`offline_ph_td3_method_report.md`](offline_ph_td3_method_report.md), including
  final-evaluation MAE 0.01838 pH at one target and low-edge tail-50 mean MAE
  0.06267 pH. The method report's latest-result section is now stale relative
  to the completed 500000-step run.
- Dynamic-model comparison in
  [`dynamic_model_identification_report.md`](dynamic_model_identification_report.md),
  where calibrated static held-out RMSE was 0.0975 pH and the tested lag,
  first-order, and transport wrappers did not improve it.
- Read-only plumbing evidence in
  [`biosmb_ph_plumbing_smoke_test_report.md`](biosmb_ph_plumbing_smoke_test_report.md),
  which confirms the software-facing `PH_2` path while retaining physical
  pump, valve, and outlet caveats.

Neither the 200000-step nor completed 500000-step result can be re-evaluated
after the fact because neither saved a checkpoint. A new serious run must save
an actor artifact and run the full frozen evaluation suite.

## 14. Literature And Standards Positioning

The custom agent follows the main TD3 ideas of twin critics, the minimum target
value, delayed actor updates, and target-policy smoothing described by
[Fujimoto, van Hoof, and Meger](https://proceedings.mlr.press/v80/fujimoto18a.html).
That algorithmic consistency does not establish process safety or sim-to-real
validity.

The repository term `offline TD3` means offline from the laboratory and trained
in simulation. In the standard literature, offline RL learns from a fixed
previously collected dataset without additional environment interaction. The
current runner instead creates new simulator transitions while training. The
distinction follows the formulation in
[Levine, Kumar, Tucker, and Fu](https://arxiv.org/abs/2005.01643).

The recommended independent safety supervisor and fallback follow the general
runtime-assurance pattern in which a high-automation component is monitored
and replaced when a safety condition is threatened. The cited
[NASA runtime-assurance report](https://ntrs.nasa.gov/citations/20200003114)
is an aerospace case study, not a certification basis for this pH system. It
supports the architecture pattern only.

## 15. Recommended Next Experiment

The next experiment is not TD3 control. It is the supervised open-loop dynamic
identification experiment already specified in the repository.

**Purpose:** determine the command-to-`PH_2` delay, mixing/residence response,
sensor response, calibration behavior, and total-flow dependence at a sampling
rate that can resolve them.

**Files likely involved later:**

- `reports/open_loop_ph_step_test_identification_plan.md`
- a finite hardware experiment runner with dry-run and guaranteed cleanup
- `simulation/dynamic_ph_process_model.py`
- focused data, identification, plotting, and analysis helpers

**Metrics that must improve:** held-out dynamic RMSE relative to calibrated
static chemistry, final offset, residual lag, and parameter repeatability.

**Failure modes to watch:** wrong pump or mass mapping, wrong valve path,
command/readback disagreement, under-sampling, holds shorter than settling,
session drift, sensor calibration changes, and a dynamic fit that explains
noise rather than transport physics.

**Figures required:** command and readback flows, total flow, `PH_2`, static and
dynamic predictions, transition overlays, residual time and lag plots, and
response-speed summaries versus total flow.

**Confirmation result:** the dynamic model passes the quantitative Phase 1
gate on held-out trials. If it does not, the correct conclusion is that active
TD3 deployment remains unsupported.

## 16. Remaining Uncertainty

The following questions require physical or operator evidence before
implementation decisions can be finalized:

1. Are the live pH streams pumps 2, 3, and 4, and is pump 1 still unavailable?
2. Which exact valves define the verified `PH_2` outlet route?
3. Does the OPC `FLOW` array represent commands, realized measurements, or
   controller estimates?
4. Can another client or operator write the same flow array concurrently?
5. Which MFCS nodes correspond to acid, acetate, and water, and what are their
   valid tare and minimum values?
6. Which pressure sensors and limits protect the active path?
7. What is the operator-approved fallback for sensor, communication, inventory,
   pressure, and model faults?
8. What live sample and decision intervals are achievable with bounded jitter?
9. What is the `PH_2` calibration history, response time, and valid operating
   range for this exact setup?
10. What controller or operating procedure is the trusted baseline for
    comparison and fallback?
11. Which target source is authoritative, and how are changes approved and
    latched?
12. Which host and immutable runtime will execute the actor?

## 17. Final Conclusion

The added code provides useful pieces but not a safe deployment path by itself.
`Biosmb-interact` supplies a starting acquisition service. `Biosmb-run-online`
supplies a rough lifecycle and logging sketch. The current TD3 stack supplies a
well-defined normalized ratio/sum policy interface for ideal simulation.

The bridge between them must be built deliberately and only after the plant
dynamics are identified. The shortest defensible path is:

```text
physical commissioning
-> read-only dynamic experiment
-> validated dynamic simulator
-> retrained and frozen TD3
-> versioned deployment contract
-> software fault testing
-> live shadow mode
-> operator-approved actions
-> short guarded closed-loop sessions
```

Until those gates pass, the correct runtime mode is `DISARMED` or `SHADOW`, not
active control.
