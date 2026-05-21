from dataclasses import dataclass


@dataclass
class PHProcessConfig:
    """Default configuration for the acetate buffer pH process."""

    pKa: float = 4.76
    Kw: float = 1e-14

    acid_stock_mol_l: float = 0.1
    acetate_stock_mol_l: float = 0.1

    acid_flow_min: float = 1.0
    acid_flow_max: float = 10.0
    acetate_flow_min: float = 1.0
    acetate_flow_max: float = 10.0
    water_flow_min: float = 1.0
    water_flow_max: float = 10.0

    default_water_flow: float = 5.0
    default_buffer_flow_sum: float = 10.0

    target_ph_min: float = 3.76
    target_ph_max: float = 5.76

    def clip_target_ph(self, target_ph: float) -> float:
        return max(self.target_ph_min, min(self.target_ph_max, float(target_ph)))
