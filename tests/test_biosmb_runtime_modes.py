"""Hardware-free tests for BioSMB setpoint and frozen-action modes."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ONLINE_DIR = ROOT / "Biosmb-run-online" / "Biosmb-run-online"
MAIN_PATH = ONLINE_DIR / "main.py"
if str(ONLINE_DIR) not in sys.path:
    sys.path.insert(0, str(ONLINE_DIR))

from custom_td3 import (  # noqa: E402
    RuntimeModeError,
    ScheduledSetpointManager,
    select_frozen_action,
    validate_target_ph,
)


def load_prepare_runtime_modes(**overrides):
    """Load only main.prepare_runtime_modes without hardware dependencies."""

    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "prepare_runtime_modes"
    )
    namespace = {
        "np": np,
        "RuntimeModeError": RuntimeModeError,
        "ScheduledSetpointManager": ScheduledSetpointManager,
        "validate_target_ph": validate_target_ph,
        "control_mode": "active_control",
        "target_ph_mode": "fixed",
        "frozen_action_mode": "deterministic",
        "online_training_enabled": False,
        "frozen_action_noise_std": 0.01,
        "frozen_action_noise_seed": 7,
        "deployment_target_ph": 4.7,
        "scheduled_target_ph_min": 3.76,
        "scheduled_target_ph_max": 5.70,
        "scheduled_setpoint_count": 5,
        "scheduled_max_steps_per_setpoint": 50,
        "scheduled_consecutive_steps_required": 10,
        "target_ph_tolerance": 0.1,
    }
    namespace.update(overrides)
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace["prepare_runtime_modes"]


class RuntimeModeTests(unittest.TestCase):
    def test_main_defaults_to_fixed_target_and_frozen_deterministic_actor(self) -> None:
        main_text = MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn('target_ph_mode = "fixed"', main_text)
        self.assertIn("online_training_enabled = False", main_text)
        self.assertIn('frozen_action_mode = "deterministic"', main_text)

    def test_main_reward_and_next_state_use_the_correct_targets(self) -> None:
        main_text = MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("target_ph=next_target_ph", main_text)
        self.assertIn("reward_target_ph=target_ph", main_text)
        self.assertIn("target_ph = next_target_ph", main_text)
        self.assertLess(
            main_text.index("target_ph=next_target_ph"),
            main_text.index("reward_target_ph=target_ph"),
        )

    def test_main_runtime_preparation_uses_manifest_target_bounds(self) -> None:
        class StubModel:
            manifest = {
                "state_bounds": [
                    [3.76, 5.76],
                    [3.76, 5.70],
                    [-1.94, 2.0],
                    [-1.0, 1.0],
                    [-1.0, 1.0],
                ]
            }

        prepare = load_prepare_runtime_modes(target_ph_mode="scheduled")
        scheduler, rng, bounds = prepare(StubModel())
        self.assertIsInstance(scheduler, ScheduledSetpointManager)
        self.assertIsNone(rng)
        self.assertEqual(bounds, (3.76, 5.70))

    def test_main_rejects_suggest_only_online_training(self) -> None:
        class StubModel:
            manifest = {
                "state_bounds": [
                    [3.76, 5.76],
                    [3.76, 5.70],
                    [-1.94, 2.0],
                    [-1.0, 1.0],
                    [-1.0, 1.0],
                ]
            }

        prepare = load_prepare_runtime_modes(
            control_mode="suggest_only",
            online_training_enabled=True,
        )
        with self.assertRaises(RuntimeModeError):
            prepare(StubModel())

    def test_restored_requirements_are_the_extended_working_set(self) -> None:
        requirements = (
            ONLINE_DIR / "requirements.txt"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(requirements), 46)
        self.assertIn("gymnasium==1.2.3", requirements)
        self.assertIn("stable_baselines3==2.8.0", requirements)
        self.assertIn("torch ==2.11.0", requirements)

    def test_schedule_uses_requested_range_count_and_ping_pong_order(self) -> None:
        scheduler = ScheduledSetpointManager(
            target_ph_min=3.76,
            target_ph_max=5.70,
            setpoint_count=5,
            max_steps_per_setpoint=50,
            consecutive_steps_required=10,
            tolerance=0.1,
        )

        np.testing.assert_allclose(
            scheduler.target_values,
            np.linspace(3.76, 5.70, 5),
        )
        self.assertEqual(
            scheduler.cycle_indices.tolist(),
            [0, 1, 2, 3, 4, 3, 2, 1],
        )
        self.assertEqual(scheduler.current_target_ph, 3.76)

    def test_schedule_changes_after_maximum_completed_steps(self) -> None:
        scheduler = ScheduledSetpointManager(
            target_ph_min=4.0,
            target_ph_max=5.0,
            setpoint_count=3,
            max_steps_per_setpoint=3,
            consecutive_steps_required=10,
            tolerance=0.05,
        )

        self.assertFalse(scheduler.observe(4.5)["target_changed"])
        self.assertFalse(scheduler.observe(4.5)["target_changed"])
        update = scheduler.observe(4.5)

        self.assertTrue(update["target_changed"])
        self.assertEqual(update["change_reason"], "maximum_steps")
        self.assertEqual(update["steps_at_target"], 3)
        self.assertEqual(update["target_ph"], 4.0)
        self.assertEqual(update["next_target_ph"], 4.5)

    def test_schedule_requires_consecutive_in_tolerance_steps(self) -> None:
        scheduler = ScheduledSetpointManager(
            target_ph_min=4.0,
            target_ph_max=5.0,
            setpoint_count=3,
            max_steps_per_setpoint=50,
            consecutive_steps_required=3,
            tolerance=0.05,
        )

        scheduler.observe(4.01)
        scheduler.observe(4.02)
        reset_update = scheduler.observe(4.2)
        self.assertEqual(reset_update["consecutive_steps_in_tolerance"], 0)
        self.assertFalse(reset_update["target_changed"])

        scheduler.observe(4.01)
        scheduler.observe(3.99)
        update = scheduler.observe(4.0)
        self.assertTrue(update["target_changed"])
        self.assertEqual(update["change_reason"], "consecutive_in_tolerance")
        self.assertEqual(update["consecutive_steps_in_tolerance"], 3)

    def test_schedule_reports_when_both_change_conditions_are_met(self) -> None:
        scheduler = ScheduledSetpointManager(
            target_ph_min=4.0,
            target_ph_max=5.0,
            setpoint_count=2,
            max_steps_per_setpoint=2,
            consecutive_steps_required=2,
            tolerance=0.05,
        )

        scheduler.observe(4.0)
        update = scheduler.observe(4.0)
        self.assertEqual(
            update["change_reason"],
            "maximum_steps_and_consecutive_in_tolerance",
        )

    def test_target_validation_uses_deployed_bounds(self) -> None:
        self.assertEqual(validate_target_ph(4.7, 3.76, 5.70), 4.7)
        with self.assertRaises(RuntimeModeError):
            validate_target_ph(5.71, 3.76, 5.70)

    def test_frozen_action_modes_are_explicit_and_bounded(self) -> None:
        class StubModel:
            @staticmethod
            def predict(state, deterministic=True):
                del state
                if not deterministic:
                    raise AssertionError("Frozen actor must remain deterministic.")
                return np.asarray([0.99, -0.99], dtype=np.float32), None

        state = np.zeros(5, dtype=np.float32)
        deterministic_action, deterministic_info = select_frozen_action(
            StubModel(),
            state,
            action_mode="deterministic",
            gaussian_noise_std=0.01,
            rng=None,
        )
        np.testing.assert_array_equal(
            deterministic_action,
            np.asarray([0.99, -0.99], dtype=np.float32),
        )
        self.assertEqual(
            deterministic_info["action_source"],
            "frozen_td3_deterministic",
        )

        first_action, first_info = select_frozen_action(
            StubModel(),
            state,
            action_mode="gaussian_noise",
            gaussian_noise_std=0.05,
            rng=np.random.default_rng(17),
        )
        second_action, _ = select_frozen_action(
            StubModel(),
            state,
            action_mode="gaussian_noise",
            gaussian_noise_std=0.05,
            rng=np.random.default_rng(17),
        )
        np.testing.assert_array_equal(first_action, second_action)
        self.assertTrue(np.all(first_action >= -1.0))
        self.assertTrue(np.all(first_action <= 1.0))
        self.assertEqual(
            first_info["action_source"],
            "frozen_td3_gaussian_noise",
        )


if __name__ == "__main__":
    unittest.main()
