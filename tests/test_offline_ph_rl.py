from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.offline_ph_td3_results import save_offline_ph_td3_result_artifacts
from run_offline_ph_td3_training import (
    build_setpoint_schedule,
    resolve_n_tests,
    resolve_set_points_len,
    validate_trajectory_flow_constraints,
)
from simulation.config import PHProcessConfig
from simulation.ph_environment import (
    PHEnvironment,
    PHEnvironmentConfig,
    fixed_buffer_target_ph_bounds,
)
from simulation.ph_reward import (
    PHRewardConfig,
    compute_ph_reward,
    compute_relative_band_offset_ph_reward,
    compute_relative_band_ph_reward,
    compute_three_term_ph_reward,
)
from TD3Agent.agent import TD3Agent


def test_environment_reset_and_step() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76, max_episode_steps=3))
    observation, info = env.reset(seed=11)
    assert observation.shape == (5,)
    assert env.action_space.shape == (1,)
    assert np.all(np.isfinite(observation))
    assert info["target_ph"] == 4.76

    next_observation, reward, terminated, truncated, step_info = env.step(
        np.array([0.0], dtype=np.float32)
    )
    assert next_observation.shape == (5,)
    assert np.all(np.isfinite(next_observation))
    assert np.isfinite(reward)
    assert terminated is False
    assert truncated is False
    assert "reward_tracking_cost" in step_info
    assert "reward_absolute_error_cost" in step_info
    assert "reward_move_cost" in step_info


def test_environment_reward_components() -> None:
    env = PHEnvironment(
        PHEnvironmentConfig(
            target_ph=4.76,
            tracking_weight=1.0,
            absolute_error_weight=2.0,
            move_penalty_weight=0.1,
            default_flow_penalty_weight=0.0,
        )
    )
    env.reset(options={"target_ph": 4.76})
    action = np.array([1.0], dtype=np.float32)
    previous_action = env.flows_to_action(env.current_flows)
    _, reward, _, _, info = env.step(action)

    setpoint_error = float(info["target_ph"] - info["ph"])
    squared_cost = setpoint_error**2
    absolute_cost = abs(setpoint_error)
    move_cost = float(np.mean(np.square(action - previous_action)))
    expected_total = squared_cost + 2.0 * absolute_cost + 0.1 * move_cost

    assert np.isclose(info["reward_squared_error_cost"], squared_cost)
    assert np.isclose(info["reward_absolute_error_cost"], absolute_cost)
    assert np.isclose(info["reward_move_cost"], move_cost)
    assert np.isclose(info["reward_total_cost"], expected_total)
    assert np.isclose(reward, -expected_total)


def test_default_reward_function_matches_previous_three_term() -> None:
    action = np.array([1.0], dtype=np.float32)
    previous_action = np.array([0.25], dtype=np.float32)
    cfg = PHRewardConfig(
        mode="three_term",
        q_squared=1.0,
        q_absolute=2.0,
        move_weight=0.1,
    )

    breakdown = compute_three_term_ph_reward(
        target_ph=4.76,
        ph=4.91,
        action=action,
        previous_action=previous_action,
        config=cfg,
    )

    setpoint_error = 4.76 - 4.91
    expected_cost = setpoint_error**2 + 2.0 * abs(setpoint_error) + 0.1 * 0.75**2
    assert np.isclose(breakdown.squared_error_cost, setpoint_error**2)
    assert np.isclose(breakdown.absolute_error_cost, abs(setpoint_error))
    assert np.isclose(breakdown.move_cost, 0.75**2)
    assert np.isclose(breakdown.total_cost, expected_cost)
    assert np.isclose(breakdown.reward, -expected_cost)


def test_zero_error_scores_better_than_nonzero_error() -> None:
    cfg = PHRewardConfig(mode="relative_band")
    zero = compute_ph_reward(
        target_ph=4.76,
        ph=4.76,
        action=np.array([0.0]),
        previous_action=np.array([0.0]),
        config=cfg,
    )
    offset = compute_ph_reward(
        target_ph=4.76,
        ph=4.80,
        action=np.array([0.0]),
        previous_action=np.array([0.0]),
        config=cfg,
    )

    assert zero.reward > offset.reward
    assert zero.absolute_error_cost == 0.0
    assert offset.absolute_error_cost > 0.0


def test_relative_band_reward_exposes_shaping_components() -> None:
    cfg = PHRewardConfig(mode="relative_band", band_floor_ph=0.02)
    breakdown = compute_relative_band_ph_reward(
        target_ph=4.76,
        ph=4.80,
        action=np.array([0.4]),
        previous_action=np.array([0.1]),
        config=cfg,
    )

    assert np.isclose(breakdown.band_ph, 0.02)
    assert breakdown.normalized_error > 1.0
    assert 0.0 <= breakdown.inside_weight <= 1.0
    assert breakdown.linear_out_term > 0.0
    assert breakdown.linear_in_term >= 0.0
    assert breakdown.move_penalty_term > 0.0
    assert breakdown.bonus_term >= 0.0


def test_relative_band_offset_penalizes_late_hold_offset_more() -> None:
    cfg = PHRewardConfig(
        mode="relative_band_offset",
        absolute_error_weight=1.0,
        tail_offset_weight=5.0,
    )
    kwargs = {
        "target_ph": 4.76,
        "ph": 4.80,
        "action": np.array([0.0]),
        "previous_action": np.array([0.0]),
        "config": cfg,
    }
    early = compute_relative_band_offset_ph_reward(**kwargs, hold_progress=0.10)
    late = compute_relative_band_offset_ph_reward(**kwargs, hold_progress=0.95)

    assert np.isclose(early.tail_offset_term, 0.0)
    assert late.tail_offset_term > early.tail_offset_term
    assert late.reward < early.reward


def test_invalid_reward_mode_raises() -> None:
    try:
        PHRewardConfig(mode="not_a_reward")
    except ValueError as exc:
        assert "reward mode" in str(exc)
    else:
        raise AssertionError("expected invalid reward mode to fail")


def test_action_bounds_and_ratio_direction() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    env.reset(options={"target_ph": 4.76})
    _, _, _, _, high_info = env.step(np.array([1.0], dtype=np.float32))
    _, _, _, _, low_info = env.step(np.array([-1.0], dtype=np.float32))

    assert high_info["acid_flow"] == 5.0
    assert high_info["acetate_flow"] == 10.0
    assert high_info["water_flow"] == 5.0
    assert low_info["acid_flow"] == 10.0
    assert low_info["acetate_flow"] == 5.0
    assert low_info["water_flow"] == 5.0
    assert high_info["buffer_flow_sum"] == 15.0
    assert low_info["buffer_flow_sum"] == 15.0
    assert high_info["ph"] > low_info["ph"]

    for raw_action in np.linspace(-5.0, 5.0, num=41):
        flows = env.action_to_flows(np.array([raw_action], dtype=np.float32))
        assert np.all(flows >= env.flow_low - 1e-6)
        assert np.all(flows <= env.flow_high + 1e-6)
        assert np.isclose(flows[0] + flows[1], 15.0)
        assert np.isclose(flows[2], 5.0)
        env.step(np.array([raw_action], dtype=np.float32))
        env.assert_current_flow_constraints()


def test_runner_flow_constraint_validation() -> None:
    process_config = PHProcessConfig()
    valid = pd.DataFrame(
        {
            "acid_flow": [5.0, 7.5, 10.0],
            "acetate_flow": [10.0, 7.5, 5.0],
            "water_flow": [5.0, 5.0, 5.0],
            "buffer_flow_sum": [15.0, 15.0, 15.0],
        }
    )
    check = validate_trajectory_flow_constraints(
        trajectory=valid,
        process_config=process_config,
        fixed_buffer_flow_sum=15.0,
        fixed_water_flow=5.0,
    )
    assert int(check["above_bound_count"].sum()) == 0
    assert int(check["below_bound_count"].sum()) == 0

    invalid = valid.copy()
    invalid.loc[1, "acetate_flow"] = 10.1
    invalid.loc[1, "buffer_flow_sum"] = 17.6
    try:
        validate_trajectory_flow_constraints(
            trajectory=invalid,
            process_config=process_config,
            fixed_buffer_flow_sum=15.0,
            fixed_water_flow=5.0,
        )
    except ValueError as exc:
        assert "acetate_flow outside" in str(exc)
    else:
        raise AssertionError("expected flow constraint validation to fail")


def test_water_is_fixed_and_not_direct_hh_ratio_input() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    env.reset(options={"target_ph": 4.76})
    _, _, _, _, first_info = env.step(np.array([0.0], dtype=np.float32))
    _, _, _, _, second_info = env.step(np.array([0.0], dtype=np.float32))

    assert first_info["water_flow"] == 5.0
    assert second_info["water_flow"] == 5.0
    assert np.isclose(first_info["ph"], second_info["ph"])
    assert np.isclose(
        first_info["molar_base_acid_ratio"],
        second_info["molar_base_acid_ratio"],
    )


def test_public_flow_helpers_and_target_update() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76))
    observation, info = env.reset(options={"target_ph": 4.76})
    assert np.isclose(info["target_ph"], 4.76)

    flows = env.action_to_flows(np.array([-2.0], dtype=np.float32))
    assert np.allclose(flows, np.array([10.0, 5.0, 5.0], dtype=np.float32))
    action = env.flows_to_action(flows)
    assert action.shape == (1,)
    assert np.all(action >= -1.0)
    assert np.all(action <= 1.0)

    nominal_flows = env.target_to_nominal_flows(4.76)
    assert np.allclose(nominal_flows, np.array([7.5, 7.5, 5.0], dtype=np.float32))

    next_observation, next_info = env.set_target_ph(5.10)
    assert observation.shape == next_observation.shape
    assert np.isclose(next_info["target_ph"], 5.10)
    assert np.isclose(next_info["ph"], info["ph"])


def test_td3_import_and_train_step_smoke() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76, max_episode_steps=20))
    observation, _ = env.reset(seed=3)
    agent = TD3Agent(
        state_dim=5,
        action_dim=1,
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
        action = rng.uniform(-1.0, 1.0, size=1).astype(np.float32)
        next_observation, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        agent.push(observation, action, reward, next_observation, done)
        observation = next_observation
        meta = agent.train_step()
        if done:
            observation, _ = env.reset()

    assert isinstance(meta, dict)
    assert meta["critic_updated"] is True


def test_result_artifact_helper_smoke() -> None:
    env = PHEnvironment(PHEnvironmentConfig(target_ph=4.76, max_episode_steps=5))
    observation, _ = env.reset(seed=19, options={"target_ph": 4.76})
    del observation

    records = []
    for step, action in enumerate(
        [
            np.array([0.0], dtype=np.float32),
            np.array([0.2], dtype=np.float32),
            np.array([-0.1], dtype=np.float32),
        ]
    ):
        _, reward, _, _, info = env.step(action)
        target_ph = float(info["target_ph"])
        records.append(
            {
                "step": step,
                "cycle": 0,
                "is_warm_start": False,
                "is_test": step == 2,
                "action_source": "smoke",
                "target_ph": target_ph,
                "ph": float(info["ph"]),
                "ph_error": float(info["ph"] - target_ph),
                "reward": float(reward),
                "reward_setpoint_error": float(info["reward_setpoint_error"]),
                "reward_squared_error_cost": float(info["reward_squared_error_cost"]),
                "reward_absolute_error_cost": float(
                    info["reward_absolute_error_cost"]
                ),
                "reward_move_cost": float(info["reward_move_cost"]),
                "reward_total_cost": float(info["reward_total_cost"]),
                "acid_flow": float(info["acid_flow"]),
                "acetate_flow": float(info["acetate_flow"]),
                "water_flow": float(info["water_flow"]),
                "buffer_flow_sum": float(info["buffer_flow_sum"]),
                "flow_ratio_acetate_acid": float(info["flow_ratio_acetate_acid"]),
                "action_ratio": float(action[0]),
                "train_updated": False,
                "critic_loss": np.nan,
                "actor_loss": np.nan,
            }
        )

    trajectory = pd.DataFrame.from_records(records)
    episode_metrics = pd.DataFrame(
        [
            {
                "cycle": 0,
                "target_ph": 4.76,
                "is_test": True,
                "steps": len(trajectory),
                "mean_ph": float(trajectory["ph"].mean()),
                "mean_abs_error": float(np.mean(np.abs(trajectory["ph_error"]))),
                "rmse": float(np.sqrt(np.mean(np.square(trajectory["ph_error"])))),
                "max_abs_error": float(np.max(np.abs(trajectory["ph_error"]))),
                "reward_sum": float(trajectory["reward"].sum()),
                "train_updates": 0,
            }
        ]
    )
    training_summary = pd.DataFrame([{"total_steps": len(trajectory)}])
    config = {"process_config": PHProcessConfig().__dict__}

    output_dir = ROOT / "results" / "_test_offline_ph_td3_artifacts"
    artifacts = save_offline_ph_td3_result_artifacts(
        output_dir=output_dir,
        trajectory=trajectory,
        episode_metrics=episode_metrics,
        training_summary=training_summary,
        config=config,
    )
    assert (output_dir / "tables" / "summary_metrics.csv").exists()
    assert (output_dir / "tables" / "trajectory_diagnostics.csv").exists()
    assert (output_dir / "tables" / "result_artifact_manifest.json").exists()
    assert len(artifacts["figures"]) >= 5
    assert all(path.exists() for path in artifacts["figures"])


def test_default_total_step_resolution() -> None:
    assert resolve_set_points_len(
        total_steps=25_000,
        n_tests=None,
        set_points_len=None,
    ) == 200
    assert resolve_n_tests(
        total_steps=25_000,
        n_tests=None,
        set_points_len=200,
    ) == 125
    assert resolve_set_points_len(
        total_steps=25_000,
        n_tests=10,
        set_points_len=None,
    ) == 2500
    assert resolve_set_points_len(
        total_steps=25_000,
        n_tests=10,
        set_points_len=6,
    ) == 6


def test_admissible_random_setpoint_schedule() -> None:
    process_config = PHProcessConfig()
    target_min, target_max = fixed_buffer_target_ph_bounds(
        process_config=process_config,
        fixed_buffer_flow_sum=15.0,
    )
    schedule, cycle_indices, setpoints = build_setpoint_schedule(
        process_config=process_config,
        n_tests=8,
        set_points_len=200,
        seed=101,
        strategy="admissible_random",
        target_ph_min=target_min,
        target_ph_max=target_max,
    )

    assert schedule.shape == (1600,)
    assert cycle_indices.shape == (1600,)
    assert setpoints.shape == (8,)
    assert np.all(setpoints >= target_min)
    assert np.all(setpoints <= target_max)
    assert len(np.unique(np.round(setpoints, decimals=6))) == len(setpoints)
    assert np.all(schedule[:200] == setpoints[0])
    assert np.all(schedule[200:400] == setpoints[1])


def run_direct() -> None:
    test_environment_reset_and_step()
    test_environment_reward_components()
    test_default_reward_function_matches_previous_three_term()
    test_zero_error_scores_better_than_nonzero_error()
    test_relative_band_reward_exposes_shaping_components()
    test_relative_band_offset_penalizes_late_hold_offset_more()
    test_invalid_reward_mode_raises()
    test_action_bounds_and_ratio_direction()
    test_runner_flow_constraint_validation()
    test_water_is_fixed_and_not_direct_hh_ratio_input()
    test_public_flow_helpers_and_target_update()
    test_td3_import_and_train_step_smoke()
    test_result_artifact_helper_smoke()
    test_default_total_step_resolution()
    test_admissible_random_setpoint_schedule()
    print("offline pH RL smoke tests passed")


if __name__ == "__main__":
    run_direct()
