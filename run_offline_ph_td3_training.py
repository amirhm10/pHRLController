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
from simulation.ph_environment import PHEnvironment, PHEnvironmentConfig


DEFAULT_SET_POINTS_LEN = 200


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create piecewise-constant pH targets and cycle indices."""
    if n_tests <= 0:
        raise ValueError("n_tests must be positive.")
    if set_points_len <= 0:
        raise ValueError("set_points_len must be positive.")

    strategy = str(strategy).lower()
    if strategy == "legacy_fixed":
        base_targets = np.array(
            [
                process_config.target_ph_min + 0.10,
                process_config.pKa - 0.35,
                process_config.pKa,
                process_config.pKa + 0.35,
                process_config.target_ph_max - 0.10,
            ],
            dtype=np.float32,
        )
        targets = np.resize(base_targets, n_tests)
    elif strategy == "admissible_random":
        rng = np.random.default_rng(seed)
        edges = np.linspace(
            process_config.target_ph_min,
            process_config.target_ph_max,
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


def create_agent(args: argparse.Namespace) -> TD3Agent:
    return TD3Agent(
        state_dim=6,
        action_dim=2,
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


def reward_definition_text() -> str:
    return (
        "-(q2*(target_pH - pH)^2 + "
        "q1*abs(target_pH - pH) + "
        "r_move*mean((action_t - action_t_minus_1)^2))"
    )


def run_training(args: argparse.Namespace) -> dict[str, Path | pd.DataFrame]:
    set_global_seeds(args.seed)
    process_config = PHProcessConfig()
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
    agent = create_agent(args)

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

        records.append(
            {
                "step": step_idx,
                "cycle": cycle,
                "is_warm_start": bool(is_warm_start),
                "is_test": bool(is_test),
                "action_source": action_source,
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
                "flow_ratio_acetate_acid": float(info["flow_ratio_acetate_acid"]),
                "action_acid": float(np.asarray(action).reshape(-1)[0]),
                "action_acetate": float(np.asarray(action).reshape(-1)[1]),
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
        )
        state = next_state

    trajectory = pd.DataFrame.from_records(records)
    episode_metrics = summarize_by_cycle(trajectory)
    summary = summarize_run(
        trajectory=trajectory,
        agent=agent,
        args=args,
        total_steps=total_steps,
        n_setpoints=n_setpoints,
        set_points_len=set_points_len,
        warm_start_steps=warm_start_steps,
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
    summary.to_csv(output_dir / "tables" / "training_summary.csv", index=False)
    config_snapshot = write_config_snapshot(
        output_dir=output_dir,
        args=args,
        process_config=process_config,
        total_steps=total_steps,
        n_setpoints=n_setpoints,
        set_points_len=set_points_len,
        warm_start_steps=warm_start_steps,
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
        squared_error_cost_sum=("reward_squared_error_cost", "sum"),
        absolute_error_cost_sum=("reward_absolute_error_cost", "sum"),
        move_cost_sum=("reward_move_cost", "sum"),
        total_cost_sum=("reward_total_cost", "sum"),
        train_updates=("train_updated", "sum"),
    )
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
                "mean_exploration_sigma": float(
                    trajectory["exploration_sigma"].mean()
                ),
                "mean_exploration_magnitude": float(
                    trajectory["exploration_magnitude"].mean()
                ),
                "mean_action_saturation_fraction": float(
                    trajectory["action_saturation_fraction"].mean()
                ),
                "reward_squared_weight": float(args.reward_squared_weight),
                "reward_absolute_weight": float(args.reward_absolute_weight),
                "move_penalty_weight": float(args.move_penalty_weight),
                "reward_definition": reward_definition_text(),
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
            "setpoint_source": "seeded_admissible_range",
            "setpoint_min": float(process_config.target_ph_min),
            "setpoint_max": float(process_config.target_ph_max),
            "warm_start_steps": int(warm_start_steps),
            "evaluation_cycle": int(n_setpoints - 1),
            "offline_training_protocol": "direct_td3_no_warm_start"
            if warm_start_steps == 0
            else "legacy_hh_warm_start_then_td3",
            "rl_state_dimension": 6,
            "rl_action_dimension": 2,
            "rl_action_variables": ["acid_flow", "acetate_flow"],
            "fixed_water_flow": float(process_config.default_water_flow),
            "reward_definition": reward_definition_text(),
            "reward_squared_weight": float(args.reward_squared_weight),
            "reward_absolute_weight": float(args.reward_absolute_weight),
            "move_penalty_weight": float(args.move_penalty_weight),
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
    parser.add_argument("--total-steps", type=int, default=25_000)
    parser.add_argument("--n-tests", type=int, default=None)
    parser.add_argument("--set-points-len", type=int, default=None)
    parser.add_argument(
        "--setpoint-strategy",
        choices=["admissible_random", "legacy_fixed"],
        default="admissible_random",
        help=(
            "How to choose setpoints. admissible_random draws seeded stratified "
            "targets from the configured admissible pH range."
        ),
    )
    parser.add_argument("--warm-start-cycles", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--buffer-size", type=int, default=5000)
    parser.add_argument("--actor-hidden", type=parse_hidden_layers, default=[64, 64])
    parser.add_argument("--critic-hidden", type=parse_hidden_layers, default=[64, 64])
    parser.add_argument("--actor-lr", type=float, default=1e-4)
    parser.add_argument("--critic-lr", type=float, default=1e-3)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--std-start", type=float, default=0.35)
    parser.add_argument("--std-end", type=float, default=0.03)
    parser.add_argument("--std-decay-steps", type=int, default=5000)
    parser.add_argument(
        "--std-decay-mode",
        choices=["linear", "exp", "cosine"],
        default="linear",
    )
    parser.add_argument("--std-decay-rate", type=float, default=0.99)
    parser.add_argument("--reward-squared-weight", type=float, default=1.0)
    parser.add_argument("--reward-absolute-weight", type=float, default=1.0)
    parser.add_argument("--move-penalty-weight", type=float, default=0.01)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--save-checkpoint", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
