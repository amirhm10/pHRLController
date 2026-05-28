from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch


RESULTS_ROOT = Path("results")
METHOD_NAME = "biosmb_ph_plumbing_map"
VALVE_COLUMNS = "ABCDEFGHIJKLMNOP"
PH_ROWS = {
    2: ("Acetic acid", "#d9473f"),
    3: ("Sodium acetate", "#2b78c6"),
    4: ("Arium water", "#1b8f5a"),
}
PH_COLUMN = "P"


def main() -> None:
    run_time = datetime.now()
    output_dir = RESULTS_ROOT / f"{METHOD_NAME}_{run_time:%Y%m%d_%H%M%S}"
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure_path = figure_dir / "biosmb_ph_plumbing_map.png"
    render_figure(figure_path)
    print(f"Saved BioSMB pH plumbing figure: {figure_path}")


def render_figure(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 8), dpi=180)
    ax.set_facecolor("#f8f9fb")
    ax.set_xlim(-2.1, len(VALVE_COLUMNS) + 1.8)
    ax.set_ylim(16.2, -1.2)
    ax.axis("off")

    draw_grid(ax)
    draw_ph_annotations(ax)
    draw_title_and_notes(ax)

    fig.tight_layout(pad=0.5)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def draw_grid(ax) -> None:
    column_count = len(VALVE_COLUMNS)
    for row in range(1, 16):
        color = PH_ROWS.get(row, (None, "#b7bcc3"))[1]
        line_width = 2.4 if row in PH_ROWS else 0.9
        alpha = 0.9 if row in PH_ROWS else 0.55
        ax.plot(
            [0, column_count - 1],
            [row, row],
            color=color,
            linewidth=line_width,
            alpha=alpha,
            zorder=1,
        )
    for col_idx, _ in enumerate(VALVE_COLUMNS):
        ax.plot(
            [col_idx, col_idx],
            [1, 15],
            color="#aeb4bb",
            linewidth=0.8,
            alpha=0.6,
            zorder=1,
        )

    for col_idx, column in enumerate(VALVE_COLUMNS):
        ax.text(
            col_idx,
            0.35,
            column,
            ha="center",
            va="center",
            fontsize=9,
            color="#30343b",
            fontweight="bold",
        )
        ax.text(
            col_idx,
            15.75,
            column,
            ha="center",
            va="center",
            fontsize=9,
            color="#30343b",
            fontweight="bold",
        )
        for row in range(1, 16):
            is_ph_valve = column == PH_COLUMN and row in PH_ROWS
            face = PH_ROWS[row][1] if is_ph_valve else "#e7e8ea"
            edge = "#1f2328" if is_ph_valve else "#878c93"
            width = 1.7 if is_ph_valve else 0.9
            radius = 0.145 if is_ph_valve else 0.105
            ax.add_patch(
                Circle(
                    (col_idx, row),
                    radius=radius,
                    facecolor=face,
                    edgecolor=edge,
                    linewidth=width,
                    zorder=3 if is_ph_valve else 2,
                )
            )
    for row in range(1, 16):
        ax.text(
            -0.55,
            row,
            str(row),
            ha="right",
            va="center",
            fontsize=8,
            color="#4a4f57",
        )


def draw_ph_annotations(ax) -> None:
    p_col_idx = VALVE_COLUMNS.index(PH_COLUMN)
    for row, (label, color) in PH_ROWS.items():
        ax.add_patch(
            FancyBboxPatch(
                (-1.85, row - 0.33),
                1.25,
                0.66,
                boxstyle="round,pad=0.06,rounding_size=0.08",
                facecolor=color,
                edgecolor=color,
                alpha=0.13,
                linewidth=0.0,
                zorder=0,
            )
        )
        ax.text(
            -1.76,
            row,
            label,
            ha="left",
            va="center",
            fontsize=10,
            color="#1f2328",
            fontweight="bold",
        )
        ax.text(
            p_col_idx + 0.33,
            row - 0.24,
            f"P{row}",
            ha="left",
            va="center",
            fontsize=10,
            color=color,
            fontweight="bold",
        )
    ax.annotate(
        "Expert sketch opens P2, P3, P4",
        xy=(p_col_idx, 3),
        xytext=(p_col_idx - 4.6, -0.35),
        fontsize=10,
        color="#1f2328",
        arrowprops={
            "arrowstyle": "->",
            "color": "#1f2328",
            "linewidth": 1.1,
            "shrinkA": 0,
            "shrinkB": 6,
        },
    )
    ax.annotate(
        "Confirmed pH readout:\nPH_2 = biosmb.get_ph(2)",
        xy=(p_col_idx, 3.9),
        xytext=(p_col_idx - 3.4, 7.1),
        fontsize=10,
        color="#1f2328",
        bbox={
            "boxstyle": "round,pad=0.35,rounding_size=0.12",
            "facecolor": "#ffffff",
            "edgecolor": "#c4c9d1",
            "linewidth": 0.8,
        },
        arrowprops={
            "arrowstyle": "->",
            "color": "#1f2328",
            "linewidth": 1.1,
            "shrinkA": 2,
            "shrinkB": 6,
        },
    )


def draw_title_and_notes(ax) -> None:
    ax.text(
        -1.85,
        -0.55,
        "BioSMB pH plumbing map",
        ha="left",
        va="center",
        fontsize=16,
        color="#15181d",
        fontweight="bold",
    )
    ax.text(
        -1.85,
        16.05,
        "Valve names are column letter plus row number. Columns run A to P from left to right. Rows 2-4 are the pH inlet rows.",
        ha="left",
        va="center",
        fontsize=9,
        color="#4a4f57",
    )


if __name__ == "__main__":
    main()
