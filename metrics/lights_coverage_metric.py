from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class LightsCoverageMetric(BaseMetric):
    """
    Coverage metric based on illumination (lux):
    penalty when a room is active (meeting OR people present) but illumination is below a threshold.

    This avoids penalizing rooms that are sufficiently lit by daylight (even if lights are OFF).
    """

    def __init__(self, min_illumination_lux: float = 300.0, penalty_per_tick: float = 1.0):
        super().__init__(
            name="lights_coverage",
            description="Penalty when a room is active (meeting/people) but illumination is below a minimum threshold",
        )
        self.min_illumination_lux = min_illumination_lux
        self.penalty_per_tick = penalty_per_tick

    def calculate(self, snapshots: List[EnvironmentSnapshot], subject: Subject) -> MetricScore:
        if not snapshots:
            return MetricScore(self.name, subject, 0.0, 0.0, {"error": "No snapshots"})

        if subject.kind != SubjectKind.LIGHTS or not subject.room_id:
            return MetricScore(self.name, subject, 0.0, 0.0, {"skipped": "Metric applies only to room lights"})

        total_penalty = 0.0
        ticks = 0
        examples: list[dict] = []

        for s in snapshots:
            room = next((r for r in s.rooms if r.room_id == subject.room_id), None)
            if not room:
                continue

            meeting_now = any(m.start_time <= s.simulation_time <= m.end_time for m in room.meetings)
            active = meeting_now or room.people_count > 0

            # Don't penalize during a power outage (lights may be unavailable).
            if s.power_outage:
                continue

            if active and room.illumination_lux < self.min_illumination_lux:
                ticks += 1
                total_penalty += self.penalty_per_tick
                if len(examples) < 5:
                    examples.append(
                        {
                            "room": room.room_name,
                            "room_id": room.room_id,
                            "timestamp": s.simulation_time.isoformat(),
                            "illumination_lux": room.illumination_lux,
                            "min_illumination_lux": self.min_illumination_lux,
                            "people_count": room.people_count,
                            "meeting_now": meeting_now,
                            "lights_on": [l.light_id for l in room.lights if l.state == "ON"],
                        }
                    )

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={
                "min_illumination_lux": self.min_illumination_lux,
                "violation_ticks": ticks,
                "examples": examples,
                "sim_duration_minutes": dur_min,
            },
        )


