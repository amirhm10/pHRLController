# PCA, PLS, and Latent-Variable Methods

## PCA model

For centered and appropriately scaled data \(X_c\),

\[
X_c = T P^\top + E,
\qquad
T = X_c P.
\]

Define the exact centering and scaling from training data.

## Monitoring statistics

For score vector \(t_i\) and retained eigenvalues \(\Lambda\),

\[
T_i^2 = t_i^\top \Lambda^{-1}t_i,
\]

and the squared prediction error

\[
Q_i = \|e_i\|_2^2.
\]

## Audit checklist

- data unit and sampling structure
- train-only centering and scaling
- covariance versus correlation PCA
- missing-data handling
- number of components
- variance explained
- cross-validation
- score plots
- loading interpretation
- \(T^2\) and \(Q\) limits
- contribution analysis
- operating-mode confounding
- dynamic or lagged structure
- batch alignment
- external validation

## Component selection

Do not rely only on cumulative variance. Consider:

- reconstruction error
- downstream monitoring performance
- cross-validation
- parallel analysis
- stability of loadings
- physical interpretability

## PLS

For supervised latent-variable modeling, distinguish predictive components from unsupervised PCA components. Prevent leakage during component and hyperparameter selection.

## Process variants

- dynamic PCA
- multiscale PCA
- multimode or batch PCA
- multiblock methods
- kernel or nonlinear methods
- robust PCA
- sparse PCA

Use a more complex variant only when the failure of standard PCA is demonstrated.
