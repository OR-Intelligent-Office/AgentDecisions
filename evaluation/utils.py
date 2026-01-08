from __future__ import annotations

from typing import List

from models.data_models import EnvironmentSnapshot


def sim_duration_minutes(snapshots: List[EnvironmentSnapshot]) -> float:
    """
    Simulation duration (based on EnvironmentState.simulationTime), in minutes.
    Used to normalize penalties: penalty_avg_per_sim_minute.
    """
    if len(snapshots) < 2:
        return 0.0
    start = snapshots[0].simulation_time
    end = snapshots[-1].simulation_time
    delta = end - start
    return max(0.0, delta.total_seconds() / 60.0)


