# Offline pH RL Environment and TD3 Scaffold

Date: 2026-07-01

## Objective

Create a simulation-only reinforcement-learning scaffold for the acetate buffer pH system while keeping the accepted ideal Henderson-Hasselbalch first-principles model unchanged. This work prepares offline TD3 experiments where the agent directly controls two pump flowrates:

- acetic acid flow, mL/min
- sodium acetate flow, mL/min

Arium water is fixed at 5 mL/min in the current scaffold and is logged as a process condition, not controlled by the TD3 action.

No BioSMB, OPC emulator, hardware runner, valve logic, MPC logic, or live controller code is part of this step.

## Why Gymnasium Was Used

Gymnasium was used because the implementation plan explicitly requested a Gymnasium-style environment with `reset()` and `step()`. The current action space has now been narrowed to `Box(-1, 1, shape=(2,))` after fixing water at 5 mL/min. The benefit is a standard, compact API:

```text
observation, info = env.reset(...)
next_observation, reward, terminated, truncated, info = env.step(action)
```

This does not mean the project must use a Gym training framework. In the source RL-assisted repository, the main pattern is a custom simulation loop that calls:

```text
agent.take_action(...)
agent.push(...)
agent.train_step(...)
```

The current pH code now supports that style through `run_offline_ph_td3_training.py`. Gymnasium is therefore only a thin environment interface and action-space definition. The practical RL workflow can still follow the custom loop style used in the other repository.

If desired later, Gymnasium can be removed and replaced by a small local `reset/step` class, but keeping it for now gives compatibility with common RL tools without changing the pH science.

## Current Implementation

### TD3 Core

The TD3 source was copied as a standalone local package:

- `TD3Agent/agent.py`
- `TD3Agent/actor.py`
- `TD3Agent/critic.py`
- `TD3Agent/replay_buffer.py`
- `utils/helpers_net.py`
- `utils/nstep.py`
- `utils/nstep_targets.py`
- `utils/sequence_sampling.py`

Only the TD3 core and minimal dependencies were copied. The MPC runners, supervisor-gated TD3 logic, SAC, DQN, residual/weight/horizon logic, BioSMB code, and generated result folders from the source repository were not copied.

In the algorithm name `TD3`, `TD` means Twin Delayed. It refers to the learning algorithm design, not to an extra action-space variable.

### pH Environment

The pH environment is implemented in:

```text
simulation/ph_environment.py
```

Main classes:

- `PHEnvironmentConfig`
- `PHEnvironment`

The action is a normalized vector:

```text
a = [a_acid, a_acetate], each in [-1, 1]
```

The environment maps the two action coordinates to acid and acetate pump bounds from `PHProcessConfig`:

```text
flow = flow_min + 0.5 * (action + 1) * (flow_max - flow_min)
```

Current default pump bounds are:

```text
acid:    1-10 mL/min
acetate: 1-10 mL/min
water:   fixed at 5 mL/min
```

The observation vector is:

```text
[current_pH, target_pH, pH_error, acid_action, acetate_action, step_fraction]
```

### Accepted First-Principles Model

The environment uses the accepted ideal Henderson-Hasselbalch model:

```text
pH = pKa + log10((C_base * F_base) / (C_acid * F_acid))
```

With the current equal 100 mM acid and acetate stocks:

```text
pH = pKa + log10(F_acetate / F_acid)
```

Water is still logged as a physical flowrate, but it is fixed at 5 mL/min in this offline RL scaffold. In the ideal static HH model it does not directly change the acid/acetate ratio when stock concentrations are equal.

### Repo-Style TD3 Simulation Runner

The new runner is:

```text
run_offline_ph_td3_training.py
```

It follows the same broad style as the RL-assisted repository:

1. Generate piecewise-constant pH setpoints.
2. Initialize the simulated plant.
3. Let TD3 choose normalized flow actions from the start of the offline rollout.
4. Convert actions to acid and acetate flows while keeping water fixed at 5 mL/min.
5. Step the pH environment.
6. Push transitions into replay.
7. Call `agent.train_step()` once the replay buffer has enough samples.
8. Save tables and figures under `results/offline_ph_td3_training_<timestamp>/`.

The default rollout length is now `25,000` steps. Setpoints change every `200` steps by default, so a default run has `125` setpoint segments. The default setpoint strategy is `admissible_random`: the runner draws seeded, stratified, non-repeating targets from the configured admissible pH range `[3.76, 5.76]`. The exact schedule is saved to:

```text
tables/setpoint_schedule.csv
```

By default there is no HH warm-start segment because the current task is offline TD3 training. A legacy HH warm-start can still be requested explicitly with `--warm-start-cycles`, but it is not part of the default protocol.

The runner reward now has three terms:

```text
reward = -(q2 * (target_pH - pH)^2
           + q1 * abs(target_pH - pH)
           + r_move * mean((action_t - action_t_minus_1)^2))
```

The default runner weights are:

```text
q2 = 1.0
q1 = 1.0
r_move = 0.01
```

The move term is computed on the normalized two-action vector `[acid_action, acetate_action]`, so it behaves like an MPC move penalty on `u_t - u_{t-1}` while staying independent of the physical mL/min scaling. The saved trajectory logs the scalar reward plus the raw component costs:

- `reward_squared_error_cost`
- `reward_absolute_error_cost`
- `reward_move_cost`
- `reward_total_cost`

Exploration is Gaussian action noise on the normalized actor output during training cycles only. The default runner uses linear decay from `std_start = 0.35` to `std_end = 0.03` over `5,000` exploratory action calls. Evaluation cycles use `agent.act_eval(...)` with no exploration noise. The saved trajectory logs:

- `exploration_sigma`
- `exploration_magnitude`
- `action_saturation_fraction`

## Generated Artifacts

A smoke training run generated:

```text
results/offline_ph_td3_training_20260701_211724/
```

Tables:

- `tables/trajectory.csv`
- `tables/trajectory_diagnostics.csv`
- `tables/episode_metrics.csv`
- `tables/setpoint_schedule.csv`
- `tables/training_summary.csv`
- `tables/config_snapshot.json`
- `tables/summary_metrics.csv`
- `tables/flow_diagnostics.csv`
- `tables/hh_consistency.csv`
- `tables/result_artifact_manifest.json`

Figures:

- `figures/fig_ph_tracking_error_reward.png`
- `figures/fig_flow_commands_and_ratio.png`
- `figures/fig_cycle_metrics.png`
- `figures/fig_action_diagnostics.png`
- `figures/fig_hh_ratio_consistency.png`
- `figures/fig_training_losses.png`

Smoke-run summary:

```text
total_steps:        600
setpoint_cycles:    3
steps_per_cycle:    200
setpoint_strategy:  admissible_random
warm_start_steps:   0
td3_train_steps:    397
batch_size:         4
overall_MAE:        0.3350 pH
overall_RMSE:       0.3793 pH
eval_MAE:           0.4353 pH
eval_RMSE:          0.4353 pH
sq_error_cost:      86.3174
abs_error_cost:     201.0169
move_cost:          79.7331
mean_exp_sigma:     0.2248
mean_exp_magnitude: 0.1660
```

This is a small software smoke test, not a scientific performance claim.
The saved trajectory has two action columns, `action_acid` and `action_acetate`, and all logged `water_flow` values are 5.0 mL/min.

## Verification

The following commands passed:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pHRL_pycache'
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile run_offline_ph_td3_training.py helpers\offline_ph_td3_results.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' tests\test_offline_ph_rl.py
```

Output:

```text
offline pH RL smoke tests passed
```

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' run_offline_ph_td3_training.py --total-steps 600 --batch-size 4 --buffer-size 512 --actor-hidden 16 --critic-hidden 16 --seed 41
```

Output confirmed `steps_per_cycle = 200`, `setpoint_cycles = 3`, `warm_start_steps = 0`, `td3_train_steps = 397`, and saved a local results bundle with figures, diagnostic tables, and `setpoint_schedule.csv`.

## Current Limitations

- This is still a static ideal-HH simulation, not a validated dynamic plant.
- Water is fixed and logged but does not directly change ideal HH pH.
- The TD3 result is only a software smoke test.
- No lab-data validation, emulator connection, BioSMB integration, pump runner, MPC layer, or live controller has been added.
- The useful next scientific step is to decide whether the RL environment should remain ideal-static for algorithm testing or should next wrap a dynamic pH model with delay, mixing, and sensor response.

## Recommended Next Step

Use `run_offline_ph_td3_training.py` as the starting loop and tune the simulation protocol:

- setpoint-count and setpoint-range sweeps around the 200-step default,
- training/test split similar to the RL-assisted repository,
- fixed seed batches for comparison,
- reward-weight sweeps for the squared, absolute, and move-penalty terms,
- later replacement of the static HH plant by an identified dynamic pH environment.

The next implementation step should still remain offline simulation-only unless hardware integration is explicitly requested.
