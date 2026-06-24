from __future__ import annotations

import os
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve()
ROOT = _SCRIPT_PATH.parents[3]
SLIDE_DIR = _SCRIPT_PATH.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results" / ".matplotlib-cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIG_DIR = SLIDE_DIR / "figures"

PREPARED_PATH = (
    ROOT
    / "results/data_preparation_20260624_123926/tables/prepared_time_feature_data.csv"
)
HH_PATH = (
    ROOT
    / "results/henderson_hasselbalch_prepared_validation_20260624_125349"
    / "tables/hh_model_comparison.csv"
)
SHIFT_PATH = (
    ROOT
    / "results/hh_residual_shift_diagnostic_20260624_132406"
    / "tables/hh_model_comparison_with_shift_context.csv"
)
CHARGE_BALANCE_PATH = (
    ROOT
    / "results/hh_residual_shift_diagnostic_20260624_132406"
    / "tables/charge_balance_metrics.csv"
)
RAW_PATH = ROOT / "Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv"

PHASE_SPLIT = 309
SHIFT_SAMPLE = 183
PAPER_DPI = 300

MAROON = "#7a003c"
BLUE = "#1c4a75"
GREEN = "#2c765c"
RED = "#9c3a34"
ORANGE = "#d8642a"
PURPLE = "#5d4e7b"
GRAY = "#626262"
LIGHT1 = "#f5efe7"
LIGHT2 = "#e9f3ef"


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    prepared = pd.read_csv(PREPARED_PATH)
    hh = pd.read_csv(HH_PATH)
    shift = pd.read_csv(SHIFT_PATH)
    charge = pd.read_csv(CHARGE_BALANCE_PATH)
    raw = pd.read_csv(RAW_PATH)

    setup_style()
    make_data_overview(prepared)
    make_water_charge_balance(charge)
    make_hh_prediction_residual(hh)
    make_shift_context(shift, raw)
    make_pka_regime_summary(shift)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#222222",
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "font.family": "DejaVu Sans",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
        }
    )


def shade_phases(ax) -> None:
    ax.axvspan(0, PHASE_SPLIT, color=LIGHT1, alpha=0.65, zorder=-10)
    ax.axvspan(PHASE_SPLIT, 961, color=LIGHT2, alpha=0.65, zorder=-10)
    ax.axvline(PHASE_SPLIT, color="#555555", lw=1.1, ls="--")


def mark_shift(ax) -> None:
    ax.axvline(SHIFT_SAMPLE, color=RED, lw=1.3, ls="--")


def make_data_overview(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(12.2, 7.2),
        sharex=True,
        gridspec_kw={"hspace": 0.16},
    )
    series = [
        ("acid_flow", "Acetic acid flow", "mL/min", MAROON),
        ("acetate_flow", "Sodium acetate flow", "mL/min", GREEN),
        ("water_flow", "Arium water flow", "mL/min", BLUE),
        ("ph_measured", "Measured pH: PH_2 / pH-sensor", "pH", PURPLE),
    ]
    x = df["sample_index"]
    for ax, (col, title, ylabel, color) in zip(axes, series):
        shade_phases(ax)
        mark_shift(ax)
        ax.plot(x, df[col], color=color, lw=1.25)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", pad=2)
        ax.grid(True, alpha=0.20, lw=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[-1].set_xlabel("Sequential sample index")
    axes[0].text(
        0.015,
        0.88,
        "Phase 1: slower sampling",
        transform=axes[0].transAxes,
        fontsize=10,
        color=GRAY,
    )
    axes[0].text(
        0.58,
        0.88,
        "Phase 2: faster sampling",
        transform=axes[0].transAxes,
        fontsize=10,
        color=GRAY,
    )
    axes[-1].annotate(
        "sample 183",
        xy=(SHIFT_SAMPLE, df.loc[df["sample_index"].eq(SHIFT_SAMPLE), "ph_measured"].iloc[0]),
        xytext=(SHIFT_SAMPLE + 35, 3.72),
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.0},
        color=RED,
        fontsize=10,
    )
    fig.savefig(FIG_DIR / "slide_data_overview.png", dpi=PAPER_DPI)
    plt.close(fig)


def make_water_charge_balance(charge: pd.DataFrame) -> None:
    labels = ["0-182", "183-308", "309-961"]
    mean_diff = charge["mean_charge_balance_minus_hh"].to_numpy()
    max_diff = charge["max_charge_balance_minus_hh"].to_numpy()

    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    x = np.arange(len(labels))
    width = 0.34
    ax.bar(
        x - width / 2,
        mean_diff,
        width,
        label="mean charge-balance - HH",
        color=BLUE,
        alpha=0.88,
    )
    ax.bar(
        x + width / 2,
        max_diff,
        width,
        label="max charge-balance - HH",
        color=ORANGE,
        alpha=0.88,
    )
    ax.axhline(0.01, color=RED, lw=1.4, ls="--", label="0.01 pH")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("pH difference")
    ax.set_xlabel("Sample segment")
    ax.set_title("Full charge-balance model barely changes the HH prediction", loc="left")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(0, 0.012)
    for xpos, val in zip(x + width / 2, max_diff):
        ax.text(xpos, val + 0.00025, f"{val:.3f}", ha="center", va="bottom", fontsize=10)
    fig.savefig(FIG_DIR / "slide_water_charge_balance.png", dpi=PAPER_DPI)
    plt.close(fig)


def make_hh_prediction_residual(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(12.2, 6.7),
        sharex=True,
        gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.14},
    )
    x = df["sample_index"]
    ax = axes[0]
    shade_phases(ax)
    mark_shift(ax)
    ax.plot(x, df["ph_measured"], color=PURPLE, lw=1.35, label="PH_2 / pH-sensor")
    ax.plot(x, df["ph_predicted_hh"], color=ORANGE, lw=1.25, label="HH prediction")
    ax.set_ylabel("pH")
    ax.set_title("Measured pH follows the HH trend, but with a biased intercept", loc="left")
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax = axes[1]
    shade_phases(ax)
    mark_shift(ax)
    ax.axhline(0, color="#222222", lw=1.0)
    ax.plot(x, df["ph_minus_ph_predicted"], color=RED, lw=1.1)
    ax.set_ylabel("pH - HH")
    ax.set_xlabel("Sequential sample index")
    ax.grid(True, alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.savefig(FIG_DIR / "slide_hh_prediction_residual.png", dpi=PAPER_DPI)
    plt.close(fig)


def make_shift_context(shift: pd.DataFrame, raw: pd.DataFrame) -> None:
    raw = raw.copy()
    raw["sample_index"] = np.arange(len(raw))
    local = shift[(shift["sample_index"] >= 160) & (shift["sample_index"] <= 210)].copy()
    raw_local = raw[(raw["sample_index"] >= 160) & (raw["sample_index"] <= 210)].copy()

    fig, axes = plt.subplots(
        4,
        1,
        figsize=(13.0, 7.5),
        sharex=True,
        gridspec_kw={"height_ratios": [1.0, 1.1, 0.78, 0.98], "hspace": 0.18},
    )
    x = local["sample_index"]

    axes[0].axhline(0, color="#222222", lw=1.0)
    axes[0].plot(x, local["ph_minus_ph_predicted"], color=RED, lw=1.8)
    axes[0].set_ylabel("pH - HH")
    axes[0].set_title("Residual shift lines up with the session/reservoir reset", loc="left")

    axes[1].plot(x, local["ph_measured"], color=PURPLE, lw=1.8, label="PH_2 / pH-sensor")
    axes[1].plot(x, local["ph_predicted_hh"], color=ORANGE, lw=1.55, label="HH prediction")
    axes[1].set_ylabel("pH")
    axes[1].legend(frameon=False, ncol=2, loc="upper right")

    axes[2].plot(
        raw_local["sample_index"],
        raw_local["observation.biosmb-sensors.PH_1"],
        color=GRAY,
        lw=1.65,
    )
    axes[2].set_ylabel("PH_1")
    axes[2].set_title("PH_1 observation (context only, not used for metrics)", loc="left", pad=1)

    mass_cols = [
        ("observation.mfcs-mass.acid-mass-grams", "acid mass", MAROON),
        ("observation.mfcs-mass.sodium-mass-grams", "sodium mass", GREEN),
        ("observation.mfcs-mass.water-mass-grams", "water mass", BLUE),
    ]
    for col, label, color in mass_cols:
        axes[3].plot(
            raw_local["sample_index"],
            raw_local[col],
            lw=1.45,
            color=color,
            label=label,
        )
    axes[3].set_ylabel("reservoir mass (g)")
    axes[3].set_xlabel("Sequential sample index")
    axes[3].legend(frameon=False, ncol=3, loc="upper right")

    for ax in axes:
        ax.axvline(SHIFT_SAMPLE, color=RED, lw=1.4, ls="--")
        ax.grid(True, alpha=0.24)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].annotate(
        "sample 183",
        xy=(SHIFT_SAMPLE, local.loc[local["sample_index"].eq(SHIFT_SAMPLE), "ph_minus_ph_predicted"].iloc[0]),
        xytext=(SHIFT_SAMPLE + 4, -0.08),
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.0},
        color=RED,
        fontsize=11,
    )
    fig.savefig(FIG_DIR / "slide_shift_context.png", dpi=PAPER_DPI)
    plt.close(fig)


def make_pka_regime_summary(df: pd.DataFrame) -> None:
    data = df.copy()
    data["pka_app"] = data["ph_measured"] - data["log10_molar_base_acid_ratio"]
    masks = [
        data["sample_index"] < SHIFT_SAMPLE,
        (data["sample_index"] >= SHIFT_SAMPLE) & (data["sample_index"] < PHASE_SPLIT),
        data["sample_index"] >= PHASE_SPLIT,
    ]
    names = ["0-182", "183-308", "309-961"]
    values = [float(data.loc[m, "pka_app"].mean()) for m in masks]
    residuals = [float(data.loc[m, "ph_minus_ph_predicted"].mean()) for m in masks]

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.2, 5.0),
        gridspec_kw={"width_ratios": [2.0, 1.0], "wspace": 0.35},
    )
    ax = axes[0]
    shade_phases(ax)
    mark_shift(ax)
    ax.plot(data["sample_index"], data["pka_app"], color=PURPLE, lw=1.05, alpha=0.90)
    ax.axhline(4.756, color=GREEN, lw=1.4, ls="--", label="literature pKa near 25 C")
    for m, val, label in zip(masks, values, names):
        xmin = data.loc[m, "sample_index"].min()
        xmax = data.loc[m, "sample_index"].max()
        ax.hlines(val, xmin, xmax, colors=RED, lw=2.4)
        ax.text((xmin + xmax) / 2, val + 0.035, f"{label}: {val:.3f}", ha="center", fontsize=10, color=RED)
    ax.set_ylabel("apparent pKa")
    ax.set_xlabel("Sequential sample index")
    ax.set_title("Apparent pKa is reasonable before sample 183, then shifts down", loc="left")
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=False, loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax = axes[1]
    colors = [GREEN, ORANGE, RED]
    y_pos = np.arange(len(names))
    ax.barh(y_pos, residuals, color=colors, alpha=0.88)
    ax.set_yticks([])
    ax.axvline(0, color="#222222", lw=1.0)
    ax.set_xlabel("mean residual")
    ax.set_title("pH - HH", loc="left")
    ax.set_xlim(-0.36, 0.02)
    for y, (name, val) in enumerate(zip(names, residuals)):
        if abs(val) < 0.08:
            text_x = val - 0.006
            text_color = "#222222"
            ha = "right"
        else:
            text_x = val + 0.012
            text_color = "white"
            ha = "left"
        ax.text(
            text_x,
            y,
            f"{name}: {val:.3f}",
            ha=ha,
            va="center",
            color=text_color,
            fontsize=11,
            fontweight="bold",
        )
    ax.grid(True, axis="x", alpha=0.20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.savefig(FIG_DIR / "slide_pka_regime_summary.png", dpi=PAPER_DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
