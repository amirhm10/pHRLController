# Research Contract

For complex tasks, record:

```yaml
question: ""
decision: ""
mode: focused-audit
scope:
  repositories: []
  cases: []
  runs: []
  files: []
allowed_actions:
  - inspect
  - analyze
  - recommend
requires_explicit_permission:
  - edit
  - execute-expensive
  - simulator-run
  - publish
evidence_cutoff: ""
deliverable: ""
assumptions: []
```

## Modes

- `orientation`: locate and reconstruct the active method or system.
- `focused-audit`: answer one bounded technical question.
- `full-result-analysis`: validate data, analyze results, diagnose mechanisms, and decide.
- `deep-literature-research`: search, screen, synthesize, and cite external evidence.
- `experiment-design`: define a falsifiable test with fixed factors and decision rules.
- `theory-audit`: verify assumptions, derivations, and guarantee strength.
- `write-up`: create an artifact from accepted findings.

Do not silently switch from `focused-audit` to `edit` or `execute`.
