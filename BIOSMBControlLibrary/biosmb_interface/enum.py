
from enum import Enum


class ValveState(Enum):
    """An enumeration for the state of a valve
    """
    CLOSED = 0
    OPEN = 1


class PumpEnabledState(Enum):
    """An enumeration for the enabled state of a pump
    """
    DISABLED = 0
    ENABLED = 1