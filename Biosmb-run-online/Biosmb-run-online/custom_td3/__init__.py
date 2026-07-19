"""Custom TD3 deployment and active online-training components."""

from .agent import GaussianNoiseSchedule, TD3Agent, set_global_seeds
from .critic import Critic

from .contracts import (
    ACTION_VARIABLES,
    STATE_VARIABLES,
    FlowMapping,
    LogicalFlows,
    RatioSumActionMapper,
    TD3ContractError,
    build_td3_state,
    format_biosmb_action,
)
from .controller import BioSMBTD3Policy
from .online_training import BioSMBOnlineTD3Trainer
from .policy import TD3Policy, TD3PolicyLoadError, sha256_file
from .replay_buffer import PERRecentReplayBuffer
from .reward import (
    PHRewardBreakdown,
    PHRewardConfig,
    compute_ph_reward,
    reward_definition_text,
)
from .runtime_modes import (
    RuntimeModeError,
    ScheduledSetpointManager,
    select_frozen_action,
    validate_target_ph,
)

__all__ = [
    "ACTION_VARIABLES",
    "STATE_VARIABLES",
    "BioSMBTD3Policy",
    "BioSMBOnlineTD3Trainer",
    "Critic",
    "FlowMapping",
    "GaussianNoiseSchedule",
    "LogicalFlows",
    "PERRecentReplayBuffer",
    "PHRewardBreakdown",
    "PHRewardConfig",
    "RatioSumActionMapper",
    "RuntimeModeError",
    "ScheduledSetpointManager",
    "TD3Agent",
    "TD3ContractError",
    "TD3Policy",
    "TD3PolicyLoadError",
    "build_td3_state",
    "compute_ph_reward",
    "format_biosmb_action",
    "reward_definition_text",
    "select_frozen_action",
    "set_global_seeds",
    "sha256_file",
    "validate_target_ph",
]
