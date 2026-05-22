from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from scipy.optimize import brentq

from simulation.config import PHProcessConfig


@dataclass(frozen=True)
class EquilibriumChargeBalanceModel:
    """Steady-state acetate buffer model from equilibrium charge balance."""

    pKa: float
    Kw: float
    acid_stock_mol_l: float
    acetate_stock_mol_l: float
    acid_name: str = "acetic acid"
    acetate_name: str = "sodium acetate"
    water_name: str = "Arium water"

    display_name: ClassVar[str] = "Equilibrium Charge Balance"
    model_name: ClassVar[str] = "equilibrium_charge_balance"

    @classmethod
    def from_config(
        cls,
        config: PHProcessConfig | None = None,
        acid_name: str = "acetic acid",
        acetate_name: str = "sodium acetate",
        water_name: str = "Arium water",
    ) -> "EquilibriumChargeBalanceModel":
        config = config or PHProcessConfig()
        return cls(
            pKa=config.pKa,
            Kw=config.Kw,
            acid_stock_mol_l=config.acid_stock_mol_l,
            acetate_stock_mol_l=config.acetate_stock_mol_l,
            acid_name=acid_name,
            acetate_name=acetate_name,
            water_name=water_name,
        )

    def __post_init__(self) -> None:
        if self.acid_stock_mol_l <= 0.0 or self.acetate_stock_mol_l <= 0.0:
            raise ValueError("Stock concentrations must be positive.")
        if self.Kw <= 0.0:
            raise ValueError("Kw must be positive.")

    @property
    def Ka(self) -> float:
        return float(10.0 ** (-self.pKa))

    def mixed_concentrations(
        self,
        acid_flow: float,
        acetate_flow: float,
        water_flow: float,
    ) -> dict[str, float]:
        acid_flow = float(acid_flow)
        acetate_flow = float(acetate_flow)
        water_flow = float(water_flow)
        if acid_flow <= 0.0 or acetate_flow <= 0.0 or water_flow < 0.0:
            raise ValueError("Flowrates must be physically valid.")

        total_flow = acid_flow + acetate_flow + water_flow
        acid_analytical = self.acid_stock_mol_l * acid_flow / total_flow
        acetate_analytical = self.acetate_stock_mol_l * acetate_flow / total_flow
        total_buffer = acid_analytical + acetate_analytical
        sodium = acetate_analytical

        return {
            "total_flow": float(total_flow),
            "acid_analytical_mol_l": float(acid_analytical),
            "acetate_analytical_mol_l": float(acetate_analytical),
            "total_buffer_mol_l": float(total_buffer),
            "sodium_mol_l": float(sodium),
        }

    def charge_balance_residual_h(
        self,
        hydrogen_mol_l: float,
        total_buffer_mol_l: float,
        sodium_mol_l: float,
    ) -> float:
        H = float(hydrogen_mol_l)
        C_T = float(total_buffer_mol_l)
        C_Na = float(sodium_mol_l)
        if H <= 0.0:
            raise ValueError("hydrogen_mol_l must be positive.")

        acetate = C_T * self.Ka / (self.Ka + H)
        hydroxide = self.Kw / H
        return float(H + C_Na - acetate - hydroxide)

    def predict_ph(
        self,
        acid_flow: float,
        acetate_flow: float,
        water_flow: float,
    ) -> float:
        concentrations = self.mixed_concentrations(
            acid_flow,
            acetate_flow,
            water_flow,
        )
        total_buffer = concentrations["total_buffer_mol_l"]
        sodium = concentrations["sodium_mol_l"]

        def residual(H: float) -> float:
            return self.charge_balance_residual_h(H, total_buffer, sodium)

        hydrogen = brentq(residual, 1e-14, 1.0)
        return float(-np.log10(hydrogen))

    def predict_array(self, acid_flow, acetate_flow, water_flow) -> np.ndarray:
        acid = np.asarray(acid_flow, dtype=float)
        acetate = np.asarray(acetate_flow, dtype=float)
        water = np.asarray(water_flow, dtype=float)
        acid, acetate, water = np.broadcast_arrays(acid, acetate, water)

        prediction = np.full(acid.shape, np.nan, dtype=float)
        valid = (
            np.isfinite(acid)
            & np.isfinite(acetate)
            & np.isfinite(water)
            & (acid > 0.0)
            & (acetate > 0.0)
            & (water >= 0.0)
        )

        flat_prediction = prediction.ravel()
        flat_acid = acid.ravel()
        flat_acetate = acetate.ravel()
        flat_water = water.ravel()
        flat_valid = valid.ravel()
        for index, is_valid in enumerate(flat_valid):
            if not is_valid:
                continue
            flat_prediction[index] = self.predict_ph(
                flat_acid[index],
                flat_acetate[index],
                flat_water[index],
            )
        return prediction

    def metadata(self) -> dict[str, float | str]:
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "pKa": float(self.pKa),
            "Ka": float(self.Ka),
            "Kw": float(self.Kw),
            "acid_stock_mol_l": float(self.acid_stock_mol_l),
            "acetate_stock_mol_l": float(self.acetate_stock_mol_l),
            "acid_name": self.acid_name,
            "acetate_name": self.acetate_name,
            "water_name": self.water_name,
        }
