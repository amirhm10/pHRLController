# pH RL Controller - Project Overview

## Current process

The current lab process is an inline acetate buffer mixing setup. Three streams are mixed:

| Stream | Chemical | Nominal concentration | Flow range |
|---|---:|---:|---:|
| Acid | Acetic acid, CH3COOH | 100 mM | 1-10 mL/min |
| Conjugate base | Sodium acetate, CH3COONa | 100 mM | 1-10 mL/min |
| Water | Arium ultrapure water | 0 mM buffer species | 1-10 mL/min |

The main objective is to track a user-defined outlet pH. The first useful pH range is expected to be around 3.76 to 5.76 because the acid and acetate pumps are bounded between 1 and 10 mL/min.

## Important chemistry point

This is not a strong acid/strong base neutralization problem. It is an acetate buffer preparation problem.

The relevant pair is:

$$
\mathrm{CH_3COOH/CH_3COO^-}
$$

The pH is mainly determined by the sodium acetate to acetic acid ratio:

$$
\frac{F_A}{F_H}
$$

where:

- $F_H$ is the acetic acid flowrate,
- $F_A$ is the sodium acetate flowrate.

Water mostly affects dilution, total flowrate, residence time, and measurement delay.

## Current code models

### Model 1: simple model

File:

```text
simulation/simple_buffer_model.py
```

Uses Henderson-Hasselbalch:

$$
\mathrm{pH}_{ss}=pK_a+\log_{10}\left(\frac{F_A}{F_H}\right)
$$

with:

$$
pK_a \approx 4.76
$$

This model is useful for fast flow guesses and target-pH-to-ratio conversion.

### Model 2: equilibrium model

File:

```text
simulation/equilibrium_buffer_model.py
```

Uses a charge-balance equation:

$$
f(H)=H+C_{Na}-C_T\frac{K_a}{K_a+H}-\frac{K_w}{H}=0
$$

then:

$$
\mathrm{pH}=-\log_{10}(H)
$$

This is still steady-state, but it includes dilution, sodium charge balance, acid equilibrium, and water self-ionization.

## Current runnable script

File:

```text
run_initial_simulation.py
```

The script:

1. creates a target pH grid from about 3.8 to 5.7,
2. computes feasible acid, acetate, and water flowrates,
3. evaluates both the simple and equilibrium models,
4. saves stamped plots to `results/<method>_<YYYYMMDD_HHMMSS>/figures/`,
5. saves the sweep table to `results/<method>_<YYYYMMDD_HHMMSS>/tables/initial_ph_sweep.csv`.

Run with:

```bash
python run_initial_simulation.py
```

## Near-term plan

1. Use the current steady-state models to generate initial flow guesses.
2. Compare model predictions against lab data.
3. Fit effective $pK_a$ and possible pH bias.
4. Add a first-order-plus-delay dynamic layer.
5. Add feedback control.
6. Add residual RL only after the model-based baseline is reliable.

## Notes copied from the vault

See:

```text
reports/first_reports/
```

These local reports are included because Codex may not have access to the Obsidian vault.
