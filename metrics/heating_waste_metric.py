from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class HeatingWasteMetric(BaseMetric):
    """
    Waste/cost metric: penalize situations where heating is ON even though it is not needed
    (based on a simple heuristic).

    "Waste tick" heuristic (thresholds can be adjusted):
    - is_heating == True
    - no people in any room
    - no meeting in any room
    - all rooms have temperature >= min_temp_ok_c

    Each such tick adds penalty_per_tick.
    """

    def __init__(
        self,
        min_temp_ok_c: float = 18.0,
        penalty_per_tick: float = 1.0,
    ):
        super().__init__(
            name="heating_waste",
            description="Penalty for heating while there are no people/meetings and temperature is already sufficient",
        )
        self.min_temp_ok_c = min_temp_ok_c
        self.penalty_per_tick = penalty_per_tick

    def calculate(self, snapshots: List[EnvironmentSnapshot], subject: Subject) -> MetricScore:
        if not snapshots:
            return MetricScore(
                metric_name=self.name,
                subject=subject,
                penalty_total=0.0,
                penalty_avg_per_sim_minute=0.0,
                details={"error": "No snapshots provided"},
            )

        if subject.kind != SubjectKind.HEATING:
            return MetricScore(
                metric_name=self.name,
                subject=subject,
                penalty_total=0.0,
                penalty_avg_per_sim_minute=0.0,
                details={"skipped": "Metric applies only to heating"},
            )

        waste_ticks = []
        total_penalty = 0.0

        for s in snapshots:
            if not s.is_heating:
                continue

            any_people = any(r.people_count > 0 for r in s.rooms)
            any_meeting_now = any(
                any(m.start_time <= s.simulation_time <= m.end_time for m in r.meetings)
                for r in s.rooms
            )
            all_temps_ok = all(r.temperature_c >= self.min_temp_ok_c for r in s.rooms)

            if (not any_people) and (not any_meeting_now) and all_temps_ok:
                waste_ticks.append(
                    {
                        "timestamp": s.simulation_time.isoformat(),
                        "issue": "Heating ON while no people/meetings and temperatures OK",
                    }
                )
                total_penalty += self.penalty_per_tick

        dur_min = sim_duration_minutes(snapshots)
        avg_per_min = (total_penalty / dur_min) if dur_min > 0 else total_penalty

        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg_per_min,
            details={
                "min_temp_ok_c": self.min_temp_ok_c,
                "waste_ticks": len(waste_ticks),
                "examples": waste_ticks[:10],
                "sim_duration_minutes": dur_min,
            },
        )


