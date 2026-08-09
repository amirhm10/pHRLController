# Algorithm Checks

## DQN and variants

- discrete action recipes documented
- Q output dimension matches action set
- epsilon applied only where intended
- double-DQN target correct
- target network update correct
- dueling aggregation identifiable
- terminal masking correct
- action mask applied consistently
- replay priorities updated from intended TD error

## TD3

- twin critics
- minimum target Q
- target policy smoothing
- noise clipping
- delayed actor update
- Polyak update
- actor action scaling
- exploration noise separate from target noise
- critic evaluates the action representation stored in replay
- deterministic evaluation

## SAC

- stochastic squashed policy
- log-probability correction for squashing
- entropy coefficient fixed or learned as intended
- target entropy
- twin critics
- reparameterized actor update
- evaluation action convention
- action scaling and Jacobian consistency

## General

- done and truncation mask
- discount convention
- reward scale
- optimizer and learning rate
- gradient clipping
- device and dtype
- random seeds
- checkpoint completeness
- target network serialization
