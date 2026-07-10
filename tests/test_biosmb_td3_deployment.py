"""Contract and parity tests for the BioSMB custom-TD3 deployment path."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
ONLINE_DIR = ROOT / "Biosmb-run-online" / "Biosmb-run-online"
TEST_OUTPUT_DIR = ROOT / "results" / "_test_biosmb_td3_deployment"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ONLINE_DIR) not in sys.path:
    sys.path.insert(0, str(ONLINE_DIR))

from TD3Agent.actor import Actor  # noqa: E402
from helpers.td3_deployment_export import export_td3_actor_bundle  # noqa: E402
import main as biosmb_main  # noqa: E402
from simulation.ph_environment import PHEnvironment, PHEnvironmentConfig  # noqa: E402
from td3_deployment import (  # noqa: E402
    ActionMappingError,
    FrozenTD3Policy,
    LogicalFlows,
    PolicyBundleError,
    RatioSumActionMapper,
    build_td3_state,
    logical_flows_to_pump_array,
    validate_flow_transition,
)


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


def create_test_bundle(directory: Path) -> tuple[Actor, Path]:
    """Export one deterministic synthetic actor using the production helper."""

    directory.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(17)
    actor = Actor(
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
        actor=actor,
        output_dir=directory,
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


class FrozenTD3PolicyTests(unittest.TestCase):
    def test_exported_actor_matches_training_actor(self) -> None:
        actor, manifest_path = create_test_bundle(TEST_OUTPUT_DIR / "parity")
        policy = FrozenTD3Policy.load(manifest_path)
        states = np.array(
            [
                [4.6, 4.7, -0.1, 0.0, -0.111111],
                [3.9, 4.3, -0.4, -0.2, 0.4],
                [5.4, 5.0, 0.4, 0.6, -0.3],
            ],
            dtype=np.float32,
        )
        actor.eval()
        with torch.inference_mode():
            expected = actor(torch.as_tensor(states)).cpu().numpy()
        actual = np.vstack([policy.predict(state) for state in states])
        np.testing.assert_allclose(actual, expected, atol=1.0e-7, rtol=0.0)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["state_bounds"][0], [3.76, 5.76])
        self.assertEqual(manifest["state_bounds"][1], [3.76, 5.7])
        np.testing.assert_allclose(
            manifest["state_bounds"][2],
            [-1.94, 2.0],
            atol=1.0e-12,
        )

    def test_hash_mismatch_is_rejected(self) -> None:
        _, manifest_path = create_test_bundle(TEST_OUTPUT_DIR / "bad_hash")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["weights_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(PolicyBundleError):
            FrozenTD3Policy.load(manifest_path)

    def test_same_dimension_wrong_state_order_is_rejected(self) -> None:
        _, manifest_path = create_test_bundle(TEST_OUTPUT_DIR / "wrong_state_order")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["state_variables"][2], manifest["state_variables"][3] = (
            manifest["state_variables"][3],
            manifest["state_variables"][2],
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(PolicyBundleError):
            FrozenTD3Policy.load(manifest_path)


class TD3ActionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        _, manifest_path = create_test_bundle(TEST_OUTPUT_DIR / "mapper")
        policy = FrozenTD3Policy.load(manifest_path)
        self.mapper = RatioSumActionMapper(policy.flow_mapping)

    def test_online_mapper_matches_training_environment(self) -> None:
        environment = PHEnvironment(
            PHEnvironmentConfig(
                action_mode="ratio_buffer_sum",
                buffer_flow_sum_min=2.0,
                buffer_flow_sum_max=20.0,
            )
        )
        action_values = np.linspace(-1.0, 1.0, 7)
        for ratio_action in action_values:
            for sum_action in action_values:
                action = np.array([ratio_action, sum_action], dtype=np.float32)
                training_flows = environment.action_to_flows(action)
                online_flows = self.mapper.action_to_flows(action)
                np.testing.assert_allclose(
                    [
                        online_flows.acid_flow,
                        online_flows.acetate_flow,
                        online_flows.water_flow,
                    ],
                    training_flows,
                    atol=1.0e-6,
                    rtol=0.0,
                )
                recovered_action = self.mapper.flows_to_action(online_flows)
                recovered_flows = self.mapper.action_to_flows(recovered_action)
                np.testing.assert_allclose(
                    [
                        recovered_flows.acid_flow,
                        recovered_flows.acetate_flow,
                        recovered_flows.water_flow,
                    ],
                    [
                        online_flows.acid_flow,
                        online_flows.acetate_flow,
                        online_flows.water_flow,
                    ],
                    atol=1.0e-6,
                    rtol=0.0,
                )
                # At minimum/maximum buffer sum, individual pump bounds force
                # a single ratio, so the ratio action is not identifiable.
                if abs(float(sum_action)) < 1.0 - 1.0e-9:
                    np.testing.assert_allclose(
                        recovered_action,
                        action,
                        atol=1.0e-6,
                        rtol=0.0,
                    )

    def test_state_uses_ph2_error_and_normalized_previous_flows(self) -> None:
        state = build_td3_state(
            measured_ph=4.6,
            target_ph=4.7,
            verified_flows=LogicalFlows(5.0, 5.0, 5.0),
            mapper=self.mapper,
        )
        np.testing.assert_allclose(
            state,
            [4.6, 4.7, -0.1, 0.0, -0.1111111111],
            atol=1.0e-6,
            rtol=0.0,
        )

    def test_water_is_always_fixed_by_td3_mapper(self) -> None:
        for action in [[-1, -1], [0, 0], [1, 1], [0.2, -0.4]]:
            self.assertEqual(self.mapper.action_to_flows(action).water_flow, 5.0)

    def test_action_must_have_two_finite_values(self) -> None:
        with self.assertRaises(ActionMappingError):
            self.mapper.action_to_flows([0.0, 0.0, 0.0])
        with self.assertRaises(ActionMappingError):
            self.mapper.action_to_flows([np.nan, 0.0])

    def test_logical_to_physical_map_preserves_uncontrolled_pumps(self) -> None:
        current = [0.2, 2.0, 3.0, 4.0, 0.6, 0.7, 0.8]
        proposed = LogicalFlows(5.0, 6.0, 5.0)
        mapped = logical_flows_to_pump_array(
            proposed,
            current,
            {"acid": 2, "acetate": 3, "water": 4},
        )
        self.assertEqual(mapped, [0.2, 5.0, 6.0, 5.0, 0.6, 0.7, 0.8])

    def test_large_physical_step_is_rejected(self) -> None:
        valid, reason = validate_flow_transition(
            proposed=LogicalFlows(8.0, 2.0, 5.0),
            previous=LogicalFlows(5.0, 5.0, 5.0),
            mapper=self.mapper,
            max_step_change=0.5,
            max_total_flow=25.0,
        )
        self.assertFalse(valid)
        self.assertIn("slew", reason.lower())


class DeploymentConfigurationTests(unittest.TestCase):
    def test_committed_default_is_suggest_only_and_unverified(self) -> None:
        config = json.loads(
            (ONLINE_DIR / "deployment_settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["control"]["mode"], "suggest_only")
        self.assertFalse(config["hardware"]["pump_mapping_verified"])
        self.assertFalse(config["hardware"]["mass_mapping_verified"])
        self.assertFalse(config["hardware"]["outlet_path_verified"])
        self.assertFalse(config["hardware"]["exclusive_pump_control_verified"])
        self.assertFalse(config["hardware"]["flow_readback_semantics_verified"])
        self.assertEqual(config["policy"]["approved_manifest_sha256"], "")

    def test_active_control_cannot_use_zero_step_override(self) -> None:
        config = biosmb_main.load_deployment_config(
            ONLINE_DIR / "deployment_settings.json"
        )
        config["timing"]["max_control_steps"] = 0
        with self.assertRaises(biosmb_main.ConfigurationError):
            biosmb_main.validate_session_limit(config, "active_control")


class FakeFlowManager:
    """Minimal manager that records full-array commands for hardware-free tests."""

    def __init__(self, flows: list[float], readback=None):
        self.flows = list(flows)
        self.readback = readback
        self.write_count = 0

    def set_all_flows(self, values) -> None:
        self.write_count += 1
        self.flows = list(values)

    def get_all_flows(self):
        return self.flows if self.readback is None else self.readback


class OnlineMainSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, manifest_path = create_test_bundle(TEST_OUTPUT_DIR / "online_main")
        cls.policy = FrozenTD3Policy.load(manifest_path)

    def test_one_batch_write_has_finite_seven_value_readback(self) -> None:
        manager = FakeFlowManager([0.2, 5.0, 5.0, 5.0, 0.6, 0.7, 0.8])
        receipt = biosmb_main.write_and_verify_flows(
            manager,
            LogicalFlows(5.2, 4.8, 5.0),
            manager.flows,
            {"acid": 2, "acetate": 3, "water": 4},
            readback_tolerance=0.05,
        )
        self.assertEqual(manager.write_count, 1)
        self.assertTrue(receipt["readback_valid"])
        self.assertEqual(
            receipt["readback_pump_flows"],
            [0.2, 5.2, 4.8, 5.0, 0.6, 0.7, 0.8],
        )

    def test_simulation_policy_cannot_be_armed_for_active_control(self) -> None:
        config = biosmb_main.load_deployment_config(
            ONLINE_DIR / "deployment_settings.json"
        )
        for flag in [
            "pump_mapping_verified",
            "mass_mapping_verified",
            "outlet_path_verified",
            "exclusive_pump_control_verified",
            "flow_readback_semantics_verified",
        ]:
            config["hardware"][flag] = True
        config["policy"]["approved_manifest_sha256"] = (
            self.policy.manifest_sha256
        )
        arm_name = config["control"]["arming_environment_variable"]
        arm_value = config["control"]["required_arming_value"]
        with patch.dict(biosmb_main.os.environ, {arm_name: arm_value}):
            with self.assertRaisesRegex(
                biosmb_main.ConfigurationError,
                "simulation_only",
            ):
                biosmb_main.validate_active_control_preconditions(
                    config,
                    self.policy,
                    "active_control",
                )

    def test_nan_or_short_command_readback_is_rejected(self) -> None:
        initial = [0.2, 5.0, 5.0, 5.0, 0.6, 0.7, 0.8]
        for malformed in [
            [0.2, 5.0, np.nan, 5.0, 0.6, 0.7, 0.8],
            [0.2, 5.0, 5.0],
        ]:
            manager = FakeFlowManager(initial, readback=malformed)
            receipt = biosmb_main.write_and_verify_flows(
                manager,
                LogicalFlows(5.0, 5.0, 5.0),
                initial,
                {"acid": 2, "acetate": 3, "water": 4},
                readback_tolerance=0.05,
            )
            self.assertEqual(manager.write_count, 1)
            self.assertFalse(receipt["readback_valid"])

    def test_suggest_only_step_has_no_hardware_write(self) -> None:
        config = biosmb_main.load_deployment_config(
            ONLINE_DIR / "deployment_settings.json"
        )
        config["timing"]["max_control_steps"] = 1
        config["timing"]["decision_interval_seconds"] = 10.0
        observation = {
            "biosmb-sensors": {"PH_2": 4.7},
            "biosmb-flows": [0.2, 5.0, 5.0, 5.0, 0.6, 0.7, 0.8],
            "mfcs-mass": {
                "acid-mass-grams": 1500.0,
                "acetate-mass-grams": 1500.0,
                "water-mass-grams": 1500.0,
            },
            "observation_valid": True,
            "observation_failure_reason": "valid",
        }
        manager = FakeFlowManager(observation["biosmb-flows"])
        events = []

        def capture_event(_collection, event, *, required):
            events.append(dict(event))

        with (
            patch.object(biosmb_main, "run_warmup", return_value=observation),
            patch.object(biosmb_main, "get_observation", return_value=observation),
            patch.object(
                biosmb_main,
                "monitor_until_deadline",
                return_value=observation,
            ),
            patch.object(
                biosmb_main,
                "read_target_ph",
                return_value=(4.7, "test"),
            ),
            patch.object(biosmb_main, "log_event", side_effect=capture_event),
        ):
            biosmb_main.run_deployment_loop(
                self.policy,
                manager,
                config,
                control_mode="suggest_only",
                redis_client=None,
                raw_collection=None,
                deployment_collection=object(),
                session_id="test-shadow-session",
            )

        self.assertEqual(manager.write_count, 0)
        event_types = [event["event_type"] for event in events]
        self.assertIn("command_intent", event_types)
        self.assertIn("command_receipt", event_types)
        receipts = [
            event for event in events if event["event_type"] == "command_receipt"
        ]
        self.assertTrue(all(not event["write_attempted"] for event in receipts))


class ContainerContractTests(unittest.TestCase):
    def test_container_remains_actor_only_shadow_first_and_nonroot(self) -> None:
        dockerfile = (ONLINE_DIR / "dockerfile").read_text(encoding="utf-8")
        compose = (ONLINE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
        requirements = (ONLINE_DIR / "requirements-runtime.txt").read_text(
            encoding="utf-8"
        )
        installed_requirements = "\n".join(
            line
            for line in requirements.lower().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        self.assertNotIn("COPY . .", dockerfile)
        self.assertIn("USER biosmb", dockerfile)
        self.assertIn("--control-mode", dockerfile)
        self.assertIn("suggest_only", dockerfile)
        self.assertIn('profiles: ["shadow"]', compose)
        self.assertIn('profiles: ["active"]', compose)
        self.assertGreaterEqual(compose.count(":/app/models:ro"), 2)
        self.assertGreaterEqual(compose.count('restart: "no"'), 2)
        self.assertNotIn("stable_baselines3", installed_requirements)
        self.assertNotIn("gymnasium", installed_requirements)


if __name__ == "__main__":
    unittest.main()
