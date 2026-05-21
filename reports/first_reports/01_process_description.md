# 01 - pH Process Description

## Known process

The current lab process is an inline mixing setup for acetate buffer preparation. The three inlet streams are:

| Stream | Chemical | Concentration | Flow range |
|---|---:|---:|---:|
| Acid | Acetic acid, CH3COOH | 100 mM | 1-10 mL/min |
| Conjugate base | Sodium acetate, CH3COONa | 100 mM | 1-10 mL/min |
| Water | Arium ultrapure water | 0 mM buffer species | 1-10 mL/min |

The first control objective is:

$$
\mathrm{pH}_{out} \approx \mathrm{pH}_{sp}
$$

where $\mathrm{pH}_{sp}$ is user-defined.

## Chemistry point

This process is not a strong acid/strong base neutralization problem. It is a weak-acid/conjugate-base buffer system.

The relevant pair is:

$$
\mathrm{CH_3COOH/CH_3COO^-}
$$

Acetic acid equilibrium:

$$
\mathrm{CH_3COOH \rightleftharpoons H^+ + CH_3COO^-}
$$

Sodium acetate dissociation:

$$
\mathrm{CH_3COONa \rightarrow Na^+ + CH_3COO^-}
$$

The pH is mainly controlled by the ratio of acetate to acetic acid.

## Role of water

Water does not directly set the ideal pH ratio when both buffer stock concentrations are equal. It mainly affects:

- dilution,
- buffer strength,
- total flowrate,
- residence time,
- transport delay,
- sensitivity to sensor noise and contamination.

The total flowrate is:

$$
F_T=F_H+F_A+F_W
$$

The approximate mixed concentrations are:

$$
[HA]=0.1\frac{F_H}{F_T}
$$

$$
[A^-]=0.1\frac{F_A}{F_T}
$$

so:

$$
\frac{[A^-]}{[HA]}=\frac{F_A}{F_H}
$$

## First model implication

Using Henderson-Hasselbalch:

$$
\mathrm{pH}_{ss}\approx pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

For acetic acid:

$$
pK_a\approx4.76
$$

Therefore:

$$
\mathrm{pH}_{ss}\approx4.76+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

With $1\leq F_H,F_A\leq10$, the ideal ratio range is:

$$
0.1\leq\frac{F_A}{F_H}\leq10
$$

so the ideal pH range is about:

$$
3.76\leq\mathrm{pH}_{ss}\leq5.76
$$

## Open lab questions

- How are the three pumps commanded?
- Can Python send flowrate setpoints?
- What is the pH sampling time?
- Where is the pH probe relative to the mixer?
- What is the transport delay?
- Are measured flowrates available or only pump setpoints?
- Is temperature measured?
- What are startup, flushing, and safety procedures?
