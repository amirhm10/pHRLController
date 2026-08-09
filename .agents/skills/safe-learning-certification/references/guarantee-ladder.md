# Safety Guarantee Ladder

| Level | Evidence | Permitted wording |
|---|---|---|
| 0 | no safety analysis | no safety claim |
| 1 | no violation observed in stated runs | "No violations were observed in these runs." |
| 2 | replicated empirical evaluation over defined scenarios | "Empirical safety was observed over the tested distribution." |
| 3 | numerical certificate over a stated sampled or gridded region | "The condition was numerically verified over the tested region." |
| 4 | local or regional theoretical guarantee under stated assumptions | "The method guarantees ... for \(x\in\Omega\) under assumptions ..." |
| 5 | robust guarantee under explicit uncertainty bounds | "The guarantee holds for all uncertainty in the stated set." |

## Required qualifiers

- model
- state or operating region
- disturbance bounds
- estimator assumptions
- discretization
- solver feasibility
- executed action
- fallback
- probability level, if stochastic

Do not compress these qualifiers out of a report title or conclusion.
