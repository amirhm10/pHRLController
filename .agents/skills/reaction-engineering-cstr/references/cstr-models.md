# CSTR Model Checklist

## Material balances

For variable volume, use

\[
\frac{d(C_iV)}{dt}
=
F_{\mathrm{in}}C_{i,\mathrm{in}}
-
F_{\mathrm{out}}C_i
+
V\sum_r\nu_{ir}r_r.
\]

Do not divide by \(V\) before accounting for \(dV/dt\).

## Energy balance

Include as applicable:

- inlet and outlet enthalpy
- reaction heat
- jacket heat transfer
- shaft work
- phase change
- heat loss
- temperature-dependent properties
- jacket dynamics

## Pressure and gas phase

For gas or variable-pressure reactors, include a consistent equation of state and flow relation.

## Validation

- no-reaction limit
- no-flow batch limit
- adiabatic limit
- isothermal limit
- zero heat-transfer limit
- residence-time response
- steady-state balance closure
