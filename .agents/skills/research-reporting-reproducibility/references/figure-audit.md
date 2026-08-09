# Figure Audit

For each figure:

## Provenance

- [ ] Source data path identified
- [ ] Run, seed, scenario, and window identified
- [ ] Generation script or notebook cell identified
- [ ] Processing and smoothing documented

## Scientific content

- [ ] Figure supports the stated claim
- [ ] Baseline and candidate are comparable
- [ ] Setpoints or references shown when relevant
- [ ] Constraints and tolerance bands shown when relevant
- [ ] Warm-start, training, and evaluation regions identified
- [ ] Uncertainty shown for replicated results
- [ ] Failed or excluded runs disclosed

## Presentation

- [ ] Axes labeled
- [ ] Units shown
- [ ] Legend unambiguous
- [ ] Line styles distinguishable
- [ ] Comparable panels share scales when appropriate
- [ ] Zoomed tail view used only with full context available
- [ ] Caption states what is plotted, not the conclusion alone

## Common misleading patterns

- different axis limits that exaggerate improvement
- smoothing without raw traces
- tail-only views hiding release failures
- cumulative metrics masking local violations
- reward plots used as tracking evidence
- one representative seed presented as typical
