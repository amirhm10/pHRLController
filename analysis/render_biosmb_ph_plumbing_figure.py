from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle


RESULTS_ROOT = Path("results")
METHOD_NAME = "biosmb_ph_plumbing_map"
VALVE_COLUMNS = "ABCDEFGHIJKLMNOP"
PH_ROWS = {
    2: ("Acetic acid", "100 mM", "#d1495b"),
    3: ("Sodium acetate", "100 mM", "#2978b5"),
    4: ("Arium water", "", "#1b998b"),
}
PH_COLUMN = "P"
BACKGROUND = "#f5f7fb"
INK = "#1c2430"
MUTED = "#667085"
GRID = "#b8c0cc"


def main() -> None:
    run_time = datetime.now()
    output_dir = RESULTS_ROOT / f"{METHOD_NAME}_{run_time:%Y%m%d_%H%M%S}"
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure_path = figure_dir / "biosmb_ph_plumbing_map.png"
    render_figure(figure_path)
    print(f"Saved BioSMB pH plumbing figure: {figure_path}")


def render_figure(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(17.2, 9.2), dpi=200)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    ax.set_xlim(-3.1, len(VALVE_COLUMNS) + 2.25)
    ax.set_ylim(16.9, -1.95)
    ax.axis("off")

    draw_soft_panel(ax)
    draw_column_headers(ax)
    draw_grid_lines(ax)
    draw_valves(ax)
    draw_stream_labels(ax)
    draw_p_column_callout(ax)
    draw_ph2_callout(ax)
    draw_title_and_footer(ax)

    fig.tight_layout(pad=0.35)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def draw_soft_panel(ax) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (-2.82, -0.78),
            19.72,
            16.75,
            boxstyle="round,pad=0.035,rounding_size=0.32",
            facecolor="#ffffff",
            edgecolor="#d9dee7",
            linewidth=1.2,
            zorder=0,
        )
    )
    ax.add_patch(
        Rectangle(
            (-2.82, -0.78),
            19.72,
            1.18,
            facecolor="#edf1f7",
            edgecolor="none",
            zorder=0.1,
        )
    )


def draw_column_headers(ax) -> None:
    for col_idx, column in enumerate(VALVE_COLUMNS):
        is_p = column == PH_COLUMN
        ax.text(
            col_idx,
            -0.12,
            column,
            ha="center",
            va="center",
            fontsize=9.5,
            color=INK if is_p else MUTED,
            fontweight="bold" if is_p else "normal",
            zorder=5,
        )
        if is_p:
            ax.add_patch(
                FancyBboxPatch(
                    (col_idx - 0.36, -0.46),
                    0.72,
                    0.66,
                    boxstyle="round,pad=0.02,rounding_size=0.1",
                    facecolor="#fff2cc",
                    edgecolor="#e1b74f",
                    linewidth=1.0,
                    zorder=4,
                )
            )


def draw_grid_lines(ax) -> None:
    column_count = len(VALVE_COLUMNS)
    for row in range(1, 16):
        if row in PH_ROWS:
            color = PH_ROWS[row][2]
            linewidth = 3.3
            alpha = 0.95
        else:
            color = GRID
            linewidth = 0.8
            alpha = 0.43
        ax.plot(
            [0, column_count - 1],
            [row, row],
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            solid_capstyle="round",
            zorder=1,
        )

    for col_idx, column in enumerate(VALVE_COLUMNS):
        color = "#d7aa2d" if column == PH_COLUMN else GRID
        linewidth = 2.1 if column == PH_COLUMN else 0.8
        alpha = 0.85 if column == PH_COLUMN else 0.5
        ax.plot(
            [col_idx, col_idx],
            [1, 15],
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            solid_capstyle="round",
            zorder=1,
        )


def draw_valves(ax) -> None:
    for col_idx, column in enumerate(VALVE_COLUMNS):
        for row in range(1, 16):
            is_ph_valve = column == PH_COLUMN and row in PH_ROWS
            face = PH_ROWS[row][2] if is_ph_valve else "#eef1f5"
            edge = "#111827" if is_ph_valve else "#9aa3af"
            radius = 0.17 if is_ph_valve else 0.115
            linewidth = 1.9 if is_ph_valve else 0.8
            alpha = 1.0 if is_ph_valve else 0.92
            ax.add_patch(
                Circle(
                    (col_idx, row),
                    radius=radius,
                    facecolor=face,
                    edgecolor=edge,
                    linewidth=linewidth,
                    alpha=alpha,
                    zorder=3,
                )
            )


def draw_stream_labels(ax) -> None:
    for row in range(1, 16):
        ax.text(
            -0.52,
            row,
            str(row),
            ha="right",
            va="center",
            fontsize=8,
            color=MUTED,
            zorder=5,
        )

    for row, (stream, concentration, color) in PH_ROWS.items():
        ax.add_patch(
            FancyBboxPatch(
                (-2.55, row - 0.37),
                1.72,
                0.74,
                boxstyle="round,pad=0.08,rounding_size=0.16",
                facecolor=color,
                edgecolor="none",
                alpha=0.13,
                zorder=2,
            )
        )
        ax.add_patch(
            Circle(
                (-2.34, row),
                radius=0.075,
                facecolor=color,
                edgecolor=color,
                zorder=3,
            )
        )
        label = stream if not concentration else f"{stream}\n{concentration}"
        ax.text(
            -2.2,
            row,
            label,
            ha="left",
            va="center",
            fontsize=9.5,
            color=INK,
            linespacing=1.05,
            fontweight="bold",
            zorder=5,
        )


def draw_p_column_callout(ax) -> None:
    p_col_idx = VALVE_COLUMNS.index(PH_COLUMN)
    ax.add_patch(
        FancyBboxPatch(
            (p_col_idx - 0.44, 1.55),
            0.88,
            3.02,
            boxstyle="round,pad=0.08,rounding_size=0.2",
            facecolor="#fff8e6",
            edgecolor="#e1b74f",
            linewidth=1.1,
            alpha=0.72,
            zorder=2,
        )
    )
    for row, (_, _, color) in PH_ROWS.items():
        ax.text(
            p_col_idx + 0.31,
            row - 0.22,
            f"P{row}",
            ha="left",
            va="center",
            fontsize=10.5,
            color=color,
            fontweight="bold",
            zorder=6,
        )
    ax.annotate(
        "Expert demo opens\nP2, P3, P4",
        xy=(p_col_idx, 3.0),
        xytext=(p_col_idx - 3.25, 0.82),
        fontsize=10.5,
        color=INK,
        ha="center",
        va="center",
        bbox={
            "boxstyle": "round,pad=0.35,rounding_size=0.18",
            "facecolor": "#fff8e6",
            "edgecolor": "#e1b74f",
            "linewidth": 1.0,
        },
        arrowprops={
            "arrowstyle": "->",
            "color": "#8a6b10",
            "linewidth": 1.35,
            "shrinkA": 2,
            "shrinkB": 8,
        },
        zorder=8,
    )


def draw_ph2_callout(ax) -> None:
    p_col_idx = VALVE_COLUMNS.index(PH_COLUMN)
    ax.annotate(
        "Confirmed measurement\nPH_2 = biosmb.get_ph(2)",
        xy=(p_col_idx, 4.0),
        xytext=(10.4, 7.35),
        fontsize=11,
        color=INK,
        ha="left",
        va="center",
        bbox={
            "boxstyle": "round,pad=0.42,rounding_size=0.18",
            "facecolor": "#f4f7ff",
            "edgecolor": "#9fb7e8",
            "linewidth": 1.0,
        },
        arrowprops={
            "arrowstyle": "->",
            "color": "#486cb5",
            "linewidth": 1.35,
            "shrinkA": 2,
            "shrinkB": 8,
        },
        zorder=8,
    )
    ax.text(
        10.4,
        8.42,
        "Physical outlet tubing after this pH path remains unverified.",
        ha="left",
        va="center",
        fontsize=8.8,
        color=MUTED,
        zorder=8,
    )


def draw_title_and_footer(ax) -> None:
    ax.text(
        -2.55,
        -1.25,
        "BioSMB pH plumbing map",
        ha="left",
        va="center",
        fontsize=18,
        color=INK,
        fontweight="bold",
        zorder=6,
    )
    ax.text(
        -2.55,
        -0.72,
        "Valve coordinates are column letter + row number. Columns run left-to-right from A to P.",
        ha="left",
        va="center",
        fontsize=9.5,
        color=MUTED,
        zorder=6,
    )
    ax.text(
        -2.55,
        16.25,
        "Rows 2-4 carry the pH inlet streams. Pump 1 is not used; pumps 2-4 map to acid, acetate, and water.",
        ha="left",
        va="center",
        fontsize=9,
        color=MUTED,
        zorder=6,
    )


if __name__ == "__main__":
    main()
