# 04 - Previous SISO pH Model Implementation

## Purpose

This report summarizes the older SISO pH implementation and extracts only the pH plant model. The MPC and RL parts are not used here.

The previous model is not the same chemistry as the current acetate-buffer process. It is useful because it shows a pattern for pH modeling:

```text
state dynamics -> absolute concentrations -> algebraic pH solve -> pH deviation
```

## Previous model structure

The previous code defines a class called:

```python
pH_siso_example
```

The process has:

- one manipulated input, `u`, interpreted as a deviation in manipulated flow,
- two concentration states, `xA` and `xS`, stored in deviation form,
- one pH output solved from a nonlinear algebraic equation.

Key parameters:

| Variable | Value | Meaning |
|---|---:|---|
| `V` | 30.0 | volume or effective holdup |
| `FS` | 1.5 | second inlet flowrate |
| `CA` | 0.5 | concentration in manipulated inlet |
| `CS` | 1.2 | concentration in second inlet |
| `KS` | `5.7143e-9` | equilibrium constant in pH equation |
| `xA_ss` | 0.3125 | steady-state first state |
| `xS_ss` | 0.4500 | steady-state second state |
| `FA_ss` | 2.5 | steady-state manipulated flow |
| `x_pH0` | 7.0 | initial pH guess for `fsolve` |

The steady-state pH from this model is approximately:

$$
\mathrm{pH}_{ss}\approx5.40
$$

## Dynamic model

The manipulated input is a deviation:

$$
F_{A,abs}=F_{A,ss}+u
$$

The total flowrate is:

$$
F_T=F_S+F_{A,abs}
$$

The states are also in deviation form:

$$
x_{A,abs}=x_A+x_{A,ss}
$$

$$
x_{S,abs}=x_S+x_{S,ss}
$$

The dynamic equations are:

$$
\frac{dx_A}{dt}=\frac{1}{V}\left(F_{A,abs}C_A-F_Tx_{A,abs}\right)
$$

$$
\frac{dx_S}{dt}=\frac{1}{V}\left(F_SC_S-F_Tx_{S,abs}\right)
$$

This is a well-mixed tank material-balance structure.

## Algebraic pH equation

The pH is solved from:

$$
0=-x_{A,abs}+10^{-\mathrm{pH}}-10^{\mathrm{pH}-14}+\frac{x_{S,abs}}{1+10^{pK_S+\mathrm{pH}-14}}
$$

The terms:

$$
10^{-\mathrm{pH}}
$$

and:

$$
10^{\mathrm{pH}-14}
$$

represent hydrogen and hydroxide-type terms. The last term represents a pH-dependent weak-species contribution.

The code uses `fsolve` with initial guess pH 7.0. It clips pH inside the residual to 0-14 for numerical safety.

## Simulation convention

The previous simulation used this sequence:

```python
y = odeint(pH_obj.pH_process, x0, ts, args=(u_mpc[i],))

xA[i + 1] = y[-1][0]
xS[i + 1] = y[-1][1]

xA_abs = xA[i + 1] + pH_obj.xA_ss
xS_abs = xS[i + 1] + pH_obj.xS_ss

pH_abs = fsolve(
    lambda pH: pH_obj.func_pH(pH, xA_abs, xS_abs),
    x0=np.array([pH_obj.x_pH0], dtype=float),
)[0]

pH_dev = pH_abs - pH_obj.pH_ss
```

So the output convention is:

$$
\mathrm{pH}_{dev}=\mathrm{pH}_{abs}-\mathrm{pH}_{ss}
$$

## Clean extracted model

```python
import numpy as np
from scipy.integrate import odeint
from scipy.optimize import fsolve


class PreviousSisoPHModel:
    def __init__(self):
        self.x_pH0 = 7.0
        self.V = 30.0
        self.FS = 1.5
        self.CA = 0.5
        self.CS = 1.2

        self.KS = float(5.7143e-9)
        self.pKS = float(-np.log10(self.KS))

        self.xA_ss = 0.3125
        self.xS_ss = 0.4500
        self.FA_ss = 2.5

        self.pH_ss = self.solve_pH([self.xA_ss, self.xS_ss])

    def state_rhs(self, x, t, u):
        FA_dev = float(u)
        xA_dev = float(x[0])
        xS_dev = float(x[1])

        FA_abs = self.FA_ss + FA_dev
        xA_abs = self.xA_ss + xA_dev
        xS_abs = self.xS_ss + xS_dev
        F_T = self.FS + FA_abs

        dxA_dt = (FA_abs * self.CA - F_T * xA_abs) / self.V
        dxS_dt = (self.FS * self.CS - F_T * xS_abs) / self.V

        return np.array([dxA_dt, dxS_dt], dtype=float)

    def ph_residual(self, pH, xA_abs, xS_abs):
        pH = np.asarray(pH, dtype=float)
        pH = np.clip(pH, 0.0, 14.0)

        H = np.power(10.0, -pH)
        OH = np.power(10.0, pH - 14.0)
        weak_term = xS_abs / (1.0 + np.power(10.0, self.pKS + pH - 14.0))

        return -xA_abs + H - OH + weak_term

    def solve_pH(self, x_abs):
        x_abs = np.asarray(x_abs, dtype=float).reshape(2,)
        sol = fsolve(
            lambda pH: self.ph_residual(pH, x_abs[0], x_abs[1]),
            x0=np.array([self.x_pH0], dtype=float),
        )
        return float(sol[0])

    def output_pH_deviation(self, x_dev):
        x_dev = np.asarray(x_dev, dtype=float).reshape(2,)
        xA_abs = self.xA_ss + x_dev[0]
        xS_abs = self.xS_ss + x_dev[1]
        pH_abs = self.solve_pH([xA_abs, xS_abs])
        return pH_abs - self.pH_ss

    def simulate_step(self, u, tf=120.0, dt=1.0):
        t = np.arange(0.0, tf + dt, dt)
        x0 = np.zeros(2)
        x = odeint(self.state_rhs, x0, t, args=(u,))
        pH_dev = np.array([self.output_pH_deviation(xi) for xi in x])
        return t, x, pH_dev
```

## What to reuse in the current project

Do not copy the chemistry directly. Reuse the modeling pattern:

1. keep deviation variables separate from absolute concentrations,
2. solve pH algebraically from concentrations,
3. use robust pH initial guesses,
4. store both absolute pH and pH deviation,
5. treat pH as a nonlinear measurement, not as a direct state.

For the current acetate-buffer project, the analogous structure is:

```text
flowrates -> mixed analytical concentrations -> equilibrium pH solve -> measured pH
```

Later dynamic model:

```text
flowrates -> concentration/residence-time dynamics -> equilibrium pH solve -> sensor delay/noise
```
