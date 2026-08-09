# Comparison and Experiment Protocol

## Experiment specification

```yaml
hypothesis: ""
changed_factor: ""
fixed_factors: []
baselines: []
seeds: []
scenarios: []
primary_metric:
  name: ""
  direction: lower
  minimum_meaningful_change: null
secondary_metrics: []
safety_limits: []
abort_rule: ""
accept_rule: ""
reject_rule: ""
required_saved_signals: []
planned_figures: []
```

## Recommended designs

- paired seed and disturbance comparison
- factorial design for interacting factors
- one-factor ablation when interaction is not the question
- blocked design across operating regimes
- leave-one-regime-out robustness evaluation
- randomized run order when execution drift is possible

## Multiple variants

When many variants are tested:

- declare the selection process
- avoid reporting only the winner
- separate exploratory tuning from final evaluation
- reserve untouched evaluation scenarios
- consider correction for multiple comparisons
- report the tuning budget

## Minimum practical effect

Specify a practical threshold, not only a p-value. A small statistically detectable improvement may not justify additional complexity, compute, or risk.
