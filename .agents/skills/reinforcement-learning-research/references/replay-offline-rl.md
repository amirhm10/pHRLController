# Replay and Offline RL

## Replay inventory

Record:

- capacity
- current size
- source policies
- time range
- episode count
- terminal fraction
- warm-start fraction
- recent fraction
- prioritized fraction
- safety-intervention fraction
- state and action ranges

## Distribution analysis

Compare replay and current-policy distributions:

\[
d_{\mathcal D}(s,a)
\quad \text{versus} \quad
d_\pi(s,a).
\]

Inspect by operating regime, setpoint, failure state, or subgroup.

## Prioritized replay

Verify:

- priority formula
- epsilon
- exponent
- importance weights
- update timing
- treatment of terminal samples
- interaction with recent or stratified sampling

## Offline RL questions

- Which policies generated the data?
- Is the learned policy selecting unsupported actions?
- Is behavior cloning competitive?
- Are Q values extrapolating?
- Is policy selection based on online feedback?
- Is off-policy evaluation justified?
- Are safety interventions represented?
- Does the dataset cover deployment conditions?

## Hybrid training

Separate:

- pretraining
- frozen periods
- live release
- online fine tuning
- probation or fallback
- evaluation

Do not mix these phases in one aggregate without stratification.
