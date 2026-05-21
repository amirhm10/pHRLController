import numpy as np
import pandas as pd

from simulation.config import PHProcessConfig


def make_target_ph_grid(
    start: float = 3.8,
    stop: float = 5.7,
    num: int = 20,
    include_pka: bool = True,
    config: PHProcessConfig | None = None,
) -> np.ndarray:
    config = config or PHProcessConfig()
    values = np.linspace(start, stop, num)
    if include_pka:
        values = np.unique(np.append(values, config.pKa))
    return np.sort(values)


def make_flow_grid(
    acid_values=None,
    acetate_values=None,
    water_values=None,
    config: PHProcessConfig | None = None,
) -> pd.DataFrame:
    config = config or PHProcessConfig()
    if acid_values is None:
        acid_values = np.linspace(config.acid_flow_min, config.acid_flow_max, 10)
    if acetate_values is None:
        acetate_values = np.linspace(config.acetate_flow_min, config.acetate_flow_max, 10)
    if water_values is None:
        water_values = np.array([config.default_water_flow])

    records = []
    for acid_flow in acid_values:
        for acetate_flow in acetate_values:
            for water_flow in water_values:
                records.append({
                    "acid_flow": float(acid_flow),
                    "acetate_flow": float(acetate_flow),
                    "water_flow": float(water_flow),
                    "ratio": float(acetate_flow / acid_flow),
                })
    return pd.DataFrame(records)


def dataframe_from_records(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame.from_records(records)
