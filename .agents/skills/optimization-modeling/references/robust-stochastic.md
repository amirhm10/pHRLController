# Robust and Stochastic Optimization

## Nominal

Uses one parameter value or forecast. Sensitivity analysis alone does not make it robust.

## Scenario based

Enforces or evaluates a finite set of scenarios. State how scenarios were generated and weighted.

## Robust

Requires an uncertainty set \(\mathcal{U}\) and constraints that hold for all allowed uncertainty, for example

\[
g(x,\xi)\le 0,\qquad \forall \xi\in\mathcal{U}.
\]

State the uncertainty set, conservatism, and tractability assumptions.

## Stochastic

Optimizes an expected or risk-aware objective under a probability model. Check distribution quality and sampling error.

## Chance constrained

\[
\Pr(g(x,\xi)\le 0)\ge 1-\epsilon.
\]

State the distributional assumptions and approximation method.

## Distributionally robust

Optimizes against a set of probability distributions. State how the ambiguity set is constructed.

## Audit questions

- Is uncertainty epistemic, aleatoric, or both?
- Is correlation represented?
- Are scenarios representative?
- Are decisions nonanticipative?
- Is the safety interpretation justified?
- Is out-of-sample validation performed?
