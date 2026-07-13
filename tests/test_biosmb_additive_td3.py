"""Hardware-free tests for the additive BioSMB custom TD3 package."""

from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
ONLINE_DIR = ROOT / "Biosmb-run-online" / "Biosmb-run-online"
TEST_OUTPUT = ROOT / "results" / "_test_biosmb_additive_td3"
LATEST_MANIFEST = (
    ROOT
    / "results"
    / "offline_ph_td3_training_20260710_183129"
    / "deployment_bundle"
    / "td3_actor_manifest.json"
)

for path in [ROOT, ONLINE_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from custom_td3 import (  # noqa: E402
    BioSMBTD3Policy,
    TD3Policy,
    TD3PolicyLoadError,
)
from helpers.td3_deployment_export import export_td3_actor_bundle  # noqa: E402
from simulation.ph_environment import PHEnvironment, PHEnvironmentConfig  # noqa: E402
from TD3Agent.actor import Actor as TrainingActor  # noqa: E402


ACTOR_CONFIG = {
    "state_dim": 5,
    "action_dim": 2,
    "hidden_dims": [128, 128],
    "activation": "relu",
    "use_layernorm": False,
    "dropout": 0.0,
    "max_action": 1.0,
    "squash": "tanh",
}

ACTION_MAPPING = {
    "mapping_version": "ratio_buffer_sum_v1",
    "acid_flow_min": 1.0,
    "acid_flow_max": 10.0,
    "acetate_flow_min": 1.0,
    "acetate_flow_max": 10.0,
    "water_flow_min": 1.0,
    "water_flow_max": 10.0,
    "buffer_flow_sum_min": 2.0,
    "buffer_flow_sum_max": 20.0,
    "fixed_water_flow": 5.0,
}


def load_main_check_action():
    """Load only main.check_action without importing hardware libraries."""

    main_path = ONLINE_DIR / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "check_action"
    )
    namespace = {
        "np": np,
        "Dict": Dict,
        "List": List,
        "Tuple": Tuple,
        "controlled_flow_indices": [0, 1, 2],
        "min_flow_rate": 1.0,
        "max_flow_rate": 10.0,
        "max_total_flow_rate": 25.0,
        "min_buffer_flow_sum": 2.0,
        "max_buffer_flow_sum": 20.0,
        "fixed_water_flow_rate": 5.0,
        "water_flow_tolerance": 1.0e-3,
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(main_path), "exec"), namespace)
    return namespace["check_action"]


def create_test_bundle(directory: Path) -> tuple[TrainingActor, Path]:
    """Export a deterministic synthetic actor through the production exporter."""

    directory.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(29)
    actor = TrainingActor(
        state_dim=5,
        action_dim=2,
        hidden_dims=[128, 128],
        activation="relu",
        use_layernorm=False,
        dropout=0.0,
        max_action=1.0,
        squash="tanh",
    )
    paths = export_td3_actor_bundle(
        actor,
        directory,
        actor_config=ACTOR_CONFIG,
        action_mapping=ACTION_MAPPING,
        current_ph_bounds=(3.76, 5.76),
        target_ph_bounds=(3.76, 5.7),
        nominal_ph=4.76,
        source_metadata={
            "simulation_only": True,
            "lab_validated": False,
            "dynamic_model_validated": False,
            "frozen_policy_validated": False,
        },
    )
    return actor, paths["manifest_path"]


class AdditivePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training_actor, manifest_path = create_test_bundle(
            TEST_OUTPUT / "valid_bundle"
        )
        cls.policy = TD3Policy.load(manifest_path)
        cls.facade = BioSMBTD3Policy(
            cls.policy,
            controlled_flow_indices=[0, 1, 2],
            controlled_stream_names={
                0: "acetic-acid",
                1: "sodium-acetate",
                2: "di-water",
            },
        )

    def test_exported_actor_prediction_matches_training_actor(self) -> None:
        state = np.asarray([4.6, 4.7, -0.1, 0.0, -0.111111], dtype=np.float32)
        self.training_actor.eval()
        with torch.inference_mode():
            expected = self.training_actor(
                torch.as_tensor(state).reshape(1, -1)
            ).numpy().reshape(-1)
        actual, recurrent_state = self.policy.predict(state, deterministic=True)
        np.testing.assert_allclose(actual, expected, atol=1.0e-7, rtol=0.0)
        self.assertIsNone(recurrent_state)

    def test_facade_builds_exact_td3_state_from_original_observation(self) -> None:
        observation = {
            "biosmb-sensors": {"PH_2": 4.6},
            "biosmb-flows": [5.0, 5.0, 5.0, 0.0, 0.0, 0.0, 0.0],
        }
        state = self.facade.build_state(observation, target_ph=4.7)
        np.testing.assert_allclose(
            state,
            [4.6, 4.7, -0.1, 0.0, -0.1111111111],
            atol=1.0e-6,
            rtol=0.0,
        )

    def test_action_mapping_matches_training_environment(self) -> None:
        environment = PHEnvironment(
            PHEnvironmentConfig(
                action_mode="ratio_buffer_sum",
                buffer_flow_sum_min=2.0,
                buffer_flow_sum_max=20.0,
            )
        )
        for ratio_action in np.linspace(-1.0, 1.0, 7):
            for sum_action in np.linspace(-1.0, 1.0, 7):
                action = np.asarray(
                    [ratio_action, sum_action],
                    dtype=np.float32,
                )
                expected = environment.action_to_flows(action)
                actual = self.policy.mapper.action_to_flows(action)
                np.testing.assert_allclose(
                    actual.as_list(),
                    expected,
                    atol=1.0e-6,
                    rtol=0.0,
                )

    def test_formatted_action_uses_original_dictionary_schema(self) -> None:
        facade = BioSMBTD3Policy(
            self.policy,
            controlled_flow_indices=[1, 2, 3],
            controlled_stream_names={
                1: "acetic-acid",
                2: "sodium-acetate",
                3: "di-water",
            },
        )
        action = facade.format_action([0.0, 0.0])
        self.assertEqual(
            set(action),
            {
                "raw_action",
                "controlled_flow_rates",
                "flow_rates",
                "total_controlled_flow_rate",
                "stream_flow_rates",
            },
        )
        self.assertEqual(len(action["flow_rates"]), 7)
        self.assertEqual(action["flow_rates"][0], 0.0)
        self.assertEqual(action["flow_rates"][3], 5.0)
        self.assertAlmostEqual(sum(action["controlled_flow_rates"][:2]), 11.0)

    def test_default_action_is_manifest_compatible(self) -> None:
        action = self.facade.default_action()
        np.testing.assert_allclose(
            action["controlled_flow_rates"],
            [7.5, 7.5, 5.0],
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            action["raw_action"],
            [0.0, 0.4444444444],
            atol=1.0e-6,
        )

    def test_measured_flows_round_trip_to_normalized_action(self) -> None:
        normalized_action = np.asarray([0.25, -0.4], dtype=np.float32)
        command = self.facade.format_action(normalized_action)
        observation = {
            "biosmb-sensors": {"PH_2": 4.65},
            "biosmb-flows": command["flow_rates"],
        }
        measured = self.facade.action_from_observation(observation)
        np.testing.assert_allclose(
            measured["raw_action"],
            normalized_action,
            atol=1.0e-6,
            rtol=0.0,
        )
        next_state = self.facade.build_state(observation, target_ph=4.7)
        np.testing.assert_allclose(
            next_state,
            [4.65, 4.7, -0.05, 0.25, -0.4],
            atol=1.0e-6,
            rtol=0.0,
        )

    def test_main_action_check_enforces_td3_flow_rules(self) -> None:
        check_action = load_main_check_action()
        valid_action = self.facade.format_action([0.0, 0.0])
        self.assertEqual(check_action(valid_action), (True, "valid"))

        wrong_water = copy.deepcopy(valid_action)
        wrong_water["controlled_flow_rates"][2] = 4.9
        wrong_water["flow_rates"][2] = 4.9
        wrong_water["total_controlled_flow_rate"] -= 0.1
        self.assertEqual(
            check_action(wrong_water),
            (False, "water_flow_does_not_match_td3_fixed_value"),
        )

        wrong_shape = copy.deepcopy(valid_action)
        wrong_shape["raw_action"] = [0.0, 0.0, 0.0]
        self.assertEqual(
            check_action(wrong_shape),
            (False, "td3_action_must_have_2_values"),
        )

    def test_hash_mismatch_is_rejected(self) -> None:
        _, manifest_path = create_test_bundle(TEST_OUTPUT / "bad_hash")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["weights_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(TD3PolicyLoadError):
            TD3Policy.load(manifest_path)


class OriginalReferenceTests(unittest.TestCase):
    def test_original_main_and_docker_entrypoint_are_restored(self) -> None:
        main_text = (ONLINE_DIR / "main.py").read_text(encoding="utf-8")
        docker_text = (ONLINE_DIR / "dockerfile").read_text(encoding="utf-8")
        self.assertIn("BioSMBOnlineTD3Trainer", main_text)
        self.assertIn("BioSMBTD3Policy", main_text)
        self.assertNotIn("from stable_baselines3 import SAC", main_text)
        self.assertNotIn("SAC.load", main_text)
        self.assertNotIn("sac_biosmb_mixing_online", main_text)
        self.assertIn('control_mode = "active_control"', main_text)
        self.assertIn("online_training_enabled = True", main_text)
        self.assertNotIn("def build_state(", main_text)
        self.assertNotIn("def get_default_action(", main_text)
        self.assertNotIn("def action_to_flow_rates(", main_text)
        self.assertIn("model.build_state(", main_text)
        self.assertIn("model.format_action(raw_action)", main_text)
        self.assertIn("model.action_from_observation(observation_after)", main_text)
        self.assertIn("next_state = model.build_state(", main_text)
        self.assertIn('CMD ["python", "./main.py"]', docker_text)
        self.assertIn("COPY . .", docker_text)

    def test_custom_package_is_self_contained(self) -> None:
        package_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ONLINE_DIR / "custom_td3").glob("*.py")
        )
        self.assertNotIn("from TD3Agent", package_text)
        self.assertNotIn("from utils", package_text)
        self.assertNotIn("stable_baselines3", package_text)


@unittest.skipUnless(LATEST_MANIFEST.is_file(), "latest saved actor is unavailable")
class LatestSavedActorTests(unittest.TestCase):
    def test_latest_500k_actor_loads_without_training_checkpoint(self) -> None:
        policy = TD3Policy.load(LATEST_MANIFEST)
        self.assertEqual(policy.source_metadata["total_steps"], 500_000)
        self.assertTrue(policy.source_metadata["simulation_only"])
        self.assertFalse(policy.source_metadata["lab_validated"])
        self.assertEqual(
            policy.manifest["weights_sha256"],
            "0c10ce7b8602bd5c455f74009e233ecc990735a3f73c76b2c99a196d23f91777",
        )


if __name__ == "__main__":
    unittest.main()
