from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from TD3Agent.agent import TD3Agent, set_global_seeds
from simulation.config import PHProcessConfig
from simulation.ph_environment import PHEnvironment, PHEnvironmentConfig


def parse_hidden_layers(value: str) -> list[int]:
    layers = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not layers:
        raise argparse.ArgumentTypeError("hidden layer list cannot be empty.")
    return layers


def build_setpoint_schedule(
    process_config: PHProcessConfig,
    n_tests: int,
    set_points_len: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Create piecewise-constant pH targets and cycle indices."""
    if n_tests <= 0:
        raise ValueError("n_tests must be positive.")
    if set_points_len <= 0:
        raise ValueError("set_points_len must be positive.")

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
    schedule = np.repeat(targets, set_points_len).astype(np.float32)
    cycle_indices = np.repeat(np.arange(n_tests), set_points_len)
    return schedule, cycle_indices


def create_agent(args: argparse.Namespace) -> TD3Agent:
    return TD3Agent(
        state_dim=7,
        action_dim=3,
        actor_hidden=args.actor_hidden,
        critic_hidden=args.critic_hidden,
        gamma=args.gamma,
        actor_lr=args.actor_lr,
        critic_lr=args.critic_lr,
        batch_size=args.batch_size,
        buffer_size=args.buffer_size,
        std_start=args.std_start,
        std_end=args.std_end,
        std_decay_steps=args.std_decay_steps,
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


def ph_tracking_reward(ph: float, target_ph: float) -> float:
    return -float((float(ph) - float(target_ph)) ** 2)


def run_training(args: argparse.Namespace) -> dict[str, Path | pd.DataFrame]:
    set_global_seeds(args.seed)
    process_config = PHProcessConfig()
    schedule, cycle_indices = build_setpoint_schedule(
        process_config=process_config,
        n_tests=args.n_tests,
        set_points_len=args.set_points_len,
    )
    total_steps = int(schedule.size)
    warm_start_steps = int(args.warm_start_cycles * args.set_points_len)
    test_cycle = int(args.n_tests - 1)

    env = PHEnvironment(
        PHEnvironmentConfig(
            process_config=process_config,
            target_ph=float(schedule[0]),
            max_episode_steps=total_steps + 1,
            tracking_weight=1.0,
            move_penalty_weight=0.0,
            default_flow_penalty_weight=0.0,
            random_seed=args.seed,
        )
    )
    state, _ = env.reset(
        seed=args.seed,
        options={
            "target_ph": float(schedule[0]),
            "initial_flows": env.target_to_nominal_flows(float(schedule[0])),
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
        elif is_test:
            action = agent.act_eval(state).astype(np.float32)
            action_source = "td3_eval"
        else:
            action = agent.take_action(state, explore=True).astype(np.float32)
            action_source = "td3_explore"

        next_state, _, terminated, truncated, info = env.step(action)
        reward = ph_tracking_reward(info["ph"], target_ph)
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
                "reward": reward,
                "acid_flow": float(info["acid_flow"]),
                "acetate_flow": float(info["acetate_flow"]),
                "water_flow": float(info["water_flow"]),
                "flow_ratio_acetate_acid": float(info["flow_ratio_acetate_acid"]),
                "action_acid": float(np.asarray(action).reshape(-1)[0]),
                "action_acetate": float(np.asarray(action).reshape(-1)[1]),
                "action_water": float(np.asarray(action).reshape(-1)[2]),
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
    summary = summarize_run(trajectory, agent, args, total_steps, warm_start_steps)

    output_dir = make_output_dir(args.output_dir)
    trajectory.to_csv(output_dir / "tables" / "trajectory.csv", index=False)
    episode_metrics.to_csv(output_dir / "tables" / "episode_metrics.csv", index=False)
    summary.to_csv(output_dir / "tables" / "training_summary.csv", index=False)
    write_config_snapshot(output_dir, args, process_config)
    plot_results(trajectory, episode_metrics, output_dir)

    if args.save_checkpoint:
        agent.save(str(output_dir / "checkpoints"), prefix="offline_ph_td3")

    print(f"Saved offline pH TD3 results to: {output_dir}")
    print(summary.to_string(index=False))
    return {
        "output_dir": output_dir,
        "trajectory": trajectory,
        "episode_metrics": episode_metrics,
        "summary": summary,
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
        train_updates=("train_updated", "sum"),
    )
    return metrics


def summarize_run(
    trajectory: pd.DataFrame,
    agent: TD3Agent,
    args: argparse.Namespace,
    total_steps: int,
    warm_start_steps: int,
) -> pd.DataFrame:
    test_rows = trajectory[trajectory["is_test"]]
    eval_rows = test_rows if not test_rows.empty else trajectory
    return pd.DataFrame(
        [
            {
                "total_steps": int(total_steps),
                "warm_start_steps": int(warm_start_steps),
                "td3_train_steps": int(agent.train_steps),
                "batch_size": int(args.batch_size),
                "overall_mae": float(np.mean(np.abs(trajectory["ph_error"]))),
                "overall_rmse": float(
                    np.sqrt(np.mean(np.square(trajectory["ph_error"])))
                ),
                "eval_mae": float(np.mean(np.abs(eval_rows["ph_error"]))),
                "eval_rmse": float(np.sqrt(np.mean(np.square(eval_rows["ph_error"])))),
                "reward_definition": "-(pH - target_pH)^2",
                "plant_model": "ideal Henderson-Hasselbalch",
            }
        ]
    )


def write_config_snapshot(
    output_dir: Path,
    args: argparse.Namespace,
    process_config: PHProcessConfig,
) -> None:
    snapshot = {
        "runner": "run_offline_ph_td3_training.py",
        "simulation_only": True,
        "uses_biosmb_or_emulator": False,
        "process_config": process_config.__dict__,
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
    }
    with open(output_dir / "tables" / "config_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


def plot_results(
    trajectory: pd.DataFrame,
    episode_metrics: pd.DataFrame,
    output_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(trajectory["step"], trajectory["ph"], label="pH", linewidth=1.8)
    ax.step(
        trajectory["step"],
        trajectory["target_ph"],
        where="post",
        label="target pH",
        linewidth=1.5,
        linestyle="--",
    )
    ax.set_xlabel("step")
    ax.set_ylabel("pH")
    ax.set_title("Offline TD3 pH Tracking")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "figures" / "ph_tracking.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(trajectory["step"], trajectory["acid_flow"], label="acid")
    ax.plot(trajectory["step"], trajectory["acetate_flow"], label="acetate")
    ax.plot(trajectory["step"], trajectory["water_flow"], label="water")
    ax.set_xlabel("step")
    ax.set_ylabel("flowrate (mL/min)")
    ax.set_title("TD3 Pump Flow Commands")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "figures" / "flow_commands.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(trajectory["step"], trajectory["reward"], label="step reward")
    ax.plot(
        episode_metrics["cycle"] * max(1, int(trajectory["step"].max() + 1) // len(episode_metrics)),
        episode_metrics["reward_sum"] / episode_metrics["steps"],
        marker="o",
        linestyle="",
        label="cycle mean reward",
    )
    ax.set_xlabel("step")
    ax.set_ylabel("reward")
    ax.set_title("pH Tracking Reward")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "figures" / "reward_trace.png", dpi=180)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a repo-style offline TD3 simulation for the ideal-HH pH plant."
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--n-tests", type=int, default=8)
    parser.add_argument("--set-points-len", type=int, default=25)
    parser.add_argument("--warm-start-cycles", type=int, default=1)
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
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--save-checkpoint", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
