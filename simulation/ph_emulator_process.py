from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


@dataclass
class PHEmulatorProcessConfig:
    """Configuration for the lightweight pH process used with the OPC emulator."""

    static_intercept: float = 0.6567
    static_slope: float = 0.7909
    response_tau_s: float = 25.0
    initial_ph: float = 4.5
    sensor_noise_std: float = 0.0
    random_seed: int = 7


class PHEmulatorProcess:
    """Static equilibrium chemistry plus first-order PH_2 response."""

    def __init__(
        self,
        process_config: PHProcessConfig | None = None,
        emulator_config: PHEmulatorProcessConfig | None = None,
    ) -> None:
        self.process_config = process_config or PHProcessConfig()
        self.emulator_config = emulator_config or PHEmulatorProcessConfig()
        self.equilibrium_model = EquilibriumChargeBalanceModel.from_config(
            self.process_config
        )
        self.rng = np.random.default_rng(self.emulator_config.random_seed)
        self.ph_sensor = float(self.emulator_config.initial_ph)

    def static_prediction(
        self,
        acid_flow: float,
        acetate_flow: float,
        water_flow: float,
    ) -> dict[str, float]:
        acid_flow = float(acid_flow)
        acetate_flow = float(acetate_flow)
        water_flow = float(water_flow)
        if acid_flow <= 0.0 or acetate_flow <= 0.0 or water_flow < 0.0:
            return {
                "ph_equilibrium_charge_balance": np.nan,
                "ph_equilibrium_affine": np.nan,
                "total_flow": acid_flow + acetate_flow + water_flow,
            }

        ph_eq = self.equilibrium_model.predict_ph(
            acid_flow,
            acetate_flow,
            water_flow,
        )
        ph_static = (
            self.emulator_config.static_intercept
            + self.emulator_config.static_slope * ph_eq
        )
        return {
            "ph_equilibrium_charge_balance": float(ph_eq),
            "ph_equilibrium_affine": float(ph_static),
            "total_flow": float(acid_flow + acetate_flow + water_flow),
        }

    def step(
        self,
        acid_flow: float,
        acetate_flow: float,
        water_flow: float,
        dt_s: float,
    ) -> dict[str, float]:
        prediction = self.static_prediction(acid_flow, acetate_flow, water_flow)
        ph_static = prediction["ph_equilibrium_affine"]
        if np.isfinite(ph_static):
            tau = max(float(self.emulator_config.response_tau_s), 1e-6)
            alpha = 1.0 - np.exp(-max(float(dt_s), 0.0) / tau)
            self.ph_sensor += alpha * (ph_static - self.ph_sensor)

        noise = self.rng.normal(0.0, self.emulator_config.sensor_noise_std)
        prediction["ph_sensor"] = float(self.ph_sensor + noise)
        return prediction
