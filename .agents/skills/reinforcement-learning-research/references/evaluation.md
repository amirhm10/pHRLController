# RL Evaluation Protocol

## Separate training and evaluation

Evaluation should not:

- add exploratory noise unless stochastic-policy performance is being measured
- update networks
- update normalization statistics
- change replay
- tune hyperparameters on final scenarios

## Minimum reporting

- number of training seeds
- number of evaluation episodes per seed
- initial-state and disturbance distributions
- checkpoint-selection rule
- deterministic or stochastic policy
- mean, median, and robust aggregate
- uncertainty interval
- worst case
- failure and violation count
- task metrics in physical units
- return and cost definitions
- sample and compute budget

## Paired comparison

Use the same evaluation scenarios for baseline and candidate where possible. Analyze per-scenario differences.

## Curves

Learning curves should show:

- unsmoothed or lightly transparent raw information
- smoothing definition
- seed spread
- evaluation rather than only training return
- environment steps, not only episodes, when episode length varies

## Claim boundary

"Improved on these seeds and scenarios" is different from "generally superior."
