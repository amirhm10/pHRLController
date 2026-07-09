from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from TD3Agent.agent import TD3Agent, set_global_seeds
from helpers.offline_ph_td3_results import save_offline_ph_td3_result_artifacts
from simulation.config import PHProcessConfig
from simulation.ph_environment import (
    PHEnvironment,
    PHEnvironmentConfig,
    fixed_buffer_target_ph_bounds,
    variable_buffer_target_ph_bounds,
)
from simulation.ph_reward import PHRewardConfig, reward_definition_text


DEFAULT_SET_POINTS_LEN = 200
DEFAULT_SETPOINT_DATA_PATH = Path(
    "Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv"
)
DEFAULT_SETPOINT_COLUMN = "target_ph"

OPTIONAL_INFO_COLUMNS = [
    "reward_band_ph",
    "reward_normalized_error",
    "reward_inside_weight",
    "reward_error_effective_term",
    "reward_linear_out_term",
    "reward_linear_in_term",
    "reward_bonus_term",
    "reward_sum_move_cost",
    "reward_sum_move_penalty_term",
    "reward_tail_offset_cost",
    "reward_tail_offset_term",
    "reward_hold_progress",
    "reward_hold_weight",
    "reward_scale",
    "setpoint_hold_step",
    "setpoint_hold_progress",
]


def parse_hidden_layers(value: str) -> list[int]:
    layers = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not layers:
        raise argparse.ArgumentTypeError("hidden layer list cannot be empty.")
    return layers


def build_setpoint_schedule(
    process_config: PHProcessConfig,
    n_tests: int,
    set_points_len: int,
    seed: int,
    strategy: str = "admissible_random",
    target_ph_min: float | None = None,
    target_ph_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create piecewise-constant pH targets and cycle indices."""
    if n_tests <= 0:
        raise ValueError("n_tests must be positive.")
    if set_points_len <= 0:
        raise ValueError("set_points_len must be positive.")
    target_low = (
        process_config.target_ph_min if target_ph_min is None else float(target_ph_min)
    )
    target_high = (
        process_config.target_ph_max if target_ph_max is None else float(target_ph_max)
    )
    if target_low >= target_high:
        raise ValueError("target_ph_min must be lower than target_ph_max.")

    strategy = str(strategy).lower()
    if strategy == "legacy_fixed":
        base_targets = np.array(
            [
                target_low + 0.10 * (target_high - target_low),
                process_config.pKa - 0.35,
                process_config.pKa,
                process_config.pKa + 0.35,
                target_high - 0.10 * (target_high - target_low),
            ],
            dtype=np.float32,
        )
        base_targets = np.clip(base_targets, target_low, target_high)
        targets = np.resize(base_targets, n_tests)
    elif strategy == "admissible_random":
        rng = np.random.default_rng(seed)
        edges = np.linspace(
            target_low,
            target_high,
            n_tests + 1,
            dtype=np.float64,
        )
        targets = rng.uniform(edges[:-1], edges[1:]).astype(np.float32)
        rng.shuffle(targets)
    else:
        raise ValueError(
            "setpoint strategy must be 'admissible_random' or 'legacy_fixed'."
        )

    schedule = np.repeat(targets, set_points_len).astype(np.float32)
    cycle_indices = np.repeat(np.arange(n_tests), set_points_len)
    return schedule, cycle_indices, targets


def load_setpoint_range_from_csv(
    path: Path,
    column: str = DEFAULT_SETPOINT_COLUMN,
) -> tuple[float, float, int]:
    """Return finite target-pH min, max, and count from a lab-data CSV."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"setpoint range CSV not found: {path}")
    try:
        values = pd.read_csv(path, usecols=[column])[column]
    except ValueError as exc:
        raise ValueError(f"setpoint range CSV must contain column '{column}'.") from exc
    values = pd.to_numeric(values, errors="coerce").to_numpy(float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError(f"setpoint column '{column}' contains no finite values.")
    return float(np.min(values)), float(np.max(values)), int(values.size)


def resolve_training_target_ph_bounds(
    *,
    args: argparse.Namespace,
    process_config: PHProcessConfig,
    reachable_bounds: tuple[float, float],
) -> tuple[float, float, dict]:
    """Resolve the actual training target range and source metadata."""
    reachable_low, reachable_high = map(float, reachable_bounds)
    if args.setpoint_range_source == "reachable":
        desired_low = reachable_low
        desired_high = reachable_high
        desired_count = None
        source = "reachable_action_range"
    elif args.setpoint_range_source == "lab_data":
        desired_low, desired_high, desired_count = load_setpoint_range_from_csv(
            path=args.setpoint_data_path,
            column=args.setpoint_column,
        )
        source = "lab_data_target_ph_range"
    else:
        raise ValueError("setpoint_range_source must be 'lab_data' or 'reachable'.")

    target_low = max(desired_low, reachable_low, float(process_config.target_ph_min))
    target_high = min(desired_high, reachable_high, float(process_config.target_ph_max))
    if target_low >= target_high:
        raise ValueError(
            "Resolved setpoint range is empty after intersecting desired, "
            "reachable, and process target bounds."
        )
    metadata = {
        "setpoint_source": source,
        "setpoint_data_path": str(args.setpoint_data_path)
        if args.setpoint_range_source == "lab_data"
        else None,
        "setpoint_column": str(args.setpoint_column)
        if args.setpoint_range_source == "lab_data"
        else None,
        "desired_setpoint_min": float(desired_low),
        "desired_setpoint_max": float(desired_high),
        "desired_setpoint_count": desired_count,
        "reachable_setpoint_min": float(reachable_low),
        "reachable_setpoint_max": float(reachable_high),
        "resolved_setpoint_min": float(target_low),
        "resolved_setpoint_max": float(target_high),
        "range_was_clipped": bool(
            not np.isclose(target_low, desired_low)
            or not np.isclose(target_high, desired_high)
        ),
    }
    return float(target_low), float(target_high), metadata


def resolve_set_points_len(
    total_steps: int,
    n_tests: int | None,
    set_points_len: int | None,
) -> int:
    """Resolve steps per setpoint cycle from total rollout length."""
    if total_steps <= 0:
        raise ValueError("total_steps must be positive.")
    if set_points_len is not None:
        if set_points_len <= 0:
            raise ValueError("set_points_len must be positive when provided.")
        return int(set_points_len)
    if n_tests is None:
        return DEFAULT_SET_POINTS_LEN
    if n_tests <= 0:
        raise ValueError("n_tests must be positive.")
    if total_steps % n_tests != 0:
        raise ValueError(
            "total_steps must be divisible by n_tests when set_points_len is not provided."
        )
    return int(total_steps // n_tests)


def resolve_n_tests(
    total_steps: int,
    n_tests: int | None,
    set_points_len: int,
) -> int:
    """Resolve number of setpoint segments in the rollout."""
    if total_steps <= 0:
        raise ValueError("total_steps must be positive.")
    if set_points_len <= 0:
        raise ValueError("set_points_len must be positive.")
    if n_tests is not None:
        if n_tests <= 0:
            raise ValueError("n_tests must be positive.")
        if total_steps != n_tests * set_points_len:
            raise ValueError(
                "total_steps must equal n_tests * set_points_len when both are provided."
            )
        return int(n_tests)
    if total_steps % set_points_len != 0:
        raise ValueError(
            "total_steps must be divisible by set_points_len when n_tests is not provided."
        )
    return int(total_steps // set_points_len)


def create_agent(
    args: argparse.Namespace,
    state_dim: int,
    action_dim: int,
) -> TD3Agent:
    return TD3Agent(
        state_dim=int(state_dim),
        action_dim=int(action_dim),
        actor_hidden=args.actor_hidden,
        critic_hidden=args.critic_hidden,
        gamma=args.gamma,
        actor_lr=args.actor_lr,
        critic_lr=args.critic_lr,
        batch_size=args.batch_size,
        buffer_size=args.buffer_size,
        std_start=args.std_start,
        std_end=args.std_end,
        std_decay_rate=args.std_decay_rate,
        std_decay_steps=args.std_decay_steps,
        std_decay_mode=args.std_decay_mode,
        max_action=1.0,
        device=torch.device(args.device),
        seed=args.seed,
    )


def make_output_dir(root: Path | None) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = root or Path("results") / f"offline_ph_td3_training_{timestamp}"
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)
    (output_dir / "figures").mkdir(parents=True, exist_ok=True)
    return output_dir


def build_reward_config(args: argparse.Namespace) -> PHRewardConfig:
    return PHRewardConfig(
        mode=args.reward_mode,
        q_squared=args.reward_squared_weight,
        q_absolute=args.reward_absolute_weight,
        move_weight=args.move_penalty_weight,
        default_flow_weight=0.0,
        band_floor_ph=args.reward_band_floor_ph,
        q_band=args.reward_squared_weight,
        r_move=args.move_penalty_weight,
        sum_move_weight=args.sum_move_penalty_weight,
        beta=0.0,
        bonus_weight_abs=args.reward_bonus_weight,
        bonus_k=args.reward_bonus_k,
        absolute_error_weight=args.reward_absolute_weight,
        tail_offset_weight=args.reward_tail_offset_weight,
    )


def validate_trajectory_flow_constraints(
    trajectory: pd.DataFrame,
    process_config: PHProcessConfig,
    action_mode: str,
    fixed_buffer_flow_sum: float,
    buffer_flow_sum_min: float,
    buffer_flow_sum_max: float,
    fixed_water_flow: float,
    tolerance: float = 1e-6,
) -> pd.DataFrame:
    """Raise if any logged flow violates configured physical constraints."""
    rows: list[dict] = []
    violations: list[str] = []
    specs = [
        (
            "acid",
            "acid_flow",
            process_config.acid_flow_min,
            process_config.acid_flow_max,
        ),
        (
            "acetate",
            "acetate_flow",
            process_config.acetate_flow_min,
            process_config.acetate_flow_max,
        ),
        (
            "water",
            "water_flow",
            process_config.water_flow_min,
            process_config.water_flow_max,
        ),
    ]
    for label, column, lower, upper in specs:
        values = trajectory[column].to_numpy(float)
        finite = np.isfinite(values)
        below_count = int(np.sum(values < float(lower) - tolerance))
        above_count = int(np.sum(values > float(upper) + tolerance))
        nonfinite_count = int(np.sum(~finite))
        rows.append(
            {
                "constraint": f"{label}_bounds",
                "lower_bound": float(lower),
                "upper_bound": float(upper),
                "observed_min": float(np.nanmin(values)),
                "observed_max": float(np.nanmax(values)),
                "below_bound_count": below_count,
                "above_bound_count": above_count,
                "nonfinite_count": nonfinite_count,
                "max_abs_deviation": np.nan,
            }
        )
        if below_count or above_count or nonfinite_count:
            violations.append(
                f"{column} outside [{float(lower)}, {float(upper)}] "
                f"with min={float(np.nanmin(values))}, max={float(np.nanmax(values))}"
            )

    buffer_sum = (
        trajectory["buffer_flow_sum"].to_numpy(float)
        if "buffer_flow_sum" in trajectory
        else trajectory["acid_flow"].to_numpy(float)
        + trajectory["acetate_flow"].to_numpy(float)
    )
    action_mode = str(action_mode)
    if action_mode == "ratio":
        buffer_deviation = np.abs(buffer_sum - float(fixed_buffer_flow_sum))
        buffer_violation_count = int(np.sum(buffer_deviation > tolerance))
        rows.append(
            {
                "constraint": "fixed_buffer_flow_sum",
                "lower_bound": float(fixed_buffer_flow_sum),
                "upper_bound": float(fixed_buffer_flow_sum),
                "observed_min": float(np.nanmin(buffer_sum)),
                "observed_max": float(np.nanmax(buffer_sum)),
                "below_bound_count": 0,
                "above_bound_count": 0,
                "nonfinite_count": int(np.sum(~np.isfinite(buffer_sum))),
                "max_abs_deviation": float(np.nanmax(buffer_deviation)),
            }
        )
        if buffer_violation_count:
            violations.append(
                f"acid+acetate sum deviates from {float(fixed_buffer_flow_sum)} "
                f"by up to {float(np.nanmax(buffer_deviation))}"
            )
    elif action_mode == "ratio_buffer_sum":
        lower = float(buffer_flow_sum_min)
        upper = float(buffer_flow_sum_max)
        below_count = int(np.sum(buffer_sum < lower - tolerance))
        above_count = int(np.sum(buffer_sum > upper + tolerance))
        rows.append(
            {
                "constraint": "buffer_flow_sum_bounds",
                "lower_bound": lower,
                "upper_bound": upper,
                "observed_min": float(np.nanmin(buffer_sum)),
                "observed_max": float(np.nanmax(buffer_sum)),
                "below_bound_count": below_count,
                "above_bound_count": above_count,
                "nonfinite_count": int(np.sum(~np.isfinite(buffer_sum))),
                "max_abs_deviation": np.nan,
            }
        )
        if below_count or above_count:
            violations.append(
                f"acid+acetate sum outside [{lower}, {upper}] "
                f"with min={float(np.nanmin(buffer_sum))}, max={float(np.nanmax(buffer_sum))}"
            )
    else:
        raise ValueError("action_mode must be 'ratio' or 'ratio_buffer_sum'.")

    water_values = trajectory["water_flow"].to_numpy(float)
    water_deviation = np.abs(water_values - float(fixed_water_flow))
    fixed_water_violation_count = int(np.sum(water_deviation > tolerance))
    rows.append(
        {
            "constraint": "fixed_water_flow",
            "lower_bound": float(fixed_water_flow),
            "upper_bound": float(fixed_water_flow),
            "observed_min": float(np.nanmin(water_values)),
            "observed_max": float(np.nanmax(water_values)),
            "below_bound_count": 0,
            "above_bound_count": 0,
            "nonfinite_count": int(np.sum(~np.isfinite(water_values))),
            "max_abs_deviation": float(np.nanmax(water_deviation)),
        }
    )
    if fixed_water_violation_count:
        violations.append(
            f"water flow deviates from {float(fixed_water_flow)} "
            f"by up to {float(np.nanmax(water_deviation))}"
        )

    if violations:
        raise ValueError("Flow constraint validation failed: " + "; ".join(violations))
    return pd.DataFrame(rows)


def run_training(args: argparse.Namespace) -> dict[str, Path | pd.DataFrame]:
    set_global_seeds(args.seed)
    process_config = PHProcessConfig()
    reward_config = build_reward_config(args)
    if args.action_mode == "ratio":
        reachable_target_bounds = fixed_buffer_target_ph_bounds(
            process_config=process_config,
            fixed_buffer_flow_sum=args.fixed_buffer_flow_sum,
        )
    else:
        reachable_target_bounds = variable_buffer_target_ph_bounds(
            process_config=process_config,
            buffer_flow_sum_min=args.buffer_flow_sum_min,
            buffer_flow_sum_max=args.buffer_flow_sum_max,
        )
    target_ph_min, target_ph_max, setpoint_metadata = resolve_training_target_ph_bounds(
        args=args,
        process_config=process_config,
        reachable_bounds=reachable_target_bounds,
    )
    set_points_len = resolve_set_points_len(
        total_steps=args.total_steps,
        n_tests=args.n_tests,
        set_points_len=args.set_points_len,
    )
    n_setpoints = resolve_n_tests(
        total_steps=args.total_steps,
        n_tests=args.n_tests,
        set_points_len=set_points_len,
    )
    schedule, cycle_indices, setpoint_values = build_setpoint_schedule(
        process_config=process_config,
        n_tests=n_setpoints,
        set_points_len=set_points_len,
        seed=args.seed,
        strategy=args.setpoint_strategy,
        target_ph_min=target_ph_min,
        target_ph_max=target_ph_max,
    )
    total_steps = int(schedule.size)
    warm_start_steps = int(max(0, args.warm_start_cycles) * set_points_len)
    test_cycle = int(n_setpoints - 1)

    env = PHEnvironment(
        PHEnvironmentConfig(
            process_config=process_config,
            target_ph=float(schedule[0]),
            max_episode_steps=total_steps + 1,
            tracking_weight=args.reward_squared_weight,
            absolute_error_weight=args.reward_absolute_weight,
            move_penalty_weight=args.move_penalty_weight,
            default_flow_penalty_weight=0.0,
            reward_config=reward_config,
            setpoint_hold_steps=set_points_len,
            action_mode=args.action_mode,
            fixed_buffer_flow_sum=args.fixed_buffer_flow_sum,
            buffer_flow_sum_min=args.buffer_flow_sum_min,
            buffer_flow_sum_max=args.buffer_flow_sum_max,
            random_seed=args.seed,
        )
    )
    state, _ = env.reset(
        seed=args.seed,
        options={
            "target_ph": float(schedule[0]),
            "initial_flows": (
                env.target_to_nominal_flows(float(schedule[0]))
                if warm_start_steps > 0
                else env.default_flows
            ),
        },
    )
    agent = create_agent(
        args,
        state_dim=env.observation_space.shape[0],
        action_dim=env.action_space.shape[0],
    )

    records: list[dict] = []
    previous_target = float(schedule[0])

    for step_idx, target_ph_value in enumerate(schedule):
        target_ph = float(target_ph_value)
        cycle = int(cycle_indices[step_idx])
        if target_ph != previous_target:
            state, _ = env.set_target_ph(target_ph)
            previous_target = target_ph

        is_warm_start = step_idx < warm_start_steps
        is_test = cycle == test_cycle

        if is_warm_start:
            nominal_flows = env.target_to_nominal_flows(target_ph)
            action = env.flows_to_action(nominal_flows)
            action_source = "warm_start_hh"
            exploration_sigma = 0.0
            exploration_magnitude = 0.0
            action_saturation_fraction = float(
                np.mean(np.abs(np.asarray(action, dtype=float)) >= 1.0 - 1e-6)
            )
        elif is_test:
            action = agent.act_eval(state).astype(np.float32)
            action_source = "td3_eval"
            exploration_sigma = 0.0
            exploration_magnitude = 0.0
            action_saturation_fraction = float(
                np.mean(np.abs(np.asarray(action, dtype=float)) >= 1.0 - 1e-6)
            )
        else:
            action = agent.take_action(state, explore=True).astype(np.float32)
            action_source = "td3_explore"
            exploration_sigma = float(getattr(agent, "_expl_sigma", 0.0))
            exploration_magnitude = float(agent.last_exploration_value)
            action_saturation_fraction = (
                float(agent.action_saturation_trace[-1])
                if agent.action_saturation_trace
                else float("nan")
            )

        next_state, reward, terminated, truncated, info = env.step(action)
        done = bool(terminated or truncated or step_idx == total_steps - 1)

        agent.push(
            np.asarray(state, dtype=np.float32),
            np.asarray(action, dtype=np.float32),
            reward,
            np.asarray(next_state, dtype=np.float32),
            done,
        )

        train_meta = None
        if step_idx >= warm_start_steps and not is_test:
            train_meta = agent.train_step()

        record = {
            "step": step_idx,
            "cycle": cycle,
            "is_warm_start": bool(is_warm_start),
            "is_test": bool(is_test),
            "action_source": action_source,
            "target_ph": target_ph,
            "ph": float(info["ph"]),
            "ph_error": float(info["ph"] - target_ph),
            "reward_mode": str(info["reward_mode"]),
            "reward": float(reward),
            "reward_setpoint_error": float(info["reward_setpoint_error"]),
            "reward_squared_error_cost": float(info["reward_squared_error_cost"]),
            "reward_absolute_error_cost": float(info["reward_absolute_error_cost"]),
            "reward_move_cost": float(info["reward_move_cost"]),
            "reward_total_cost": float(info["reward_total_cost"]),
            "acid_flow": float(info["acid_flow"]),
            "acetate_flow": float(info["acetate_flow"]),
            "water_flow": float(info["water_flow"]),
            "flow_ratio_acetate_acid": float(info["flow_ratio_acetate_acid"]),
            "buffer_flow_sum": float(info["buffer_flow_sum"]),
            "action_ratio": float(np.asarray(action).reshape(-1)[0]),
            "action_buffer_sum": float(np.asarray(action).reshape(-1)[1])
            if np.asarray(action).reshape(-1).size > 1
            else np.nan,
            "normalized_buffer_sum_action": float(info["normalized_buffer_sum_action"]),
            "exploration_sigma": exploration_sigma,
            "exploration_magnitude": exploration_magnitude,
            "action_saturation_fraction": action_saturation_fraction,
            "train_updated": train_meta is not None,
            "critic_loss": np.nan
            if train_meta is None
            else float(train_meta["critic_loss"]),
            "actor_loss": np.nan
            if train_meta is None or train_meta["actor_loss"] is None
            else float(train_meta["actor_loss"]),
        }
        for column in OPTIONAL_INFO_COLUMNS:
            if column in info:
                value = info[column]
                record[column] = np.nan if value is None else float(value)
        records.append(record)
        state = next_state

    trajectory = pd.DataFrame.from_records(records)
    flow_constraint_check = validate_trajectory_flow_constraints(
        trajectory=trajectory,
        process_config=process_config,
        action_mode=args.action_mode,
        fixed_buffer_flow_sum=args.fixed_buffer_flow_sum,
        buffer_flow_sum_min=args.buffer_flow_sum_min,
        buffer_flow_sum_max=args.buffer_flow_sum_max,
        fixed_water_flow=env.fixed_water_flow,
    )
    episode_metrics = summarize_by_cycle(trajectory)
    summary = summarize_run(
        trajectory=trajectory,
        agent=agent,
        args=args,
        total_steps=total_steps,
        n_setpoints=n_setpoints,
        set_points_len=set_points_len,
        warm_start_steps=warm_start_steps,
        target_ph_min=target_ph_min,
        target_ph_max=target_ph_max,
        setpoint_metadata=setpoint_metadata,
        reward_config=reward_config,
        env=env,
    )
    setpoint_schedule = summarize_setpoint_schedule(
        setpoint_values=setpoint_values,
        set_points_len=set_points_len,
        test_cycle=test_cycle,
    )

    output_dir = make_output_dir(args.output_dir)
    trajectory.to_csv(output_dir / "tables" / "trajectory.csv", index=False)
    episode_metrics.to_csv(output_dir / "tables" / "episode_metrics.csv", index=False)
    setpoint_schedule.to_csv(
        output_dir / "tables" / "setpoint_schedule.csv",
        index=False,
    )
    flow_constraint_check.to_csv(
        output_dir / "tables" / "flow_constraint_check.csv",
        index=False,
    )
    summary.to_csv(output_dir / "tables" / "training_summary.csv", index=False)
    config_snapshot = write_config_snapshot(
        output_dir=output_dir,
        args=args,
        process_config=process_config,
        total_steps=total_steps,
        n_setpoints=n_setpoints,
        set_points_len=set_points_len,
        warm_start_steps=warm_start_steps,
        reward_config=reward_config,
        env=env,
        target_ph_min=target_ph_min,
        target_ph_max=target_ph_max,
        setpoint_metadata=setpoint_metadata,
    )
    artifacts = save_offline_ph_td3_result_artifacts(
        output_dir=output_dir,
        trajectory=trajectory,
        episode_metrics=episode_metrics,
        training_summary=summary,
        config=config_snapshot,
    )

    if args.save_checkpoint:
        agent.save(str(output_dir / "checkpoints"), prefix="offline_ph_td3")

    print(f"Saved offline pH TD3 results to: {output_dir}")
    print(f"Saved TD3 pH figures to: {artifacts['figures_dir']}")
    print(summary.to_string(index=False))
    return {
        "output_dir": output_dir,
        "trajectory": trajectory,
        "episode_metrics": episode_metrics,
        "summary": summary,
        "flow_constraint_check": flow_constraint_check,
        "artifacts": artifacts,
    }


def summarize_by_cycle(trajectory: pd.DataFrame) -> pd.DataFrame:
    grouped = trajectory.groupby("cycle", as_index=False)
    metrics = grouped.agg(
        target_ph=("target_ph", "first"),
        is_test=("is_test", "max"),
        steps=("step", "count"),
        mean_ph=("ph", "mean"),
        mean_abs_error=("ph_error", lambda x: float(np.mean(np.abs(x)))),
        rmse=("ph_error", lambda x: float(np.sqrt(np.mean(np.square(x))))),
        max_abs_error=("ph_error", lambda x: float(np.max(np.abs(x)))),
        reward_sum=("reward", "sum"),
        mean_reward=("reward", "mean"),
        squared_error_cost_sum=("reward_squared_error_cost", "sum"),
        absolute_error_cost_sum=("reward_absolute_error_cost", "sum"),
        move_cost_sum=("reward_move_cost", "sum"),
        sum_move_cost_sum=("reward_sum_move_cost", "sum"),
        total_cost_sum=("reward_total_cost", "sum"),
        train_updates=("train_updated", "sum"),
    )
    optional_sum_columns = [
        "reward_error_effective_term",
        "reward_linear_out_term",
        "reward_linear_in_term",
        "reward_bonus_term",
        "reward_sum_move_penalty_term",
        "reward_tail_offset_term",
    ]
    for column in optional_sum_columns:
        if column in trajectory:
            values = trajectory.groupby("cycle")[column].sum()
            metrics[f"{column}_sum"] = metrics["cycle"].map(values).to_numpy(float)
    return metrics


def summarize_setpoint_schedule(
    setpoint_values: np.ndarray,
    set_points_len: int,
    test_cycle: int,
) -> pd.DataFrame:
    cycles = np.arange(len(setpoint_values), dtype=int)
    start_steps = cycles * int(set_points_len)
    end_steps = start_steps + int(set_points_len) - 1
    return pd.DataFrame(
        {
            "cycle": cycles,
            "start_step": start_steps,
            "end_step": end_steps,
            "target_ph": np.asarray(setpoint_values, dtype=float),
            "is_test": cycles == int(test_cycle),
        }
    )


def summarize_run(
    trajectory: pd.DataFrame,
    agent: TD3Agent,
    args: argparse.Namespace,
    total_steps: int,
    n_setpoints: int,
    set_points_len: int,
    warm_start_steps: int,
    target_ph_min: float,
    target_ph_max: float,
    setpoint_metadata: dict,
    reward_config: PHRewardConfig,
    env: PHEnvironment,
) -> pd.DataFrame:
    test_rows = trajectory[trajectory["is_test"]]
    eval_rows = test_rows if not test_rows.empty else trajectory
    return pd.DataFrame(
        [
            {
                "total_steps": int(total_steps),
                "setpoint_cycles": int(n_setpoints),
                "steps_per_cycle": int(set_points_len),
                "setpoint_strategy": str(args.setpoint_strategy),
                "setpoint_source": str(setpoint_metadata["setpoint_source"]),
                "setpoint_min": float(target_ph_min),
                "setpoint_max": float(target_ph_max),
                "desired_setpoint_min": float(
                    setpoint_metadata["desired_setpoint_min"]
                ),
                "desired_setpoint_max": float(
                    setpoint_metadata["desired_setpoint_max"]
                ),
                "setpoint_range_was_clipped": bool(
                    setpoint_metadata["range_was_clipped"]
                ),
                "warm_start_steps": int(warm_start_steps),
                "td3_train_steps": int(agent.train_steps),
                "batch_size": int(args.batch_size),
                "overall_mae": float(np.mean(np.abs(trajectory["ph_error"]))),
                "overall_rmse": float(
                    np.sqrt(np.mean(np.square(trajectory["ph_error"])))
                ),
                "eval_mae": float(np.mean(np.abs(eval_rows["ph_error"]))),
                "eval_rmse": float(np.sqrt(np.mean(np.square(eval_rows["ph_error"])))),
                "overall_squared_error_cost": float(
                    trajectory["reward_squared_error_cost"].sum()
                ),
                "overall_absolute_error_cost": float(
                    trajectory["reward_absolute_error_cost"].sum()
                ),
                "overall_move_cost": float(trajectory["reward_move_cost"].sum()),
                "overall_sum_move_cost": float(
                    trajectory["reward_sum_move_cost"].sum()
                ),
                "mean_exploration_sigma": float(
                    trajectory["exploration_sigma"].mean()
                ),
                "mean_exploration_magnitude": float(
                    trajectory["exploration_magnitude"].mean()
                ),
                "mean_action_saturation_fraction": float(
                    trajectory["action_saturation_fraction"].mean()
                ),
                "fixed_buffer_flow_sum": float(args.fixed_buffer_flow_sum),
                "buffer_flow_sum_min": float(args.buffer_flow_sum_min),
                "buffer_flow_sum_max": float(args.buffer_flow_sum_max),
                "fixed_water_flow": float(env.fixed_water_flow),
                "action_mode": str(args.action_mode),
                "rl_state_dimension": int(env.observation_space.shape[0]),
                "rl_action_dimension": int(env.action_space.shape[0]),
                "reward_mode": reward_config.mode,
                "reward_squared_weight": float(args.reward_squared_weight),
                "reward_absolute_weight": float(args.reward_absolute_weight),
                "move_penalty_weight": float(args.move_penalty_weight),
                "sum_move_penalty_weight": float(args.sum_move_penalty_weight),
                "reward_band_floor_ph": float(args.reward_band_floor_ph),
                "reward_bonus_weight": float(reward_config.bonus_weight_abs),
                "reward_bonus_k": float(reward_config.bonus_k),
                "reward_tail_offset_weight": float(args.reward_tail_offset_weight),
                "reward_definition": reward_definition_text(reward_config),
                "plant_model": "ideal Henderson-Hasselbalch",
            }
        ]
    )


def write_config_snapshot(
    output_dir: Path,
    args: argparse.Namespace,
    process_config: PHProcessConfig,
    total_steps: int,
    n_setpoints: int,
    set_points_len: int,
    warm_start_steps: int,
    reward_config: PHRewardConfig,
    env: PHEnvironment,
    target_ph_min: float,
    target_ph_max: float,
    setpoint_metadata: dict,
) -> dict:
    snapshot = {
        "runner": "run_offline_ph_td3_training.py",
        "simulation_only": True,
        "uses_biosmb_or_emulator": False,
        "process_config": process_config.__dict__,
        "resolved_rollout": {
            "total_steps": int(total_steps),
            "setpoint_cycles": int(n_setpoints),
            "steps_per_cycle": int(set_points_len),
            "setpoint_strategy": str(args.setpoint_strategy),
            "setpoint_source": str(setpoint_metadata["setpoint_source"]),
            "setpoint_range_source": str(args.setpoint_range_source),
            "setpoint_data_path": str(args.setpoint_data_path),
            "setpoint_column": str(args.setpoint_column),
            "desired_setpoint_min": float(setpoint_metadata["desired_setpoint_min"]),
            "desired_setpoint_max": float(setpoint_metadata["desired_setpoint_max"]),
            "desired_setpoint_count": setpoint_metadata["desired_setpoint_count"],
            "reachable_setpoint_min": float(
                setpoint_metadata["reachable_setpoint_min"]
            ),
            "reachable_setpoint_max": float(
                setpoint_metadata["reachable_setpoint_max"]
            ),
            "setpoint_min": float(target_ph_min),
            "setpoint_max": float(target_ph_max),
            "setpoint_range_was_clipped": bool(
                setpoint_metadata["range_was_clipped"]
            ),
            "warm_start_steps": int(warm_start_steps),
            "evaluation_cycle": int(n_setpoints - 1),
            "offline_training_protocol": "direct_td3_no_warm_start"
            if warm_start_steps == 0
            else "legacy_hh_warm_start_then_td3",
            "rl_state_dimension": int(env.observation_space.shape[0]),
            "rl_action_dimension": int(env.action_space.shape[0]),
            "rl_state_variables": [
                "current_ph",
                "target_ph",
                "current_ph_minus_target_ph",
                "normalized_ratio_action",
            ]
            + (
                ["normalized_buffer_sum_action"]
                if args.action_mode == "ratio_buffer_sum"
                else []
            ),
            "rl_action_variables": ["acetate_acid_ratio"]
            + (
                ["acid_acetate_total_flow"]
                if args.action_mode == "ratio_buffer_sum"
                else []
            ),
            "action_mode": str(args.action_mode),
            "fixed_buffer_flow_sum": float(args.fixed_buffer_flow_sum),
            "buffer_flow_sum_min": float(args.buffer_flow_sum_min),
            "buffer_flow_sum_max": float(args.buffer_flow_sum_max),
            "fixed_water_flow": float(env.fixed_water_flow),
            "reward_config": reward_config.to_dict(),
            "reward_definition": reward_definition_text(reward_config),
            "reward_mode": reward_config.mode,
            "reward_squared_weight": float(args.reward_squared_weight),
            "reward_absolute_weight": float(args.reward_absolute_weight),
            "move_penalty_weight": float(args.move_penalty_weight),
            "sum_move_penalty_weight": float(args.sum_move_penalty_weight),
            "reward_band_floor_ph": float(args.reward_band_floor_ph),
            "reward_bonus_weight": float(reward_config.bonus_weight_abs),
            "reward_bonus_k": float(reward_config.bonus_k),
            "reward_tail_offset_weight": float(args.reward_tail_offset_weight),
            "exploration_mode": "gaussian",
            "exploration_std_start": float(args.std_start),
            "exploration_std_end": float(args.std_end),
            "exploration_std_decay_steps": int(args.std_decay_steps),
            "exploration_std_decay_mode": str(args.std_decay_mode),
            "exploration_std_decay_rate": float(args.std_decay_rate),
        },
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
    }
    with open(output_dir / "tables" / "config_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a repo-style offline TD3 simulation for the ideal-HH pH plant."
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--total-steps", type=int, default=500_000)
    parser.add_argument("--n-tests", type=int, default=None)
    parser.add_argument("--set-points-len", type=int, default=None)
    parser.add_argument(
        "--setpoint-strategy",
        choices=["admissible_random", "legacy_fixed"],
        default="admissible_random",
        help=(
            "How to choose setpoints. admissible_random draws seeded stratified "
            "targets from the resolved target-pH range."
        ),
    )
    parser.add_argument(
        "--setpoint-range-source",
        choices=["lab_data", "reachable"],
        default="lab_data",
        help=(
            "Source for the desired target-pH range. lab_data uses the min/max "
            "of the configured setpoint CSV column, intersected with reachable "
            "simulator bounds."
        ),
    )
    parser.add_argument(
        "--setpoint-data-path",
        type=Path,
        default=DEFAULT_SETPOINT_DATA_PATH,
        help="CSV used when --setpoint-range-source lab_data is selected.",
    )
    parser.add_argument(
        "--setpoint-column",
        default=DEFAULT_SETPOINT_COLUMN,
        help="Column containing desired pH setpoints in the setpoint data CSV.",
    )
    parser.add_argument("--warm-start-cycles", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--buffer-size", type=int, default=60_000)
    parser.add_argument("--actor-hidden", type=parse_hidden_layers, default=[128, 128])
    parser.add_argument("--critic-hidden", type=parse_hidden_layers, default=[128, 128])
    parser.add_argument("--actor-lr", type=float, default=1e-4)
    parser.add_argument("--critic-lr", type=float, default=1e-3)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--std-start", type=float, default=0.35)
    parser.add_argument("--std-end", type=float, default=0.01)
    parser.add_argument("--std-decay-steps", type=int, default=5000)
    parser.add_argument(
        "--std-decay-mode",
        choices=["linear", "exp", "cosine"],
        default="linear",
    )
    parser.add_argument("--std-decay-rate", type=float, default=0.99)
    parser.add_argument("--reward-squared-weight", type=float, default=1.0)
    parser.add_argument("--reward-absolute-weight", type=float, default=1.0)
    parser.add_argument(
        "--move-penalty-weight",
        type=float,
        default=0.0,
        help="Weight on normalized action movement. Defaults to zero for steady-state tracking.",
    )
    parser.add_argument(
        "--sum-move-penalty-weight",
        type=float,
        default=5.0,
        help=(
            "Weight on ((acid+acetate sum change)/(sum range))^2. "
            "This is the MPC-like move penalty used by the variable-sum action."
        ),
    )
    parser.add_argument(
        "--reward-mode",
        choices=["three_term", "relative_band", "relative_band_offset"],
        default="relative_band_offset",
        help=(
            "Reward used by the offline pH simulation. The default is the "
            "offset-focused relative-band shaped reward."
        ),
    )
    parser.add_argument("--reward-band-floor-ph", type=float, default=0.01)
    parser.add_argument(
        "--reward-bonus-weight",
        type=float,
        default=0.05,
        help=(
            "Absolute reward-unit weight on the relative-band near-setpoint "
            "bonus. Larger values make zero and near-zero pH offset more attractive."
        ),
    )
    parser.add_argument(
        "--reward-bonus-k",
        type=float,
        default=6.0,
        help="Sharpness of the exponential near-setpoint bonus shape.",
    )
    parser.add_argument("--reward-tail-offset-weight", type=float, default=0.0)
    parser.add_argument(
        "--action-mode",
        choices=["ratio", "ratio_buffer_sum"],
        default="ratio_buffer_sum",
        help=(
            "ratio uses the legacy one-action fixed-sum setup. "
            "ratio_buffer_sum lets TD3 choose ratio and acid+acetate total flow."
        ),
    )
    parser.add_argument(
        "--fixed-buffer-flow-sum",
        type=float,
        default=15.0,
        help=(
            "Acid+acetate sum in ratio-only mode, and nominal/default sum in "
            "ratio_buffer_sum mode."
        ),
    )
    parser.add_argument("--buffer-flow-sum-min", type=float, default=2.0)
    parser.add_argument("--buffer-flow-sum-max", type=float, default=20.0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--save-checkpoint", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
