from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class BlindsDaylightMetric(BaseMetric):
    """
    Simple "sensible blinds" metric based on external light (lux):
    - if external_light_lux >= open_threshold_lux and the room is active (people or meeting) -> blinds should be OPEN
    - if external_light_lux <= close_threshold_lux and the room is inactive (no people and no meeting) -> blinds should be CLOSED
    """

    def __init__(
        self,
        open_threshold_lux: float = 6000.0,
        close_threshold_lux: float = 3000.0,
        penalty_per_tick: float = 1.0,
    ):
        super().__init__(
            name="blinds_daylight",
            description="Penalty when blinds state conflicts with a simple daylight/activity heuristic",
        )
        self.open_threshold_lux = open_threshold_lux
        self.close_threshold_lux = close_threshold_lux
        self.penalty_per_tick = penalty_per_tick

    def calculate(self, snapshots: List[EnvironmentSnapshot], subject: Subject) -> MetricScore:
        if not snapshots:
            return MetricScore(self.name, subject, 0.0, 0.0, {"error": "No snapshots"})

        if subject.kind != SubjectKind.BLINDS or not subject.room_id:
            return MetricScore(self.name, subject, 0.0, 0.0, {"skipped": "Metric applies only to blinds"})

        total_penalty = 0.0
        ticks = 0

        for s in snapshots:
            room = next((r for r in s.rooms if r.room_id == subject.room_id), None)
            if not room or not room.blinds:
                continue

            meeting_now = any(m.start_time <= s.simulation_time <= m.end_time for m in room.meetings)
            active = meeting_now or room.people_count > 0

            if s.external_light_lux >= self.open_threshold_lux and active:
                if room.blinds.state != "OPEN":
                    ticks += 1
                    total_penalty += self.penalty_per_tick
            if s.external_light_lux <= self.close_threshold_lux and (not active):
                if room.blinds.state != "CLOSED":
                    ticks += 1
                    total_penalty += self.penalty_per_tick

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={
                "open_threshold_lux": self.open_threshold_lux,
                "close_threshold_lux": self.close_threshold_lux,
                "violation_ticks": ticks,
                "sim_duration_minutes": dur_min,
            },
        )


