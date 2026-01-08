from __future__ import annotations

from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class PrinterWasteMetric(BaseMetric):
    """
    Penalty when the printer is ON despite no people and no ongoing meeting.
    """

    def __init__(self, penalty_per_tick: float = 0.5):
        super().__init__(
            name="printer_waste",
            description="Penalty when printer is ON despite no people and no meetings",
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

            meeting_now = any(m.start_time <= s.simulation_time <= m.end_time for m in room.meetings)
            if room.people_count == 0 and not meeting_now and room.printer.state == "ON":
                ticks += 1
                total_penalty += self.penalty_per_tick

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={"waste_ticks": ticks, "sim_duration_minutes": dur_min},
        )


