---
name: research-result-loop
description: Compatibility entrypoint for research-stage interpretation, experiment comparison, scientific audits, and research planning across chemical engineering, machine learning, reinforcement learning, control, optimization, mathematics, and scientific software. Use when a repository already calls $research-result-loop or when a question spans several research disciplines. Route to focused specialists; do not use for simple file lookup, routine formatting, or a local syntax fix.
license: MIT
compatibility: Designed for repository-local Agent Skills clients. Specialist activation may be automatic or manual depending on the client.
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Research Result Loop

## Purpose

Preserve compatibility with repositories that already invoke `$research-result-loop` while replacing the old monolithic workflow with a staged, modular research process.

This skill is a router. It does not attempt to contain all chemical-engineering, ML, RL, MPC, optimization, solver, mathematics, software, and reporting expertise itself.

## Default action boundary

Unless the user explicitly authorizes more:

- inspect files and history
- analyze code, equations, data, figures, and reports
- identify evidence, risks, and uncertainties
- recommend next actions

Do not edit files, execute Aspen, launch long training, regenerate user-owned results, or run destructive commands merely because this skill activated.

## Use this entrypoint when

- the repository or `AGENTS.md` already names `$research-result-loop`
- the task asks what worked, what failed, or why results changed
- several research disciplines must be combined
- a complete result analysis or research plan is requested
- the user asks for a literature-supported scientific audit

For a narrow request, use the most specific specialist directly.

## Routing procedure

1. Establish a research contract:
   - exact question
   - decision the answer must support
   - case study and repository scope
   - allowed actions
   - evidence and recency requirements
   - requested artifact, if any
2. Select one operating mode:
   - `orientation`
   - `focused-audit`
   - `full-result-analysis`
   - `deep-literature-research`
   - `experiment-design`
   - `theory-audit`
   - `write-up`
3. Activate `research-orchestrator`.
4. Add only the specialists needed for the current stage. Prefer one to three at a time.
5. Use a project profile for repository-specific paths, variables, units, environments, and execution restrictions.
6. Validate evidence before interpreting mechanisms.
7. Distinguish observations, verified defects, interpretations, hypotheses, and recommendations.
8. Stop when the question is answered. Do not force every specialist or every report section into every task.

## Specialist routing

- Literature, papers, citations, or competing methods: `literature-evidence-research`
- Data validity, metrics, seeds, fair comparisons, or ablations: `experiment-and-statistics`
- Reports, figures, LaTeX, provenance, or archival output: `research-reporting-reproducibility`
- Derivations, assumptions, proofs, conditioning, or stability logic: `mathematical-reasoning-verification`
- Problem formulation, constraints, objectives, or dynamic optimization: `optimization-modeling`
- IPOPT, HiGHS, OSQP, SCIP, scaling, derivatives, or infeasibility: `solver-engineering`
- PCA, PLS, deep networks, soft sensors, forecasting, calibration, or OOD evaluation: `machine-learning-research`
- MDPs, rewards, replay, TD3, SAC, DQN, offline RL, or policy evaluation: `reinforcement-learning-research`
- System identification, observers, MPC, target selection, feasibility, or robustness: `control-mpc-research`
- Lyapunov filters, barrier functions, shields, safety gates, or fallback: `safe-learning-certification`
- Balances, units, thermodynamics, transport, or general process physics: `chemical-engineering-foundations`
- Aspen Plus, Aspen Dynamics, `.bkp`, `.apw`, `.dynf`, or simulator convergence: `aspen-process-simulation`
- Columns, VLE, MESH equations, trays, packing, reflux, reboilers, or hydraulics: `distillation-separations`
- Kinetics, reactor balances, multiplicity, runaway, or CSTR dynamics: `reaction-engineering-cstr`
- Polymer kinetics, moments, molecular weight, viscosity, or grade transitions: `polymerization-process-engineering`
- Aqueous equilibria, buffers, titration, electrolytes, or pH control: `ph-aqueous-systems`
- Hazard scenarios, safe operating envelopes, trips, startup, or shutdown: `process-safety-operability`
- Architecture, refactoring, interfaces, configuration, typing, or maintainability: `scientific-software-engineering`
- Unit, invariant, property-based, metamorphic, integration, notebook, simulator, ML, or RL tests: `scientific-software-testing`

## Shared evidence rules

- Do not infer conclusions from filenames alone.
- Identify the active execution path before auditing implementation.
- Validate run provenance and data alignment before computing metrics.
- Compare methods only when the changed factor and fixed factors are explicit.
- Use evidence appropriate to the claim type. A figure is not a proof, and a solver status is not a physical-validity certificate.
- Do not invent citations, data, units, code paths, simulator states, or guarantees.
- Treat one trajectory or one seed as exploratory evidence unless the question explicitly concerns that run.
- Preserve raw results, old figures, original simulator files, and user-owned notebooks.

## Adaptive output

Use only sections needed by the request. A useful default is:

1. Scope and files inspected
2. Current method or system
3. Evidence and validation status
4. Findings, with confidence
5. Alternative explanations
6. Recommendation or next discriminating experiment
7. Remaining uncertainty
8. Files changed and verification, only when changes were authorized

## Gotchas

- The old skill activated on broad keywords. This compatibility version should route by user intent.
- A request mentioning `RL` does not automatically require control or chemical-engineering analysis.
- A request mentioning `MPC` does not automatically require literature, figures, and report editing.
- A report-writing request should not silently reopen accepted scientific conclusions unless an inconsistency is found.
- Repository instructions and project profiles override generic path guesses.
