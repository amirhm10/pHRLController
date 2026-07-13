"""Source and numerical parity checks for the BioSMB custom TD3 copy."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
ONLINE_DIR = ROOT / "Biosmb-run-online" / "Biosmb-run-online"
CUSTOM_DIR = ONLINE_DIR / "custom_td3"
MODELS_DIR = ONLINE_DIR / "models"
SOURCE_RUN = ROOT / "results" / "offline_ph_td3_training_20260710_183129"

for path in [ROOT, ONLINE_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from custom_td3 import (  # noqa: E402
    BioSMBOnlineTD3Trainer,
    BioSMBTD3Policy,
    GaussianNoiseSchedule,
    PHRewardConfig as CopiedRewardConfig,
    TD3Agent as CopiedTD3Agent,
    compute_ph_reward as compute_copied_reward,
)
from TD3Agent.agent import TD3Agent as RootTD3Agent  # noqa: E402
from simulation.ph_reward import (  # noqa: E402
    PHRewardConfig as RootRewardConfig,
    compute_ph_reward as compute_root_reward,
)


class SourceFidelityTests(unittest.TestCase):
    def test_inactive_training_modules_are_not_copied(self) -> None:
        for name in [
            "nstep.py",
            "nstep_targets.py",
            "sequence_sampling.py",
            "process_config.py",
        ]:
            self.assertFalse((CUSTOM_DIR / name).exists())

    def test_inactive_feature_names_are_absent_from_active_agent(self) -> None:
        source = (CUSTOM_DIR / "agent.py").read_text(encoding="utf-8")
        for name in [
            "multistep",
            "lambda_return",
            "param_noise",
            "bc_context",
            "hard_update_interval",
            "target_combine",
        ]:
            self.assertNotIn(name, source)


class NumericalFidelityTests(unittest.TestCase):
    def test_reward_matches_root_implementation(self) -> None:
        root_kwargs = {
            "mode": "relative_band_offset",
            "q_squared": 1.0,
            "q_absolute": 1.0,
            "move_weight": 0.0,
            "sum_move_weight": 5.0,
            "band_floor_ph": 0.01,
            "bonus_weight_abs": 0.05,
            "bonus_k": 6.0,
            "absolute_error_weight": 1.0,
            "tail_offset_weight": 0.0,
        }
        copied_kwargs = {
            "band_floor_ph": 0.01,
            "q_band": 1.0,
            "r_move": 0.0,
            "sum_move_weight": 5.0,
            "bonus_weight_abs": 0.05,
            "bonus_k": 6.0,
            "absolute_error_weight": 1.0,
            "tail_offset_weight": 0.0,
        }
        inputs = {
            "target_ph": 4.7,
            "ph": 4.63,
            "action": np.asarray([0.2, -0.1], dtype=np.float32),
            "previous_action": np.asarray([0.1, -0.2], dtype=np.float32),
            "hold_progress": 0.4,
            "buffer_sum": 10.1,
            "previous_buffer_sum": 9.8,
            "buffer_sum_min": 2.0,
            "buffer_sum_max": 20.0,
        }
        expected = compute_root_reward(
            config=RootRewardConfig(**root_kwargs),
            **inputs,
        ).to_info_dict()
        actual = compute_copied_reward(
            config=CopiedRewardConfig(**copied_kwargs),
            **inputs,
        ).to_info_dict()
        self.assertTrue(set(actual).issubset(expected))
        for name in actual:
            if isinstance(actual[name], str):
                self.assertEqual(actual[name], expected[name])
            else:
                self.assertAlmostEqual(actual[name], expected[name], places=14)
        self.assertEqual(expected["reward_economic_flow_cost"], 0.0)
        self.assertEqual(expected["reward_economic_flow_penalty_term"], 0.0)

    def test_active_one_step_update_matches_original_agent(self) -> None:
        common = {
            "state_dim": 5,
            "action_dim": 2,
            "actor_hidden": [128, 128],
            "critic_hidden": [128, 128],
            "gamma": 0.97,
            "actor_lr": 1.0e-4,
            "critic_lr": 1.0e-3,
            "batch_size": 64,
            "policy_delay": 2,
            "target_policy_smoothing_noise_std": 0.2,
            "noise_clip": 0.5,
            "max_action": 1.0,
            "tau": 0.005,
            "buffer_size": 60_000,
            "replay_frac_per": 0.5,
            "replay_frac_recent": 0.2,
            "replay_recent_window": 1_000,
            "replay_alpha": 0.6,
            "replay_beta_start": 0.4,
            "replay_beta_end": 1.0,
            "replay_beta_steps": 50_000,
            "device": torch.device("cpu"),
            "seed": 31,
        }
        root = RootTD3Agent(
            **common,
            grad_clip_norm=10.0,
            std_start=0.02,
            std_end=0.01,
            std_decay_steps=5_000,
            std_decay_mode="linear",
            exploration_mode="gaussian",
            multistep_mode="one_step",
            n_step=1,
            target_update="soft",
            target_combine="min",
            loss_type="huber",
            use_adamw=True,
            actor_freeze=0,
        )
        copied = CopiedTD3Agent(
            **common,
            grad_clip_norm=10.0,
            std_start=0.02,
            std_end=0.01,
            std_decay_steps=5_000,
        )

        generator = np.random.default_rng(93)
        for index in range(96):
            state = generator.normal(size=5).astype(np.float32)
            action = np.tanh(generator.normal(size=2)).astype(np.float32)
            reward = float(generator.normal())
            next_state = generator.normal(size=5).astype(np.float32)
            done = bool(index == 95)
            root.push(state, action, reward, next_state, done)
            copied.push(state, action, reward, next_state, done)

        for step in range(4):
            np.random.seed(141 + step)
            torch.manual_seed(241 + step)
            expected = root.train_step()
            np.random.seed(141 + step)
            torch.manual_seed(241 + step)
            actual = copied.train_step()
            self.assertAlmostEqual(
                actual["critic_loss"],
                expected["critic_loss"],
                places=7,
            )
            self.assertEqual(actual["actor_slot"], expected["actor_slot"])
            if expected["actor_loss"] is None:
                self.assertIsNone(actual["actor_loss"])
            else:
                self.assertAlmostEqual(
                    actual["actor_loss"],
                    expected["actor_loss"],
                    places=7,
                )
        for root_parameter, copied_parameter in zip(
            root.actor.parameters(),
            copied.actor.parameters(),
        ):
            torch.testing.assert_close(copied_parameter, root_parameter)
        for root_parameter, copied_parameter in zip(
            root.critic.parameters(),
            copied.critic.parameters(),
        ):
            torch.testing.assert_close(copied_parameter, root_parameter)

    def test_online_noise_continues_from_offline_endpoint(self) -> None:
        schedule = GaussianNoiseSchedule()
        self.assertEqual(schedule.value(0), 0.02)
        self.assertEqual(schedule.value(5_000), 0.01)
        self.assertEqual(schedule.value(50_000), 0.01)

    def test_latest_actor_bundle_passes_golden_cases(self) -> None:
        model = BioSMBTD3Policy.load(MODELS_DIR / "td3_actor_manifest.json")
        self.assertEqual(model.manifest["algorithm"], "custom_td3")
        self.assertEqual(model.manifest["source"]["total_steps"], 500_000)

    def test_training_checkpoint_actor_matches_deployment_actor(self) -> None:
        training_agent = CopiedTD3Agent(device=torch.device("cpu"), seed=7)
        training_agent.load(str(MODELS_DIR / "td3_training_checkpoint.pkl"))
        deployed = BioSMBTD3Policy.load(MODELS_DIR / "td3_actor_manifest.json")
        states = [case["state"] for case in deployed.manifest["golden_cases"]]
        for state in states:
            expected = training_agent.act_eval(np.asarray(state, np.float32))
            actual, _ = deployed.predict(state, deterministic=True)
            np.testing.assert_allclose(actual, expected, atol=1.0e-7, rtol=0.0)


class ModelArtifactTests(unittest.TestCase):
    def test_deployment_artifacts_are_exact_latest_run_copies(self) -> None:
        source_bundle = SOURCE_RUN / "deployment_bundle"
        for name in ["td3_actor_manifest.json", "td3_actor_weights.pt"]:
            self.assertEqual(
                (MODELS_DIR / name).read_bytes(),
                (source_bundle / name).read_bytes(),
            )

    def test_training_artifacts_are_exact_latest_run_copies(self) -> None:
        self.assertEqual(
            (MODELS_DIR / "td3_training_checkpoint.pkl").read_bytes(),
            (
                SOURCE_RUN
                / "checkpoints"
                / "offline_ph_td3_20260710_183222.pkl"
            ).read_bytes(),
        )
        self.assertEqual(
            (MODELS_DIR / "td3_training_config.json").read_bytes(),
            (SOURCE_RUN / "tables" / "config_snapshot.json").read_bytes(),
        )

    def test_historical_sac_artifacts_are_absent(self) -> None:
        self.assertFalse(
            (MODELS_DIR / "sac_biosmb_mixing_online_checkpoint.zip").exists()
        )
        self.assertFalse(
            (
                MODELS_DIR
                / "sac_biosmb_mixing_online_checkpoint_replay_buffer.pkl"
            ).exists()
        )

    def test_online_configuration_is_active_and_starts_at_offline_noise(self) -> None:
        import json

        config = json.loads(
            (MODELS_DIR / "td3_online_training_config.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["exploration"]["std_start"], 0.02)
        self.assertEqual(config["exploration"]["std_end"], 0.01)
        self.assertEqual(config["batch_size"], 64)
        self.assertEqual(config["buffer_size"], 10_000)
        self.assertEqual(config["replay"]["recent_window"], 200)
        self.assertTrue(config["safety_status"]["online_updates_enabled"])
        self.assertTrue(config["safety_status"]["exploratory_actions_enabled"])


class OnlineTrainingIntegrationTests(unittest.TestCase):
    def test_new_offline_checkpoint_overrides_stale_network_config(self) -> None:
        root_agent = RootTD3Agent(
            state_dim=5,
            action_dim=2,
            actor_hidden=[64, 64],
            critic_hidden=[64, 64],
            gamma=0.99,
            batch_size=64,
            buffer_size=100,
            device=torch.device("cpu"),
            seed=7,
        )
        temp_dir = ROOT / "results"
        checkpoint_path = None
        config_path = temp_dir / "_test_td3_online_training_config.json"
        try:
            checkpoint_path = root_agent.save(
                str(temp_dir),
                prefix="offline_ph_td3_test",
                include_optim=True,
            )
            config = json.loads(
                (MODELS_DIR / "td3_online_training_config.json").read_text(
                    encoding="utf-8"
                )
            )
            config["actor_hidden"] = [128, 128]
            config["critic_hidden"] = [128, 128]
            config["gamma"] = 0.97
            config_path.write_text(json.dumps(config), encoding="utf-8")

            trainer = BioSMBOnlineTD3Trainer.load(
                config_path=config_path,
                source_checkpoint=checkpoint_path,
                checkpoint_directory=temp_dir / "online_checkpoints",
                device="cpu",
            )
        finally:
            config_path.unlink(missing_ok=True)
            if checkpoint_path is not None:
                Path(checkpoint_path).unlink(missing_ok=True)

        self.assertEqual(trainer.agent.actor_hidden, [64, 64])
        self.assertEqual(trainer.agent.critic_hidden, [64, 64])
        self.assertEqual(trainer.agent.gamma, 0.99)
        self.assertEqual(
            trainer.config["resolved_source_checkpoint"]["checkpoint_kind"],
            "custom_td3_offline_training_v2",
        )

    def test_reward_replay_and_first_batch_update_are_connected(self) -> None:
        policy = BioSMBTD3Policy.load(MODELS_DIR / "td3_actor_manifest.json")
        trainer = BioSMBOnlineTD3Trainer.load(
            config_path=MODELS_DIR / "td3_online_training_config.json",
            source_checkpoint=MODELS_DIR / "td3_training_checkpoint.pkl",
            checkpoint_directory=MODELS_DIR / "_unused_test_checkpoints",
            device="cpu",
        )
        trainer.verify_initial_actor(policy)
        self.assertEqual(trainer.agent.batch_size, 64)
        self.assertEqual(trainer.agent.buffer.capacity, 10_000)
        self.assertEqual(trainer.agent.buffer.recent_window, 200)

        state = np.asarray(
            policy.manifest["golden_cases"][0]["state"],
            dtype=np.float32,
        )
        action, exploration = trainer.take_action(state)
        default_action = policy.default_action()["raw_action"]
        self.assertGreaterEqual(exploration["exploration_sigma"], 0.01)
        self.assertLessEqual(exploration["exploration_sigma"], 0.02)

        reward_info = None
        training_info = None
        for _ in range(64):
            reward_info, training_info = trainer.record_transition(
                state=state,
                action=action,
                reward_target_ph=4.76,
                measured_ph_after=4.75,
                previous_action=action,
                default_action=default_action,
                next_state=state,
                buffer_sum=15.0,
                previous_buffer_sum=15.0,
                buffer_sum_min=2.0,
                buffer_sum_max=20.0,
                done=False,
            )

        self.assertIsNotNone(reward_info)
        self.assertTrue(np.isfinite(reward_info["reward"]))
        self.assertEqual(training_info["buffer_size"], 64)
        self.assertTrue(training_info["train_updated"])
        self.assertEqual(training_info["train_steps"], 1)


if __name__ == "__main__":
    unittest.main()
