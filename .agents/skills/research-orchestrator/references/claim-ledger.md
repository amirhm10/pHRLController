# Claim Ledger Template

Use one row per major claim.

| ID | Claim | Class | Evidence | Counterevidence or confounders | Confidence | Needed next check |
|---|---|---|---|---|---|---|
| C1 | ... | empirical observation | file, metric, figure, source | ... | high, medium, low | ... |

## Claim classes

- **Verified defect**: a direct inconsistency, failed invariant, wrong mapping, or reproducible implementation error.
- **Empirical observation**: directly measured from identified data using a stated metric and window.
- **Strong interpretation**: several independent observations support the same mechanism and alternatives are weak.
- **Plausible mechanism**: consistent with evidence but not uniquely identified.
- **Open hypothesis**: requires a controlled experiment.
- **Design recommendation**: proposed action, not evidence that the action will succeed.

## Evidence types

- code trace or test
- raw-data calculation
- replicated experiment
- figure or trajectory
- mathematical derivation
- solver residual or diagnostic
- physical balance or invariant
- verified primary literature
- simulator state or export

A figure alone supports a visual or behavioral claim. It does not establish causality, stability, global optimality, or physical validity.
