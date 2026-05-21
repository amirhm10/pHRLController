# 02 - Simplest Model First Try

## Purpose

This report documents the first usable pH model for the current acetate-buffer mixing process. The goal is not to capture every chemical detail. The goal is to get a physically meaningful first model that can generate initial flowrate commands before lab data are available.

## Main equation

For the first try, use:

$$
\boxed{\mathrm{pH}_{ss}=pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)}
$$

where:

- $F_H$ is the acetic acid flowrate,
- $F_A$ is the sodium acetate flowrate,
- $pK_a\approx4.76$ for acetic acid near room temperature.

With the current 100 mM acid and acetate stocks:

$$
\boxed{\mathrm{pH}_{ss}\approx4.76+\log_{10}\left(\frac{F_A}{F_H}\right)}
$$

## Derivation

For a weak-acid/conjugate-base buffer:

$$
\mathrm{pH}=pK_a+\log_{10}\left(\frac{[A^-]}{[HA]}\right)
$$

For this system:

$$
HA=\mathrm{CH_3COOH}
$$

$$
A^-=\mathrm{CH_3COO^-}
$$

The total flowrate is:

$$
F_T=F_H+F_A+F_W
$$

The mixed concentrations are approximately:

$$
[HA]=C_H^0\frac{F_H}{F_T}
$$

$$
[A^-]=C_A^0\frac{F_A}{F_T}
$$

Because both stock concentrations are equal:

$$
C_H^0=C_A^0=0.1\ \mathrm{M}
$$

so:

$$
\frac{[A^-]}{[HA]}=\frac{F_A}{F_H}
$$

This gives the simple model.

## Target pH to ratio

For a desired target pH:

$$
\frac{F_A}{F_H}=10^{\mathrm{pH}_{sp}-pK_a}
$$

Examples:

| Target pH | Required $F_A/F_H$ | Interpretation |
|---:|---:|---|
| 4.00 | 0.17 | acid-rich |
| 4.50 | 0.55 | more acid than acetate |
| 4.76 | 1.00 | equal acid and acetate |
| 5.00 | 1.74 | more acetate than acid |
| 5.50 | 5.50 | acetate-rich |

## Reachable pH range

With pump bounds:

$$
1\leq F_H,F_A\leq10
$$

The smallest and largest ratios are:

$$
\frac{F_A}{F_H}=0.1
$$

and:

$$
\frac{F_A}{F_H}=10
$$

Therefore:

$$
\mathrm{pH}_{min}=4.76+\log_{10}(0.1)=3.76
$$

$$
\mathrm{pH}_{max}=4.76+\log_{10}(10)=5.76
$$

So the ideal reachable range is about:

$$
\boxed{3.76\leq\mathrm{pH}_{ss}\leq5.76}
$$

## Flow allocation rule used in the starter code

The starter code first computes the required ratio:

$$
r=10^{\mathrm{pH}_{sp}-pK_a}
$$

A convenient first allocation is:

$$
F_H+F_A=S
$$

where the default is:

$$
S=10\ \mathrm{mL/min}
$$

Then:

$$
F_H=\frac{S}{1+r}
$$

$$
F_A=\frac{Sr}{1+r}
$$

The code then checks pump bounds and preserves the ratio when possible.

## Code location

Implemented in:

```text
simulation/simple_buffer_model.py
```

Main class:

```python
SimpleBufferModel
```

Important methods:

```python
predict_ph(acid_flow, acetate_flow, water_flow=None)
ratio_from_target(target_ph, clip=True)
flows_from_target(target_ph, water_flow=None, buffer_flow_sum=None, clip=True)
```

## Limitations

This model ignores:

- activity coefficients,
- water self-ionization,
- temperature dependence of $pK_a$,
- pH probe bias,
- pH probe dynamics,
- pump dynamics,
- transport delay,
- incomplete mixing.

It is a good first model, not the final model.
