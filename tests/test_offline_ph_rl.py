from __future__ import annotations

import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation.ph_environment import PHEnvironment, PHEnvironmentConfig
from TD3Agent.agent import TD3Agent


def test_environment_reset_and_step() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76, max_episode_steps=3))
    observation, info = env.reset(seed=11)
    assert observation.shape == (7,)
    assert env.action_space.shape == (3,)
    assert np.all(np.isfinite(observation))
    assert info["target_ph"] == 4.76

    next_observation, reward, terminated, truncated, step_info = env.step(
        np.array([0.0, 0.0, 0.0], dtype=np.float32)
    )
    assert next_observation.shape == (7,)
    assert np.all(np.isfinite(next_observation))
    assert np.isfinite(reward)
    assert terminated is False
    assert truncated is False
    assert "reward_tracking_cost" in step_info


def test_action_bounds_and_ratio_direction() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    env.reset(options={"target_ph": 4.76})
    _, _, _, _, high_info = env.step(np.array([-1.0, 1.0, -1.0], dtype=np.float32))
    _, _, _, _, low_info = env.step(np.array([1.0, -1.0, -1.0], dtype=np.float32))

    assert high_info["acid_flow"] == 1.0
    assert high_info["acetate_flow"] == 10.0
    assert high_info["water_flow"] == 1.0
    assert low_info["acid_flow"] == 10.0
    assert low_info["acetate_flow"] == 1.0
    assert high_info["ph"] > low_info["ph"]


def test_water_is_logged_but_not_direct_hh_ratio_input() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    env.reset(options={"target_ph": 4.76})
    _, _, _, _, low_water_info = env.step(
        np.array([0.0, 0.0, -1.0], dtype=np.float32)
    )
    _, _, _, _, high_water_info = env.step(
        np.array([0.0, 0.0, 1.0], dtype=np.float32)
    )

    assert low_water_info["water_flow"] == 1.0
    assert high_water_info["water_flow"] == 10.0
    assert np.isclose(low_water_info["ph"], high_water_info["ph"])
    assert np.isclose(
        low_water_info["molar_base_acid_ratio"],
        high_water_info["molar_base_acid_ratio"],
    )


def test_public_flow_helpers_and_target_update() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    observation, info = env.reset(options={"target_ph": 4.76})
    assert np.isclose(info["target_ph"], 4.76)

    flows = env.action_to_flows(np.array([-2.0, 0.0, 2.0], dtype=np.float32))
    assert np.allclose(flows, np.array([1.0, 5.5, 10.0], dtype=np.float32))
    action = env.flows_to_action(flows)
    assert np.all(action >= -1.0)
    assert np.all(action <= 1.0)

    nominal_flows = env.target_to_nominal_flows(4.76)
    assert np.allclose(nominal_flows[:2], np.array([5.0, 5.0], dtype=np.float32))

    next_observation, next_info = env.set_target_ph(5.10)
    assert observation.shape == next_observation.shape
    assert np.isclose(next_info["target_ph"], 5.10)
    assert np.isclose(next_info["ph"], info["ph"])


def test_td3_import_and_train_step_smoke() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76, max_episode_steps=20))
    observation, _ = env.reset(seed=3)
    agent = TD3Agent(
        state_dim=7,
        action_dim=3,
        actor_hidden=[16],
        critic_hidden=[16],
        batch_size=4,
        buffer_size=64,
        device=torch.device("cpu"),
        seed=5,
    )
    rng = np.random.default_rng(13)
    meta = None
    for _ in range(8):
        action = rng.uniform(-1.0, 1.0, size=3).astype(np.float32)
        next_observation, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        agent.push(observation, action, reward, next_observation, done)
        observation = next_observation
        meta = agent.train_step()
        if done:
            observation, _ = env.reset()

    assert isinstance(meta, dict)
    assert meta["critic_updated"] is True


def run_direct() -> None:
    test_environment_reset_and_step()
    test_action_bounds_and_ratio_direction()
    test_water_is_logged_but_not_direct_hh_ratio_input()
    test_public_flow_helpers_and_target_update()
    test_td3_import_and_train_step_smoke()
    print("offline pH RL smoke tests passed")


if __name__ == "__main__":
    run_direct()
