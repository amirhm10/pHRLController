# Routing Matrix

Use this matrix after defining the decision question.

| Question pattern | Primary skill | Add when needed |
|---|---|---|
| What happened in an experiment? | experiment-and-statistics | domain specialist, reporting |
| Why did an RL policy change behavior? | reinforcement-learning-research | control, safety, statistics |
| Is an MPC method correct? | control-mpc-research | math, optimization, solver |
| Is the process model physically valid? | chemical-engineering-foundations | unit-operation specialist |
| Why does Aspen fail or disagree? | aspen-process-simulation | thermodynamics, unit operation, solver |
| Is a column operating plausibly? | distillation-separations | Aspen, safety, control |
| Is a CSTR model or run unstable? | reaction-engineering-cstr | math, solver, safety |
| Are polymer molecular properties credible? | polymerization-process-engineering | CSTR, Aspen, statistics |
| Is pH behavior chemically and dynamically correct? | ph-aqueous-systems | control, Aspen, solver |
| Is an ML model scientifically valid? | machine-learning-research | statistics, domain specialist, testing |
| Is an RL result trustworthy? | reinforcement-learning-research | statistics, safety, domain specialist |
| Is the optimization problem well formulated? | optimization-modeling | math, solver, domain specialist |
| Why did the solver fail? | solver-engineering | optimization, math, software testing |
| Is a safety guarantee justified? | safe-learning-certification | math, control, RL |
| Should code be reorganized? | scientific-software-engineering | testing, domain specialist |
| What tests are needed? | scientific-software-testing | software, domain specialist |
| What does the literature establish? | literature-evidence-research | relevant specialist |
| Create a paper-quality artifact | research-reporting-reproducibility | evidence-owning specialists |

## Common combinations

### RL-assisted MPC result

1. experiment-and-statistics
2. reinforcement-learning-research
3. control-mpc-research
4. safe-learning-certification only if safety claims or interventions matter
5. chemical or unit-operation specialist when process physics is causal

### Aspen distillation result

1. aspen-process-simulation
2. distillation-separations
3. solver-engineering if convergence is involved
4. control-mpc-research for closed-loop analysis
5. process-safety-operability for abnormal scenarios

### Polymer CSTR result

1. reaction-engineering-cstr
2. polymerization-process-engineering
3. control or RL specialist as needed
4. solver and mathematics for stiffness or optimization
5. statistics for comparative claims

### ML soft sensor

1. machine-learning-research
2. experiment-and-statistics
3. chemical-engineering-foundations or application specialist
4. scientific-software-testing
5. reporting only when an artifact is requested

## Negative routing

Do not activate the suite for:

- finding a symbol or file
- a local syntax correction
- routine text rewriting with no scientific-claim review
- a simple unit conversion
- a one-line formula evaluation
- dependency installation unless scientific environment analysis is requested
