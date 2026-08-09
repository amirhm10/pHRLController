# Source Quality and Applicability

## Preferred source hierarchy

For technical claims:

1. official specifications, standards, or documentation
2. primary peer-reviewed papers
3. official benchmark repositories and datasets
4. high-quality reviews
5. recent preprints
6. credible technical reports
7. issue discussions and community sources for implementation symptoms
8. informal summaries only as navigation aids

## Applicability matrix

| Dimension | Current project | Source | Match |
|---|---|---|---|
| system or domain | | | |
| state and action type | | | |
| data regime | | | |
| dynamics or time scale | | | |
| constraints and safety | | | |
| baseline | | | |
| evaluation metric | | | |
| simulation versus experiment | | | |

A mathematically related paper can still be weak evidence if the data regime or implementation assumptions differ.

## Red flags

- no baseline or weak baseline
- single seed for stochastic methods
- test data used for tuning
- unknown implementation details
- changing several factors at once
- no uncertainty
- only average performance
- selective reporting
- claims stronger than experiments
- no distinction between simulation and physical validation
