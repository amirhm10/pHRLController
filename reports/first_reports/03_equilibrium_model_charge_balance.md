---
title: "pH Process - Equilibrium Model Charge Balance"
tags:
  - pH-control
  - acetate-buffer
  - charge-balance
  - equilibrium-model
  - first-principles-model
status: draft
created: 2026-05-20
---

# pH Process - Equilibrium Model Charge Balance

## 1. Purpose

The previous note used the simplest Henderson-Hasselbalch model:

$$
\mathrm{pH}_{ss}\approx pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

That model is useful for intuition and first flow guesses. This note moves one step further by solving an equilibrium charge-balance model for the acetate buffer.

The new model is still steady-state, but it explicitly includes:

- dilution through the total flowrate,
- weak-acid equilibrium,
- sodium ion from sodium acetate,
- water self-ionization,
- electroneutrality.

This is the next model before adding pH probe delay, mixing dynamics, and feedback control.

## 2. Why move beyond Henderson-Hasselbalch?

The Henderson-Hasselbalch equation estimates the pH of a weak-acid/conjugate-base buffer from the acid/base ratio.[^hh]

For this project, it gives:

$$
\mathrm{pH}_{HH}=pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

However, it assumes that the equilibrium ratio $[A^-]/[HA]$ is close to the analytical mixing ratio. This is usually good for normal buffer concentrations, but it can become less accurate when the solution is very dilute, when one species is nearly absent, or when water self-ionization matters.[^po-senozan]

The charge-balance model keeps the same chemistry but solves the equilibrium more directly.

## 3. Model workflow

![Equilibrium model workflow](assets/equilibrium_model_workflow.svg)

The idea is:

1. Calculate mixed analytical concentrations from the three flowrates.
2. Use the acid equilibrium to express $[HA]$ and $[A^-]$ as functions of $H=[H^+]$.
3. Use water self-ionization to express $[OH^-]$ as a function of $H$.
4. Solve charge balance for $H$.
5. Convert $H$ to pH.

Strictly, pH is defined using hydrogen ion activity, not just concentration.[^iupac-ph] Here we still approximate activity by concentration, so this is not yet a full activity-coefficient model.

## 4. Mixed analytical concentrations

Define:

$$
F_H = \text{acetic acid flowrate}
$$

$$
F_A = \text{sodium acetate flowrate}
$$

$$
F_W = \text{water flowrate}
$$

$$
F_T=F_H+F_A+F_W
$$

The stock concentrations are:

$$
C_H^0=0.1\ \mathrm{M}
$$

$$
C_A^0=0.1\ \mathrm{M}
$$

After ideal mixing:

$$
C_H=C_H^0\frac{F_H}{F_T}
$$

$$
C_A=C_A^0\frac{F_A}{F_T}
$$

The total acetate-family concentration is:

$$
C_T=C_H+C_A
$$

where:

$$
C_T=[HA]+[A^-]
$$

The sodium concentration is:

$$
C_{Na}=C_A
$$

because sodium acetate contributes one sodium ion per acetate-family species.

## 5. Equilibrium speciation

Use:

$$
HA \rightleftharpoons H^+ + A^-
$$

$$
K_a=\frac{[H^+][A^-]}{[HA]}
$$

For acetic acid near room temperature:

$$
pK_a\approx4.76
$$

This should later be fitted as an effective parameter because temperature, ionic strength, and calibration may shift the apparent value.[^pubchem-acetic]

Let:

$$
H=[H^+]
$$

Then:

$$
[HA](H)=C_T\frac{H}{K_a+H}
$$

$$
[A^-](H)=C_T\frac{K_a}{K_a+H}
$$

Water self-ionization gives:

$$
[OH^-](H)=\frac{K_w}{H}
$$

with the common room-temperature approximation:

$$
K_w\approx10^{-14}
$$

## 6. Charge balance

![Charge balance in the acetate buffer model](assets/equilibrium_model_charge_balance.svg)

At equilibrium, total positive charge equals total negative charge:

$$
H+C_{Na}=[A^-](H)+[OH^-](H)
$$

Substitute the speciation equations:

$$
H+C_{Na}=C_T\frac{K_a}{K_a+H}+\frac{K_w}{H}
$$

Move everything to one side:

$$
\boxed{f(H)=H+C_{Na}-C_T\frac{K_a}{K_a+H}-\frac{K_w}{H}=0}
$$

After solving this scalar nonlinear equation:

$$
\boxed{\mathrm{pH}=-\log_{10}(H)}
$$

## 7. Comparison with the simplest model

![Henderson-Hasselbalch versus exact equilibrium model](assets/equilibrium_model_hh_vs_exact.svg)

At normal buffer concentration, for example $C_T=50\ \mathrm{mM}$, the charge-balance model and Henderson-Hasselbalch prediction are almost the same.

At very dilute concentration, for example $C_T=1\ \mathrm{mM}$, the difference becomes larger. This happens because the buffer species no longer dominate the equilibrium as strongly, and water self-ionization becomes more relevant.

## 8. When does Henderson-Hasselbalch start to fail?

![Error versus total buffer concentration](assets/equilibrium_model_error_vs_concentration.svg)

The plotted quantity is:

$$
\mathrm{error}=\mathrm{pH}_{eq}-\mathrm{pH}_{HH}
$$

The green region shows the approximate total buffer concentration range expected from $100\ \mathrm{mM}$ stocks and $1$ to $10\ \mathrm{mL/min}$ pump bounds.

The main takeaway is:

- in the expected operating range, the simple model is probably close,
- at very low concentration, the equilibrium model is safer,
- acid-rich cases can be more sensitive to dilution.

## 9. Python implementation

```python
import numpy as np
from scipy.optimize import brentq


def ph_equilibrium_acetate(
    F_H,
    F_A,
    F_W,
    C_H0=0.1,
    C_A0=0.1,
    pKa=4.76,
    Kw=1e-14,
):
    if F_H <= 0 or F_A <= 0 or F_W < 0:
        raise ValueError("Flowrates must be physically valid.")

    F_T = F_H + F_A + F_W
    C_H = C_H0 * F_H / F_T
    C_A = C_A0 * F_A / F_T

    C_T = C_H + C_A
    C_Na = C_A
    Ka = 10 ** (-pKa)

    def charge_balance_in_pH(pH):
        H = 10 ** (-pH)
        A_minus = C_T * Ka / (Ka + H)
        OH = Kw / H
        return H + C_Na - A_minus - OH

    return brentq(charge_balance_in_pH, 0.0, 14.0)
```

## 10. How to use this model

Use the models in this order:

1. Use Henderson-Hasselbalch for fast target-to-flow calculations.
2. Use the equilibrium model to check the predicted steady-state pH.
3. Fit an effective $pK_a$ and possible pH bias using lab data.
4. Add a first-order-plus-delay dynamic model.
5. Add feedback control.
6. Use residual RL only after the baseline works.

A useful corrected form after data collection is:

$$
\mathrm{pH}_{meas}\approx \mathrm{pH}_{eq}(F_H,F_A,F_W;pK_{a,eff})+b_{pH}
$$

where $pK_{a,eff}$ and $b_{pH}$ are fitted from lab data.

## 11. What this model still does not include

This model still ignores:

- pH probe dynamics,
- transport delay,
- pump dynamics,
- activity coefficients,
- temperature dependence of $K_a$ and $K_w$,
- dissolved carbon dioxide,
- incomplete mixing,
- sensor calibration drift.

These are later modeling layers.

## 12. References

[^hh]: Henderson-Hasselbalch equation overview and weak-acid/conjugate-base buffer form: https://en.wikipedia.org/wiki/Henderson%E2%80%93Hasselbalch_equation

[^iupac-ph]: IUPAC Gold Book definition of pH as a hydrogen ion activity quantity: https://goldbook.iupac.org/terms/view/P04524

[^pubchem-acetic]: PubChem compound summary for acetic acid, including chemical identity and acid dissociation information: https://pubchem.ncbi.nlm.nih.gov/compound/Acetic-Acid

[^po-senozan]: Po, H. N., and Senozan, N. M. "The Henderson-Hasselbalch Equation: Its History and Limitations." Journal of Chemical Education, 78, 1499-1503, 2001. DOI: https://doi.org/10.1021/ed078p1499
