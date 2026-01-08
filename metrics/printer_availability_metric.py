from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class PrinterAvailabilityMetric(BaseMetric):
    """
    Penalty when the room is active (people or meeting), the printer has resources (>0),
    there is no power outage, and the printer is still not ON.
    """

    def __init__(self, penalty_per_tick: float = 1.0):
        super().__init__(
            name="printer_availability",
            description="Penalty when printer is OFF during activity (people/meeting) despite having resources",
        )
        self.penalty_per_tick = penalty_per_tick

    def calculate(self, snapshots: List[EnvironmentSnapshot], subject: Subject) -> MetricScore:
        if not snapshots:
            return MetricScore(self.name, subject, 0.0, 0.0, {"error": "No snapshots"})

        if subject.kind != SubjectKind.PRINTER:
            return MetricScore(self.name, subject, 0.0, 0.0, {"skipped": "Metric applies only to printers"})

        total_penalty = 0.0
        ticks = 0

        for s in snapshots:
            room = next(
                (r for r in s.rooms if r.printer and r.printer.printer_id == subject.subject_id),
                None,
            )
            if not room or not room.printer:
                continue

            p = room.printer
            has_resources = p.toner_level > 0 and p.paper_level > 0
            meeting_now = any(m.start_time <= s.simulation_time <= m.end_time for m in room.meetings)
            should_be_on = (room.people_count > 0 or meeting_now) and has_resources and not s.power_outage

            if should_be_on and p.state != "ON":
                ticks += 1
                total_penalty += self.penalty_per_tick

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={"violation_ticks": ticks, "sim_duration_minutes": dur_min},
        )


