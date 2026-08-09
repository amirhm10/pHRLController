---
name: research-orchestrator
description: Plan and coordinate multidisciplinary research tasks across literature, experiments, mathematics, ML, RL, control, optimization, solvers, chemical engineering, safety, software, testing, and reporting. Use when a task spans more than one specialist or requires a staged evidence-backed investigation. Establish scope and permissions, select a small set of specialists, maintain a claim ledger, and synthesize the final decision. Do not use for a single simple calculation or local code lookup.
license: MIT
compatibility: Designed for repository-local Agent Skills clients with optional web, code, data, and simulator tools.
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Research Orchestrator

## Purpose

Coordinate a research task without turning every request into a full research program. Keep the central question, action boundary, evidence ledger, and final synthesis consistent while focused specialists handle disciplinary analysis.

## Research contract

Before substantial work, determine:

- `question`: the exact question to answer
- `decision`: what choice, claim, or next action the answer will support
- `mode`: orientation, focused audit, full analysis, literature review, experiment design, theory audit, or write-up
- `scope`: repositories, cases, runs, files, dates, and systems included
- `allowed_actions`: inspect, analyze, create derived artifacts, edit, execute, or publish
- `evidence_cutoff`: source recency or experiment cutoff
- `deliverable`: answer, report, figures, code review, experiment plan, or another artifact

Do not repeat a question the user has already answered. Resolve minor ambiguity from repository context and state the assumption.

## Routing principles

- Activate the smallest coherent set of skills.
- Prefer one to three specialists per stage.
- Sequence dependent work. Data validation must precede metric interpretation.
- Parallelize independent work only when the environment supports it and evidence can later be reconciled.
- Use repository profiles for paths, variable mappings, units, environment, and expensive-execution rules.
- Keep public-web research separate from sensitive private-data operations when practical.

See [the routing matrix](references/routing-matrix.md) when the task is multidisciplinary or ambiguous.

## Required workflow

### 1. Orient

Identify:

- active execution entrypoint
- authoritative implementation files
- baseline and candidate
- saved data and configuration
- previous reports and failed attempts
- missing evidence

Trace the execution path when implementation matters:

`entrypoint -> runner -> model or agent -> controller -> plant or simulator -> logger -> saved bundle`.

### 2. Validate evidence

Before scientific interpretation:

- establish run provenance
- verify signal shapes, timestamps, units, scaling, and windows
- verify proposed, transformed, executed, and stored actions where relevant
- verify metric definitions
- identify exclusions and missing runs
- declare whether the evidence is exploratory or confirmatory

### 3. Dispatch specialists

Assign bounded questions, not vague roles. Examples:

- RL specialist: "Audit action semantics, replay, critic use, and evaluation protocol."
- Distillation specialist: "Check thermodynamic, stage, and hydraulic plausibility."
- Solver specialist: "Determine whether failures are formulation, scaling, derivative, or initialization problems."
- Statistics specialist: "Assess fairness, uncertainty, and whether the conclusion survives paired comparisons."

### 4. Reconcile

When specialists disagree, compare:

- assumptions
- data windows
- variable definitions
- model versions
- coordinate systems
- causal versus correlational claims
- theoretical versus empirical evidence

Do not average incompatible conclusions.

### 5. Build a claim ledger

Classify each major statement as:

- verified defect
- empirical observation
- strong interpretation
- plausible mechanism
- open hypothesis
- design recommendation

Record evidence, confounders, and confidence. Use [the claim-ledger template](references/claim-ledger.md) for a complex task.

### 6. Decide

Answer the decision question directly. When evidence is insufficient, define the smallest discriminating experiment or inspection that would resolve the uncertainty.

### 7. Validate the response

Check that:

- every major claim has appropriate evidence
- no citation, unit, path, or guarantee was invented
- the action boundary was respected
- negative and contradictory evidence was not hidden
- recommendations are testable
- the output structure matches the user's mode

## Action permissions

Default to `inspect`, `analyze`, and `recommend`.

Require explicit authorization before:

- editing code, notebooks, reports, or simulator files
- executing Aspen or an externally connected plant
- launching long simulations or training
- deleting, renaming, or overwriting artifacts
- committing, pushing, or publishing

A request to create a report or skill package authorizes only the requested artifact, not unrelated repository modifications.

## Stop conditions

Stop expanding scope when:

- the decision question is answered with adequate evidence
- the missing evidence is identified and cannot be obtained within the task
- another specialist would add context but not change the decision
- continued analysis would require an unauthorized execution or modification

## Output

Adapt to the task. For a full analysis, prefer:

- research contract
- files and evidence inspected
- system or method reconstruction
- validation results
- findings with confidence
- alternative explanations
- decision
- next discriminating experiment
- remaining uncertainty
- changed files and verification, if applicable

## Gotchas

- More activated skills can reduce focus. Do not activate the entire suite.
- The latest timestamp is not automatically the authoritative result.
- A recently modified report may summarize older runs.
- A safe-looking controller may simply be falling back almost all the time.
- A high-reward controller may be optimizing a misaligned reward.
- A converged solver may still return a physically invalid or local solution.
- A well-written report does not strengthen weak evidence.
