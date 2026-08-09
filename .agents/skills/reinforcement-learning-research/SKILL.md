---
name: reinforcement-learning-research
description: Analyze and design reinforcement-learning systems as a first-class discipline. Use for MDP or POMDP formulation, environment correctness, reward and cost design, exploration, replay buffers, actor-critic or value learning, TD3, SAC, DQN, offline RL, imitation learning, model-based RL, multi-agent RL, policy evaluation, and reproducibility. Trace proposed through executed actions, separate training from evaluation, and require multi-seed or scenario evidence for broad claims.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Reinforcement Learning Research

## Purpose

Determine whether an RL problem is correctly formulated, implemented, trained, and evaluated. Treat control as one application among many. Combine with `control-mpc-research` only when the policy modifies or controls a dynamical system through MPC or another controller.

## 1. Formalize the decision process

Define an MDP

\[
\mathcal{M} =
(\mathcal{S},\mathcal{A},P,r,\gamma,\rho_0),
\]

or constrained MDP with costs \(c_j\).

State:

- observation and latent state
- Markov or partially observable assumption
- action
- transition timing
- reward and cost
- discount factor
- initial-state distribution
- episode termination
- time-limit truncation
- decision interval
- environment integration interval

If the observation is not Markov, consider history, recurrent state, a belief state, or an explicit limitation.

## 2. Audit environment semantics

Trace:

`observation -> policy action -> scaling -> clipping -> projection or gate -> executed action -> transition -> reward -> stored transition`.

Verify:

- state and next-state ordering
- reward timing
- termination versus truncation
- reset validity
- wrapper consistency
- random seeds
- disturbances
- observation normalization
- action normalization
- delayed measurements
- simulator statefulness
- hidden future information

Read [environment-audit.md](references/environment-audit.md).

## 3. Define action semantics

Record every action representation:

- raw network output
- exploration-perturbed action
- scaled physical action
- clipped action
- safety-projected action
- supervisor-selected action
- executed action
- replay-stored action
- critic-evaluated action

The critic, replay buffer, behavior-cloning loss, and diagnostics must use action semantics consistent with the intended algorithm.

## 4. Audit reward and cost

Separate:

- environment objective
- training reward
- safety cost
- auxiliary loss
- evaluation metric
- terminal reward
- shaping
- normalization or clipping

Check:

- sign
- scale
- domination by one term
- availability at decision time
- nonstationarity
- reward hacking
- conflict with evaluation metrics
- unsafe tradeoffs hidden by a scalar reward

## 5. Audit data collection and exploration

Analyze:

- initial-state diversity
- disturbance diversity
- action distribution
- saturation
- state-action coverage
- exploration schedule
- entropy or action variance
- coverage of rare or unsafe states
- warm-start data
- supervisor or behavior-policy mixture
- distribution shift from data to current policy

## 6. Audit replay

Inspect:

- capacity and effective age
- uniform, prioritized, recent, or stratified fractions
- priority definition and update
- source policy
- duplicates and correlation
- terminal transitions
- state and action ranges
- coverage by regime
- proposed and executed actions
- safety-intervention metadata
- stale data
- per-agent buffers and credit assignment

Read [replay-offline-rl.md](references/replay-offline-rl.md).

## 7. Audit learning

For value-based methods:

- Bellman targets
- target network update
- double-Q logic
- action masking
- epsilon schedule
- Q scale and drift
- overestimation

For actor-critic methods:

- critic target
- actor objective
- twin critics
- delayed policy updates
- target smoothing
- entropy tuning
- gradient scale
- critic disagreement
- target network lag
- action bounds

Use [algorithm-checks.md](references/algorithm-checks.md) for TD3, SAC, and DQN.

## 8. Evaluate policies

Keep evaluation separate from training.

Use:

- separate evaluation environments
- deterministic and stochastic evaluation as appropriate
- multiple training seeds
- multiple initial states and scenarios
- fixed evaluation budget
- declared checkpoint selection
- return and task metrics
- safety costs
- worst case and failure frequency
- sample efficiency
- wall-clock and inference cost
- robust aggregates and uncertainty

Read [evaluation.md](references/evaluation.md).

## 9. Offline and hybrid RL

When data come from logs, MPC, supervisors, or multiple policies:

- identify behavior policies
- assess support coverage
- compare with behavior cloning
- avoid unsupported actions
- distinguish offline tuning from online evaluation
- consider conservative or behavior-regularized methods
- audit off-policy evaluation assumptions
- require safe online validation before deployment

## 10. Decide

State:

- whether the environment and transitions are correct
- whether the objective is aligned
- whether the data support the learned policy
- whether learning is stable
- where the policy works and fails
- evidence strength
- next discriminating experiment

## Gotchas

- Decreasing critic loss does not prove useful Q ordering.
- A critic used as a safety gate requires calibration against realized outcomes.
- Training return is not evaluation performance.
- Time-limit truncation should not always be treated as terminal.
- Replay generated by a supervisor is not equivalent to on-policy experience.
- A high-acceptance actor may still be unsafe, while a low-acceptance actor may be irrelevant.
- One seed is exploratory evidence.
