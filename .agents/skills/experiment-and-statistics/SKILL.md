---
name: experiment-and-statistics
description: Design, validate, and analyze scientific experiments and computational results. Use for data-integrity audits, metric definitions, seed aggregation, uncertainty intervals, fair baseline comparison, ablations, sensitivity analysis, hypothesis testing, and falsifiable next experiments across ML, RL, control, optimization, and chemical engineering. Validate provenance and analysis windows before interpreting performance. Do not use a single curve or point estimate as confirmatory evidence.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Experiment and Statistics

## Purpose

Ensure that conclusions follow from valid data, defined metrics, fair comparisons, and appropriate uncertainty. This skill is domain-independent and should be combined with a specialist that understands the mechanism being studied.

## Required order

1. Provenance
2. Data integrity
3. Metric definition
4. Comparison design
5. Statistical summary
6. Mechanism-oriented analysis
7. Decision rule
8. Reporting

Do not compute sophisticated statistics on unvalidated signals.

## 1. Establish provenance

Identify:

- run folder or dataset
- code or commit version
- configuration
- model or checkpoint
- seed
- scenario and disturbances
- sampling time
- training and evaluation status
- inclusion or exclusion reason

If provenance is incomplete, report that limitation.

## 2. Audit data integrity

Check:

- signal lengths
- timestamps and sampling intervals
- missing values and infinities
- reset and episode boundaries
- train, validation, and test separation
- physical versus scaled coordinates
- setpoint and disturbance alignment
- action and reward timing
- proposed versus executed action
- logged versus recomputed metrics
- duplicated or truncated records
- whether all compared runs contain equivalent fields

Read [data-integrity.md](references/data-integrity.md) for complex bundles.

## 3. Define metrics before calculation

Every metric needs:

- mathematical definition
- units
- signal source
- analysis window
- normalization
- aggregation across outputs, episodes, seeds, or scenarios
- direction of improvement

For control tasks, separate transient, post-warm, per-setpoint, and tail performance.

For ML tasks, separate train, validation, in-distribution test, and distribution-shifted test performance.

For RL tasks, separate training return, evaluation return, safety cost, sample efficiency, and worst-case behavior.

## 4. Check comparison fairness

Hold fixed unless intentionally varied:

- plant or dataset version
- initial condition
- disturbance or split
- constraints
- sample time
- rollout or training budget
- preprocessing
- solver settings
- checkpoint-selection rule
- evaluation protocol
- seeds or paired scenarios
- safety and fallback configuration

State the changed factor explicitly.

## 5. Quantify uncertainty

Prefer paired differences when runs share seeds or scenarios:

$$ \Delta M_s = M_s^{\mathrm{candidate}} - M_s^{\mathrm{baseline}}. $$

Report an appropriate subset of:

- mean and standard deviation
- median and interquartile range
- interquartile mean
- bootstrap confidence interval
- effect size
- probability of improvement
- worst case
- violation count
- performance profile
- sensitivity range

Do not hide failed, aborted, or negative runs.

## 6. Analyze mechanisms

Stratify results by factors that may explain behavior:

- setpoint block
- operating regime
- disturbance
- action source
- safety intervention
- model mismatch
- warm-start versus live learning
- training phase
- saturation or active constraint
- subgroup or equipment
- data coverage

A correlation can suggest a mechanism but does not establish causality.

## 7. Design the next experiment

Define:

- hypothesis
- one primary changed factor
- fixed factors
- seeds and scenarios
- primary metric
- secondary metrics
- minimum meaningful improvement
- safety or feasibility limits
- abort rule
- acceptance and rejection rule
- required saved signals
- planned figures

See [comparison-protocol.md](references/comparison-protocol.md).

## 8. Validate conclusions

Before finalizing:

- reproduce key metrics from raw data when possible
- inspect sensitivity to window choice
- check whether one run dominates the conclusion
- compare against a simple baseline
- state exploratory versus confirmatory status
- list unresolved confounders

## Output

Use:

- data and provenance status
- metric definitions
- comparison design
- numerical results with uncertainty
- robustness or sensitivity checks
- interpretation
- limitations
- next experiment or decision

## Gotchas

- The latest run is not necessarily the best-controlled comparison.
- Tail averages can hide release failures and transient violations.
- Smoothed curves obscure variance and extreme episodes.
- Random row splits can leak process trajectories, batches, or time.
- More seeds do not fix a biased metric or unfair baseline.
- Statistical significance is not practical significance.
