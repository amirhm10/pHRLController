import numpy as np
from scipy.optimize import brentq

from simulation.config import PHProcessConfig
from simulation.simple_buffer_model import SimpleBufferModel


class EquilibriumBufferModel:
    """Steady-state acetate buffer model using charge balance."""

    def __init__(self, config: PHProcessConfig | None = None):
        self.config = config or PHProcessConfig()
        self.simple_model = SimpleBufferModel(self.config)

    def mixed_concentrations(self, acid_flow: float, acetate_flow: float, water_flow: float) -> dict:
        acid_flow = float(acid_flow)
        acetate_flow = float(acetate_flow)
        water_flow = float(water_flow)
        if acid_flow <= 0 or acetate_flow <= 0 or water_flow < 0:
            raise ValueError("Flowrates must be physically valid.")

        total_flow = acid_flow + acetate_flow + water_flow
        acid_analytical = self.config.acid_stock_mol_l * acid_flow / total_flow
        acetate_analytical = self.config.acetate_stock_mol_l * acetate_flow / total_flow
        total_buffer = acid_analytical + acetate_analytical
        sodium = acetate_analytical

        return {
            "total_flow": float(total_flow),
            "acid_analytical": float(acid_analytical),
            "acetate_analytical": float(acetate_analytical),
            "total_buffer": float(total_buffer),
            "sodium": float(sodium),
        }

    def predict_ph(self, acid_flow: float, acetate_flow: float, water_flow: float) -> float:
        concentrations = self.mixed_concentrations(acid_flow, acetate_flow, water_flow)
        C_T = concentrations["total_buffer"]
        C_Na = concentrations["sodium"]
        Ka = 10 ** (-self.config.pKa)
        Kw = self.config.Kw

        def charge_balance_in_pH(pH):
            H = 10 ** (-pH)
            acetate = C_T * Ka / (Ka + H)
            hydroxide = Kw / H
            return H + C_Na - acetate - hydroxide

        return float(brentq(charge_balance_in_pH, 0.0, 14.0))

    def compare_to_simple(self, acid_flow: float, acetate_flow: float, water_flow: float) -> dict:
        ph_simple = self.simple_model.predict_ph(acid_flow, acetate_flow, water_flow)
        ph_equilibrium = self.predict_ph(acid_flow, acetate_flow, water_flow)
        concentrations = self.mixed_concentrations(acid_flow, acetate_flow, water_flow)

        return {
            "acid_flow": float(acid_flow),
            "acetate_flow": float(acetate_flow),
            "water_flow": float(water_flow),
            "ratio": float(acetate_flow / acid_flow),
            "ph_simple": float(ph_simple),
            "ph_equilibrium": float(ph_equilibrium),
            "ph_difference": float(ph_equilibrium - ph_simple),
            **concentrations,
        }

    def flows_from_target(
        self,
        target_ph: float,
        water_flow: float | None = None,
        buffer_flow_sum: float | None = None,
        clip: bool = True,
    ) -> dict:
        """Use simple model to choose flows, then evaluate the equilibrium model."""
        flows = self.simple_model.flows_from_target(
            target_ph,
            water_flow=water_flow,
            buffer_flow_sum=buffer_flow_sum,
            clip=clip,
        )
        ph_equilibrium = self.predict_ph(
            flows["acid_flow"],
            flows["acetate_flow"],
            flows["water_flow"],
        )
        flows["ph_simple"] = flows.pop("predicted_ph")
        flows["ph_equilibrium"] = float(ph_equilibrium)
        flows["ph_difference"] = float(ph_equilibrium - flows["ph_simple"])
        flows["model"] = "equilibrium_charge_balance"
        return flows

    def sweep_targets(self, target_ph_values, water_flow: float | None = None) -> list[dict]:
        return [self.flows_from_target(pH, water_flow=water_flow) for pH in target_ph_values]
