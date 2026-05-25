from datetime import datetime
from pathlib import Path

from helpers.experiment_grid import dataframe_from_records, make_target_ph_grid
from helpers.plotting import (
    plot_flow_allocation,
    plot_model_difference,
    plot_ratio_map,
    plot_target_sweep,
    setup_output_dir,
)
from simulation.config import PHProcessConfig
from simulation.equilibrium_buffer_model import EquilibriumBufferModel
from simulation.simple_buffer_model import SimpleBufferModel


def main():
    config = PHProcessConfig()
    simple_model = SimpleBufferModel(config)
    equilibrium_model = EquilibriumBufferModel(config)

    method_name = "equilibrium_charge_balance"
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    stamp_text = f"method={method_name} | run_time={run_time_display}"

    result_dir = setup_output_dir(Path("results") / f"{method_name}_{run_stamp}")
    figure_dir = setup_output_dir(result_dir / "figures")
    table_dir = setup_output_dir(result_dir / "tables")

    target_ph_values = make_target_ph_grid(
        start=3.8,
        stop=5.7,
        num=20,
        include_pka=True,
        config=config,
    )

    records = []
    for target_ph in target_ph_values:
        result = equilibrium_model.flows_from_target(
            target_ph,
            water_flow=config.default_water_flow,
            buffer_flow_sum=config.default_buffer_flow_sum,
            clip=True,
        )
        records.append(result)

    df = dataframe_from_records(records)
    df["run_method"] = method_name
    df["run_time"] = run_time_display
    df.to_csv(table_dir / "initial_ph_sweep.csv", index=False)

    plot_target_sweep(df, figure_dir / "target_ph_sweep.png", stamp_text=stamp_text)
    plot_flow_allocation(df, figure_dir / "flow_allocation.png", stamp_text=stamp_text)
    plot_model_difference(df, figure_dir / "model_difference.png", stamp_text=stamp_text)
    plot_ratio_map(df, figure_dir / "ratio_map.png", stamp_text=stamp_text)

    print("Initial pH sweep completed.")
    print(f"Method: {method_name}")
    print(f"Run time: {run_time_display}")
    print(f"Saved result directory: {result_dir}")
    print(f"Saved table: {table_dir / 'initial_ph_sweep.csv'}")
    print(f"Saved figures in: {figure_dir}")
    print()
    print(df[[
        "target_ph_used",
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "ph_simple",
        "ph_equilibrium",
        "ph_difference",
    ]].round(4).to_string(index=False))

    example_conditions(simple_model, equilibrium_model, config)


def example_conditions(simple_model, equilibrium_model, config):
    print("\nExample fixed-flow evaluations:")
    examples = [
        (10.0, 1.0, config.default_water_flow),
        (5.0, 5.0, config.default_water_flow),
        (1.0, 10.0, config.default_water_flow),
        (4.0, 7.0, 3.0),
    ]
    for acid_flow, acetate_flow, water_flow in examples:
        ph_simple = simple_model.predict_ph(acid_flow, acetate_flow, water_flow)
        ph_equilibrium = equilibrium_model.predict_ph(acid_flow, acetate_flow, water_flow)
        print(
            f"FH={acid_flow:.2f}, FA={acetate_flow:.2f}, FW={water_flow:.2f} | "
            f"simple pH={ph_simple:.4f}, equilibrium pH={ph_equilibrium:.4f}"
        )


if __name__ == "__main__":
    main()
