from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class LightsWasteMetric(BaseMetric):
    """
    Penalty when there are no people and no ongoing meeting in the room, but any light is ON.
    """

    def __init__(self, penalty_per_tick: float = 1.0):
        super().__init__(
            name="lights_waste",
            description="Penalty when lights are ON despite no people and no meetings",
        )
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
            if room.people_count == 0 and not meeting_now:
                any_on = any(l.state == "ON" for l in room.lights)
                if any_on:
                    ticks += 1
                    total_penalty += self.penalty_per_tick
                    if len(examples) < 5:
                        examples.append(
                            {
                                "room": room.room_name,
                                "room_id": room.room_id,
                                "timestamp": s.simulation_time.isoformat(),
                                "people_count": room.people_count,
                                "meeting_now": meeting_now,
                                "lights_on": [l.light_id for l in room.lights if l.state == "ON"],
                                "illumination_lux": room.illumination_lux,
                            }
                        )

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={"waste_ticks": ticks, "examples": examples, "sim_duration_minutes": dur_min},
        )


