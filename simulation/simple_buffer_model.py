import numpy as np

from simulation.config import PHProcessConfig


class SimpleBufferModel:
    """Henderson-Hasselbalch steady-state model for acetate buffer mixing."""

    def __init__(self, config: PHProcessConfig | None = None):
        self.config = config or PHProcessConfig()

    def predict_ph(self, acid_flow: float, acetate_flow: float, water_flow: float | None = None) -> float:
        acid_flow = float(acid_flow)
        acetate_flow = float(acetate_flow)
        self._check_acid_acetate_flows(acid_flow, acetate_flow)
        return float(self.config.pKa + np.log10(acetate_flow / acid_flow))

    def ratio_from_target(self, target_ph: float, clip: bool = True) -> float:
        if clip:
            target_ph = self.config.clip_target_ph(target_ph)
        return float(10 ** (float(target_ph) - self.config.pKa))

    def flows_from_target(
        self,
        target_ph: float,
        water_flow: float | None = None,
        buffer_flow_sum: float | None = None,
        clip: bool = True,
    ) -> dict:
        """Calculate feasible flowrates from a target pH.

        The preferred rule keeps acid_flow + acetate_flow = buffer_flow_sum.
        If that violates pump bounds, the function rescales around the target
        ratio and returns the nearest feasible pair that preserves the ratio.
        """
        if water_flow is None:
            water_flow = self.config.default_water_flow
        if buffer_flow_sum is None:
            buffer_flow_sum = self.config.default_buffer_flow_sum

        target_ph_used = self.config.clip_target_ph(target_ph) if clip else float(target_ph)
        ratio = self.ratio_from_target(target_ph_used, clip=False)

        acid_flow = buffer_flow_sum / (1.0 + ratio)
        acetate_flow = buffer_flow_sum * ratio / (1.0 + ratio)

        acid_flow, acetate_flow = self._make_ratio_feasible(ratio, acid_flow, acetate_flow)
        water_flow = self._clip(water_flow, self.config.water_flow_min, self.config.water_flow_max)
        predicted_ph = self.predict_ph(acid_flow, acetate_flow, water_flow)

        return {
            "target_ph_requested": float(target_ph),
            "target_ph_used": float(target_ph_used),
            "acid_flow": float(acid_flow),
            "acetate_flow": float(acetate_flow),
            "water_flow": float(water_flow),
            "ratio": float(acetate_flow / acid_flow),
            "predicted_ph": float(predicted_ph),
            "model": "simple_henderson_hasselbalch",
        }

    def sweep_targets(self, target_ph_values, water_flow: float | None = None) -> list[dict]:
        return [self.flows_from_target(pH, water_flow=water_flow) for pH in target_ph_values]

    def _make_ratio_feasible(self, ratio: float, acid_flow: float, acetate_flow: float) -> tuple[float, float]:
        acid_min = self.config.acid_flow_min
        acid_max = self.config.acid_flow_max
        acetate_min = self.config.acetate_flow_min
        acetate_max = self.config.acetate_flow_max

        lower_acid = max(acid_min, acetate_min / ratio)
        upper_acid = min(acid_max, acetate_max / ratio)
        if lower_acid > upper_acid:
            raise ValueError(
                "Target ratio is infeasible with current acid/acetate pump bounds. "
                f"ratio={ratio:.4g}"
            )

        acid_flow = self._clip(acid_flow, lower_acid, upper_acid)
        acetate_flow = ratio * acid_flow
        return acid_flow, acetate_flow

    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, float(value)))

    @staticmethod
    def _check_acid_acetate_flows(acid_flow: float, acetate_flow: float) -> None:
        if acid_flow <= 0 or acetate_flow <= 0:
            raise ValueError("acid_flow and acetate_flow must be positive.")
