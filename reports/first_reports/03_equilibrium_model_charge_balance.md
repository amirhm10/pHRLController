# 03 - Equilibrium Model Charge Balance

## Purpose

This report documents the second steady-state model for the acetate-buffer process. It moves one step beyond Henderson-Hasselbalch by solving a charge-balance equation for the hydrogen ion concentration.

This model is still not dynamic. It does not include mixing delay, pump dynamics, or pH probe dynamics.

## Why use this model?

The simple model is:

$$
\mathrm{pH}_{HH}=pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

This is good for intuition and first flow guesses. However, it assumes the analytical mixing ratio is close to the equilibrium ratio. That can become less accurate when the solution is dilute or when water self-ionization becomes important.

The equilibrium model uses:

- analytical concentration balances,
- acetic acid equilibrium,
- sodium charge balance,
- water self-ionization.

## Mixed concentrations

Define:

$$
F_T=F_H+F_A+F_W
$$

The mixed analytical acid contribution is:

$$
C_H=C_H^0\frac{F_H}{F_T}
$$

The mixed analytical acetate contribution is:

$$
C_A=C_A^0\frac{F_A}{F_T}
$$

For the current system:

$$
C_H^0=C_A^0=0.1\ \mathrm{M}
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

## Acid equilibrium

For acetic acid:

$$
HA \rightleftharpoons H^+ + A^-
$$

$$
K_a=\frac{[H^+][A^-]}{[HA]}
$$

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

with:

$$
K_w\approx10^{-14}
$$

## Charge balance

Total positive charge equals total negative charge:

$$
H+C_{Na}=[A^-](H)+[OH^-](H)
$$

Substitute the equations:

$$
H+C_{Na}=C_T\frac{K_a}{K_a+H}+\frac{K_w}{H}
$$

Move all terms to one side:

$$
\boxed{f(H)=H+C_{Na}-C_T\frac{K_a}{K_a+H}-\frac{K_w}{H}=0}
$$

Then:

$$
\boxed{\mathrm{pH}=-\log_{10}(H)}
$$

## Code location

Implemented in:

```text
simulation/equilibrium_buffer_model.py
```

Main class:

```python
EquilibriumBufferModel
```

Important methods:

```python
mixed_concentrations(acid_flow, acetate_flow, water_flow)
predict_ph(acid_flow, acetate_flow, water_flow)
compare_to_simple(acid_flow, acetate_flow, water_flow)
flows_from_target(target_ph, water_flow=None, buffer_flow_sum=None, clip=True)
```

## Implementation idea

The code solves the charge balance in pH-space:

```python
def charge_balance_in_pH(pH):
    H = 10 ** (-pH)
    acetate = C_T * Ka / (Ka + H)
    hydroxide = Kw / H
    return H + C_Na - acetate - hydroxide

pH = brentq(charge_balance_in_pH, 0.0, 14.0)
```

Solving in pH-space is convenient because it brackets the solution over the physical pH range 0 to 14.

## Relation to simple model

The equilibrium model should be close to the simple model in the normal concentration range. If the two models strongly disagree under normal operating conditions, possible causes include:

- wrong stock concentration assumptions,
- wrong pKa value,
- temperature effects,
- pH probe bias,
- nonideal activity effects,
- or a coding error.

## What this model still ignores

This model does not include:

- transport delay,
- pH probe response time,
- pump dynamics,
- incomplete mixing,
- temperature-dependent pKa and Kw,
- activity coefficient corrections,
- dissolved carbon dioxide effects.

These are later layers.
