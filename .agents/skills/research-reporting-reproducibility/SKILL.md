---
name: research-reporting-reproducibility
description: Create and audit scientific reports, papers, figures, tables, LaTeX or Markdown, and reproducibility records from already validated evidence. Use for research write-ups, figure packages, result narratives, run manifests, citation checks, model or dataset documentation, and archival experiment notes. Preserve uncertainty and provenance, match evidence to claim type, and avoid strengthening claims during editing. Do not silently redo the scientific analysis unless an inconsistency is found.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Research Reporting and Reproducibility

## Purpose

Turn accepted findings into a clear, traceable scientific artifact. Preserve the difference between what was tested, observed, inferred, and still unknown.

## Entry condition

Before writing substantive conclusions, verify that:

- the evidence-owning specialist completed its analysis
- metric definitions and windows are known
- run provenance is available or its absence is stated
- citations are verified
- the user authorized creation or modification of the artifact

If these conditions fail, stop and request or perform the missing validation within the allowed scope.

## Report workflow

### 1. Define audience and artifact

Identify:

- paper, technical report, change report, notebook narrative, poster, or response
- intended audience
- required format
- target length
- notation and style conventions
- whether the artifact is exploratory, internal, or publication-facing

### 2. Build a claim-evidence map

For every major claim, identify:

- claim class
- source data or derivation
- metric and window
- figure or table
- citation, if external
- uncertainty and limitations

Use evidence appropriate to the claim. See [figure-audit.md](references/figure-audit.md).

### 3. Preserve scientific distinctions

Clearly separate:

- objective
- method
- mathematical formulation
- experimental setup
- observations
- interpretation
- limitations
- next experiment

Do not write that a method is proven, stable, safe, optimal, robust, or superior unless the evidence supports that exact level.

### 4. Record provenance

Create or update a run manifest containing:

- repository and commit
- dirty state
- configuration
- seed and scenario
- model or checkpoint
- environment
- simulator version and case, if relevant
- sampling time
- source-data paths
- analysis scripts
- figure paths
- metric definitions

See [run-manifest.md](references/run-manifest.md).

### 5. Create figures and tables

- Use raw data or verified derived data.
- Show units, setpoints, constraints, and evaluation windows when relevant.
- Keep axes comparable across methods.
- Show uncertainty for replicated results.
- Keep unsmoothed information available when smoothing.
- Do not omit failed runs without explanation.
- Use a small set of high-signal figures.
- Save the code or exact procedure used to generate each derived artifact when practical.

### 6. Handle citations

- Verify every source and citation key.
- Cite the sentence the source supports.
- Distinguish local reports, primary literature, official documentation, and preprints.
- Do not copy extended source text.
- Do not create a BibTeX entry from uncertain metadata.

### 7. Preserve artifacts

- Do not overwrite raw results.
- Do not replace old figures unless explicitly requested.
- Use dated or versioned output paths.
- Keep report edits targeted unless a full rewrite is requested.
- List changed files and how to verify them.

### 8. Audit the final artifact

Check:

- notation consistency
- units
- table rendering
- equation rendering
- figure labels and legends
- internal cross-references
- citation keys
- claim strength
- missing limitations
- reproducibility information
- broken paths

## Default report structure

Adapt as needed:

1. Executive summary
2. Objective and decision question
3. Method and mathematical formulation
4. Experimental setup and provenance
5. Results
6. Figures and evidence
7. Interpretation and competing explanations
8. Limitations
9. Decision or next experiment
10. Reproducibility appendix

## Gotchas

- Editing for confidence can accidentally turn a hypothesis into a conclusion.
- A plot generated from the wrong bundle can look plausible.
- Tables with incompatible units invite misleading aggregation.
- A smooth learning curve can hide seed variance or catastrophic episodes.
- Recent modification time does not prove the report covers the latest experiment.
