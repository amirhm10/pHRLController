from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from simulation.config import PHProcessConfig


@dataclass(frozen=True)
class HendersonHasselbalchModel:
    """Generic Henderson-Hasselbalch model for weak-acid buffer mixing."""

    pKa: float
    acid_stock_mol_l: float
    base_stock_mol_l: float
    acid_name: str = "acid"
    base_name: str = "base"
    water_name: str = "water"

    display_name: ClassVar[str] = "Henderson-Hasselbalch"
    model_name: ClassVar[str] = "henderson_hasselbalch"

    @classmethod
    def from_config(
        cls,
        config: PHProcessConfig | None = None,
        acid_name: str = "acetic acid",
        base_name: str = "sodium acetate",
        water_name: str = "Arium water",
    ) -> "HendersonHasselbalchModel":
        config = config or PHProcessConfig()
        return cls(
            pKa=config.pKa,
            acid_stock_mol_l=config.acid_stock_mol_l,
            base_stock_mol_l=config.acetate_stock_mol_l,
            acid_name=acid_name,
            base_name=base_name,
            water_name=water_name,
        )

    def __post_init__(self) -> None:
        if self.acid_stock_mol_l <= 0.0 or self.base_stock_mol_l <= 0.0:
            raise ValueError("Stock concentrations must be positive.")

    def predict_ph(
        self,
        acid_flow: float,
        base_flow: float,
        water_flow: float | None = None,
    ) -> float:
        """Predict ideal buffer pH from acid/base molar inlet ratio."""
        ratio = self.molar_base_acid_ratio(acid_flow, base_flow, water_flow)
        return float(self.pKa + np.log10(ratio))

    def predict_array(
        self,
        acid_flow,
        base_flow,
        water_flow=None,
    ) -> np.ndarray:
        acid = np.asarray(acid_flow, dtype=float)
        base = np.asarray(base_flow, dtype=float)
        acid, base = np.broadcast_arrays(acid, base)

        valid = np.isfinite(acid) & np.isfinite(base) & (acid > 0.0) & (base > 0.0)
        if water_flow is not None:
            water = np.asarray(water_flow, dtype=float)
            water = np.broadcast_to(water, acid.shape)
            valid = valid & np.isfinite(water) & (water >= 0.0)

        prediction = np.full(acid.shape, np.nan, dtype=float)
        ratio = (self.base_stock_mol_l * base[valid]) / (
            self.acid_stock_mol_l * acid[valid]
        )
        prediction[valid] = self.pKa + np.log10(ratio)
        return prediction

    def molar_base_acid_ratio(
        self,
        acid_flow: float,
        base_flow: float,
        water_flow: float | None = None,
    ) -> float:
        acid_flow = float(acid_flow)
        base_flow = float(base_flow)
        if acid_flow <= 0.0 or base_flow <= 0.0:
            raise ValueError("acid_flow and base_flow must be positive.")
        if water_flow is not None and float(water_flow) < 0.0:
            raise ValueError("water_flow must be nonnegative when provided.")
        return float(
            (self.base_stock_mol_l * base_flow)
            / (self.acid_stock_mol_l * acid_flow)
        )

    def mixed_concentrations(
        self,
        acid_flow: float,
        base_flow: float,
        water_flow: float,
    ) -> dict[str, float]:
        """Return inlet mixed analytical concentrations for diagnostics."""
        acid_flow = float(acid_flow)
        base_flow = float(base_flow)
        water_flow = float(water_flow)
        if acid_flow <= 0.0 or base_flow <= 0.0 or water_flow < 0.0:
            raise ValueError("Flowrates must be physically valid.")

        total_flow = acid_flow + base_flow + water_flow
        acid_analytical = self.acid_stock_mol_l * acid_flow / total_flow
        base_analytical = self.base_stock_mol_l * base_flow / total_flow
        return {
            "total_flow": float(total_flow),
            "acid_analytical_mol_l": float(acid_analytical),
            "base_analytical_mol_l": float(base_analytical),
            "molar_base_acid_ratio": float(base_analytical / acid_analytical),
        }

    def metadata(self) -> dict[str, float | str]:
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "pKa": float(self.pKa),
            "acid_stock_mol_l": float(self.acid_stock_mol_l),
            "base_stock_mol_l": float(self.base_stock_mol_l),
            "acid_name": self.acid_name,
            "base_name": self.base_name,
            "water_name": self.water_name,
        }
