# MESH Equations and Thermodynamics

For component \(i\), stage \(j\):

## Material balance

\[
0 =
L_{j-1}x_{i,j-1}
+
V_{j+1}y_{i,j+1}
+
F_j z_{i,j}
-
L_jx_{i,j}
-
V_jy_{i,j}
\]

at steady state, with appropriate side-draw and reaction terms when present.

## Equilibrium

\[
y_{i,j}=K_{i,j}(T_j,P_j,\mathbf{x}_j)x_{i,j}.
\]

## Summation

\[
\sum_i x_{i,j}=1,
\qquad
\sum_i y_{i,j}=1.
\]

## Enthalpy

\[
0 =
L_{j-1}h_{j-1}^L
+
V_{j+1}h_{j+1}^V
+
F_jh_j^F
-
L_jh_j^L
-
V_jh_j^V
+
Q_j.
\]

Adapt signs and streams to the actual model.

## Audit

- component balance closure
- phase equilibrium residual
- summation
- enthalpy closure
- property method
- stage efficiency
- pressure
- feed phase
- condenser and reboiler boundary equations
