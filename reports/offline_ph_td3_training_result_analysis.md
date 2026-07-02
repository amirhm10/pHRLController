# Offline TD3 pH Tracking Result Analysis

Generated on 2026-07-02 00:40:05 from saved result files only.

## Scope

This report analyzes the current offline pH TD3 simulation output. It does not launch BioSMB, an OPC emulator, hardware, MPC, valves, or pumps. The source result folder is:

`results/offline_ph_td3_training_20260702_003841`

The purpose is to create editable figures and a first write-up around the ratio-action TD3 scaffold. The result should be treated as an offline software diagnostic, not as a validated pH controller.

## Method

The environment state is the five-element vector

$$ s_t = [\mathrm{pH}_t,\ \mathrm{pH}^{\mathrm{sp}}_t,\ e_t,\ a_{r,t},\ \tau_t], $$

where `e_t = pH_t - pH_sp,t`. The TD3 action is

$$ a_t = [a_{r,t}],\quad a_{r,t} \in [-1,1]. $$

The action is mapped to a bounded acetate/acid flow ratio in log space:

$$ \log_{10}(F_{Ac}/F_{HAc}) = \ell_{\min} + \frac{a_{r,t}+1}{2}(\ell_{\max}-\ell_{\min}). $$

The buffer-flow sum is fixed at `15.0` mL/min, so `F_HAc + F_Ac` is constant and the ratio action determines the two buffer flows. Water is fixed and logged at 5 mL/min.

The setpoint schedule uses `admissible_random` targets. Each setpoint is held for `400` steps, and this saved run contains `125` setpoint segments.

The plant pH is the accepted ideal Henderson-Hasselbalch relation

$$ \mathrm{pH} = pK_a + \log_{10}\left(\frac{C_{Ac} F_{Ac}}{C_{HAc} F_{HAc}}\right). $$

Because the current acid and acetate stock concentrations are equal, this reduces to

$$ \mathrm{pH} = pK_a + \log_{10}\left(\frac{F_{Ac}}{F_{HAc}}\right). $$

The saved runner reward is

$$ r_t = -\left(q_2 e_t^2 + q_1 |e_t| + r_{\Delta u}\|a_t-a_{t-1}\|_2^2/n_u\right), $$

where `e_t = pH_sp,t - pH_t`, `a_t` is the normalized ratio action, and `n_u = 1`.

## Quantitative Summary

| Scope | Steps | MAE | RMSE | Max \|e\| | Reward sum | Sq cost | Abs cost | Move cost | Train updates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_steps | 50000 | 0.02347 | 0.04466 | 0.4247 | -1284 | 99.72 | 1173 | 1141 | 49537 |
| td3_training_steps | 49600 | 0.02331 | 0.04467 | 0.4247 | -1267 | 98.99 | 1156 | 1139 | 49537 |
| td3_eval_steps | 400 | 0.04282 | 0.04283 | 0.04304 | -17.87 | 0.7337 | 17.13 | 1.066 | 0 |

Overall MAE is 0.02347 pH and overall RMSE is 0.04466 pH. The evaluation-window MAE is 0.04282 pH and evaluation-window RMSE is 0.04283 pH. These values depend on the saved run length and random seed.

## Learning-Phase Diagnostics

| Phase | Steps | MAE | RMSE | Max \|e\| | Mean \|ratio error\| | Mean sigma | Mean \|noise\| |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_steps | 50000 | 0.02347 | 0.04466 | 0.4247 | 0.02347 | 0.06176 | 0.04935 |
| first_10000_steps | 10000 | 0.06569 | 0.09386 | 0.4247 | 0.06569 | 0.19 | 0.1517 |
| after_exploration_decay | 40000 | 0.01291 | 0.01704 | 0.1026 | 0.01291 | 0.0297 | 0.02377 |
| last_5000_training_steps | 5000 | 0.01057 | 0.01374 | 0.1026 | 0.01057 | 0.03 | 0.02419 |
| evaluation_cycle | 400 | 0.04282 | 0.04283 | 0.04304 | 0.04282 | 0 | 0 |
| first_20_each_cycle | 2500 | 0.02689 | 0.05024 | 0.4058 | 0.02689 | 0.06297 | 0.05083 |
| first_50_each_cycle | 6250 | 0.02577 | 0.04862 | 0.4247 | 0.02577 | 0.06288 | 0.05126 |
| last_50_each_cycle | 31250 | 0.02275 | 0.04351 | 0.4081 | 0.02275 | 0.06128 | 0.04878 |

The main learning signature is the drop from 0.06569 pH MAE during `first_10000_steps` to 0.01291 pH MAE after exploration reaches its floor. This indicates that the one-dimensional ratio action is learnable in the ideal HH simulator.

The final deterministic evaluation cycle gives 0.04282 pH MAE and 0.04304 pH maximum absolute error. This is encouraging, but it is still only one held-out setpoint cycle from the same reachable fixed-sum range.

## Cycle-Group And Settling Diagnostics

| Cycle group | Cycles | Mean cycle MAE | Mean cycle RMSE | Max cycle \|e\| | Mean move cost |
| --- | --- | --- | --- | --- | --- |
| cycles_0_24 | 25 | 0.06569 | 0.07905 | 0.4247 | 38.31 |
| cycles_25_49 | 25 | 0.01359 | 0.01586 | 0.08054 | 1.709 |
| cycles_50_74 | 25 | 0.0118 | 0.0141 | 0.09015 | 1.797 |
| cycles_75_99 | 25 | 0.01363 | 0.01581 | 0.07676 | 1.668 |
| cycles_100_123 | 24 | 0.01136 | 0.01388 | 0.1026 | 2.184 |
| evaluation_cycles | 1 | 0.04282 | 0.04283 | 0.04304 | 1.066 |

| Tolerance | Hold steps | Settled cycles | Failed cycles | Median settling steps | P90 settling steps | Max settling steps |
| --- | --- | --- | --- | --- | --- | --- |
| 0.05 | 20 | 107 | 18 | 0 | 13.2 | 334 |
| 0.02 | 20 | 83 | 42 | 26 | 148.8 | 354 |

The settling table is computed within each 400-step setpoint hold. A cycle is counted as settled only after the error stays inside the tolerance band for the listed hold duration.

## Best And Worst Setpoint Cycles

| Rank | Cycle | Target pH | Eval | MAE | RMSE | Max \|e\| | Move cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| worst | 2 | 5.037 | False | 0.1725 | 0.1938 | 0.4247 | 76.11 |
| worst | 4 | 4.653 | False | 0.1564 | 0.1776 | 0.4081 | 73.02 |
| worst | 0 | 4.857 | False | 0.1454 | 0.1728 | 0.3976 | 95.75 |
| worst | 5 | 4.646 | False | 0.1328 | 0.1541 | 0.4058 | 74.31 |
| worst | 7 | 4.634 | False | 0.1071 | 0.1268 | 0.3182 | 65.21 |
| best | 74 | 4.57 | False | 0.007512 | 0.009683 | 0.02839 | 1.108 |
| best | 100 | 4.518 | False | 0.007937 | 0.009954 | 0.02728 | 3.142 |
| best | 106 | 5.023 | False | 0.008022 | 0.01013 | 0.03301 | 0.9219 |
| best | 99 | 5.029 | False | 0.008024 | 0.01001 | 0.03118 | 1.997 |
| best | 66 | 4.568 | False | 0.008037 | 0.01013 | 0.03152 | 2.732 |

## Figures

![pH tracking, error, and reward](figures/offline_ph_td3_training_20260702_003841_analysis/fig_ph_tracking_error_reward.png)

This figure is the main tracking diagnostic. The fourth panel separates the raw squared-error, absolute-error, and move-penalty costs before reward weighting.

![flow commands and ratio](figures/offline_ph_td3_training_20260702_003841_analysis/fig_flow_commands_and_ratio.png)

This figure shows the actual acid and acetate commands under the fixed buffer-flow sum, the fixed water-flow log, and the acid/acetate log-ratio that drives the ideal HH pH.

![cycle metrics](figures/offline_ph_td3_training_20260702_003841_analysis/fig_cycle_metrics.png)

![action diagnostics](figures/offline_ph_td3_training_20260702_003841_analysis/fig_action_diagnostics.png)

The action diagnostic figure includes the normalized ratio-action trajectory, the ratio/log-ratio scatter, and exploration traces when those columns are available.

![HH ratio consistency](figures/offline_ph_td3_training_20260702_003841_analysis/fig_hh_ratio_consistency.png)

The maximum absolute residual against the ideal HH ratio line is 1.776e-15 pH. Water is fixed at 5 mL/min and does not create an independent pH offset in this static ideal model.

![training losses](figures/offline_ph_td3_training_20260702_003841_analysis/fig_training_losses.png)

## Flow Diagnostics

| Flow | Mean | Min | Max | Low sat frac | High sat frac | Mean \|dF\| |
| --- | --- | --- | --- | --- | --- | --- |
| acid | 7.487 | 5 | 10 | 0 | 4e-05 | 0.1951 |
| acetate | 7.513 | 5 | 10 | 0 | 0.00122 | 0.1951 |
| water | 5 | 5 | 5 | 0 | 0 | 0 |
| buffer_sum | 15 | 15 | 15 | nan | nan | 2.91e-07 |

Flow-limit check: no logged acid, acetate, or water flow exceeded its configured pump bounds. The maximum logged physical flow was 10 mL/min.

The logged acid-plus-acetate sum stayed between 15 and 15 mL/min.

## Interpretation

The current scaffold is behaving consistently with the intended static first-principles pH model. The action-to-flow mapping is bounded, the reward sign penalizes tracking error and action movement, and the logged pH follows the acid/acetate ratio.

For this saved run, the TD3 policy appears to learn the static ratio-tracking task after the initial exploration-heavy period. The early cycles contain the dominant tracking failures, while later cycles operate near the ideal HH inverse mapping. This is useful algorithm evidence for the offline simulator, not validation of the laboratory plant.

## Bugs, Inconsistencies, Or Risks

- The plant is static ideal HH, so it does not include delay, mixing, residence time, sensor lag, or lab mismatch.
- Water is fixed at 5 mL/min in this version and is plotted only as a logged process condition.
- The final evaluation result is only one setpoint cycle, so it should not be treated as robust generalization evidence.
- The current fixed 15 mL/min buffer-flow sum restricts the reachable setpoint range to about 4.459-5.061 pH under the current pump bounds.
- The move penalty is small compared with the absolute-error term, so the learned action can still show occasional sharp moves during training.
- The report reads saved CSV files, so stale figures are possible if the report is not regenerated after a new run.

## Recommended Next Experiments

The next step should be a deterministic evaluation sweep, not another single final-cycle check. After training, evaluate the frozen actor without exploration on a grid of reachable setpoints across 4.459-5.061 pH. The key metrics should be MAE, maximum absolute error, settling count within 0.02 and 0.05 pH, and flow saturation fraction.

After that, run a small seed batch, for example seeds 7, 21, 47, 73, and 101, using the same 50000-step protocol. Compare the mean and worst-case evaluation MAE rather than relying on one run.

A third useful experiment is a fixed-sum sweep. Try buffer-flow sums such as 12, 15, and 18 mL/min, and record the reachable pH range, saturation frequency, and tracking quality. This will tell us whether 15 mL/min is a good control design choice or just a convenient first setting.

Current reproducibility command:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' run_offline_ph_td3_training.py --total-steps 50000 --set-points-len 400 --std-decay-steps 10000 --batch-size 64 --buffer-size 5000 --seed 7
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' analysis\generate_offline_ph_td3_report.py --result-dir results/offline_ph_td3_training_20260702_003841
```

## Provenance

Files inspected or consumed:

- `run_offline_ph_td3_training.py`
- `simulation/ph_environment.py`
- `simulation/henderson_hasselbalch_model.py`
- `reports/overview.md`
- `reports/offline_ph_rl_environment_report.md`
- `results/offline_ph_td3_training_20260702_003841/tables/trajectory.csv`
- `results/offline_ph_td3_training_20260702_003841/tables/episode_metrics.csv`
- `results/offline_ph_td3_training_20260702_003841/tables/training_summary.csv`
- `results/offline_ph_td3_training_20260702_003841/tables/config_snapshot.json`

Generated outputs:

- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/summary_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/flow_diagnostics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/cycle_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/hh_consistency.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/learning_phase_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/cycle_group_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/settling_diagnostics.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/cycle_extremes.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/source_training_summary.csv`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/manifest.json`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_ph_tracking_error_reward.png`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_flow_commands_and_ratio.png`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_cycle_metrics.png`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_action_diagnostics.png`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_hh_ratio_consistency.png`
- `reports/figures/offline_ph_td3_training_20260702_003841_analysis/fig_training_losses.png`
- `reports/offline_ph_td3_training_result_analysis.md`
