from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class BlindsDaylightMetric(BaseMetric):
    """
    Prosta metryka "sensowne rolety" na podstawie daylightIntensity:
    - jeśli daylightIntensity >= open_threshold i w pokoju są osoby lub spotkanie -> rolety powinny być OPEN
    - jeśli daylightIntensity <= close_threshold i brak osób i brak spotkania -> rolety powinny być CLOSED
    """

    def __init__(
        self,
        open_threshold: float = 0.6,
        close_threshold: float = 0.3,
        penalty_per_tick: float = 0.5,
    ):
        super().__init__(
            name="blinds_daylight",
            description="Kara za rolety niezgodne z prostą heurystyką na podstawie daylightIntensity i aktywności",
        )
        self.open_threshold = open_threshold
        self.close_threshold = close_threshold
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

            if s.daylight_intensity >= self.open_threshold and active:
                if room.blinds.state != "OPEN":
                    ticks += 1
                    total_penalty += self.penalty_per_tick
            if s.daylight_intensity <= self.close_threshold and (not active):
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
                "open_threshold": self.open_threshold,
                "close_threshold": self.close_threshold,
                "violation_ticks": ticks,
                "sim_duration_minutes": dur_min,
            },
        )


