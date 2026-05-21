from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def setup_output_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def plot_target_sweep(df, output_path: str | Path | None = None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["target_ph_used"], df["ph_simple"], marker="o", linewidth=2, label="Simple model")
    ax.plot(df["target_ph_used"], df["ph_equilibrium"], marker="s", linewidth=2, label="Equilibrium model")
    ax.plot(df["target_ph_used"], df["target_ph_used"], linestyle="--", linewidth=2, label="Target pH")
    ax.set_xlabel("Target pH")
    ax.set_ylabel("Predicted pH")
    ax.set_title("Target pH sweep")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save_if_requested(fig, output_path)
    return fig, ax


def plot_flow_allocation(df, output_path: str | Path | None = None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["target_ph_used"], df["acid_flow"], marker="o", linewidth=2, label="Acetic acid flow")
    ax.plot(df["target_ph_used"], df["acetate_flow"], marker="s", linewidth=2, label="Sodium acetate flow")
    ax.plot(df["target_ph_used"], df["water_flow"], marker="^", linewidth=2, label="Water flow")
    ax.set_xlabel("Target pH")
    ax.set_ylabel("Flowrate (mL/min)")
    ax.set_title("Flow allocation from target pH")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save_if_requested(fig, output_path)
    return fig, ax


def plot_model_difference(df, output_path: str | Path | None = None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axhline(0.0, linestyle="--", linewidth=2)
    ax.plot(df["target_ph_used"], df["ph_difference"], marker="o", linewidth=2)
    ax.set_xlabel("Target pH")
    ax.set_ylabel("pH difference: equilibrium - simple")
    ax.set_title("Difference between pH models")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save_if_requested(fig, output_path)
    return fig, ax


def plot_ratio_map(df, output_path: str | Path | None = None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["ratio"], df["ph_equilibrium"], marker="o", linestyle="", label="Equilibrium model")
    ax.plot(df["ratio"], df["ph_simple"], marker="x", linestyle="", label="Simple model")
    ax.set_xscale("log")
    ax.set_xlabel("Flow ratio FA/FH")
    ax.set_ylabel("Predicted pH")
    ax.set_title("pH as a function of acetate/acid flow ratio")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend()
    fig.tight_layout()
    _save_if_requested(fig, output_path)
    return fig, ax


def _save_if_requested(fig, output_path: str | Path | None):
    if output_path is None:
        return
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
