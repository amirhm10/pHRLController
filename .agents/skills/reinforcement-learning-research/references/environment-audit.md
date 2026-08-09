# RL Environment Audit

## Transition contract

For each step, verify:

\[
(s_k,a_k,r_k,s_{k+1},d_k).
\]

- observation emitted before action
- action applied for the documented duration
- reward uses the intended state or transition
- next observation corresponds to post-action state
- termination and truncation recorded separately
- reset initializes all hidden simulator and wrapper state

## Markov audit

List information influencing the next transition or reward:

- plant state
- estimator state
- controller memory
- previous action
- setpoint
- disturbance
- time within episode
- target-selector state
- safety-gate or probation state
- recurrent hidden state

If relevant information is omitted, document the POMDP or augment the observation.

## Normalization

- training statistics only
- same mapping in evaluation
- clipping documented
- inverse transform tested
- physical constraints transformed correctly

## Random-action smoke test

Before training:

- run valid random actions
- confirm observation and reward finiteness
- exercise bounds and terminal conditions
- verify logs
- verify saved transitions
- check that the environment can recover or reset
