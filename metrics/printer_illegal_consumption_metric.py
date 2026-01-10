from __future__ import annotations

from typing import List, Optional, Tuple

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class PrinterIllegalConsumptionMetric(BaseMetric):
    """
    Penalty when toner/paper decreases even though the printer is not ON.
    This catches classes of bugs where resources are consumed while the device is OFF.
    """

    def __init__(self, penalty_per_tick: float = 1.0):
        super().__init__(
            name="printer_illegal_consumption",
            description="Penalty when toner/paper decreases while the printer is not ON",
        )
        self.penalty_per_tick = penalty_per_tick

    def calculate(self, snapshots: List[EnvironmentSnapshot], subject: Subject) -> MetricScore:
        if len(snapshots) < 2:
            return MetricScore(self.name, subject, 0.0, 0.0, {"error": "Not enough snapshots"})

        if subject.kind != SubjectKind.PRINTER:
            return MetricScore(self.name, subject, 0.0, 0.0, {"skipped": "Metric applies only to printers"})

        total_penalty = 0.0
        ticks = 0
        examples: list[dict] = []

        prev_levels: Optional[Tuple[int, int]] = None
        prev_state: Optional[str] = None

        for s in snapshots:
            room = next(
                (r for r in s.rooms if r.printer and r.printer.printer_id == subject.subject_id),
                None,
            )
            if not room or not room.printer:
                continue

            p = room.printer
            cur_levels = (p.toner_level, p.paper_level)
            if prev_levels is not None:
                toner_down = cur_levels[0] < prev_levels[0]
                paper_down = cur_levels[1] < prev_levels[1]
                if (toner_down or paper_down) and p.state != "ON":
                    ticks += 1
                    total_penalty += self.penalty_per_tick
                    if len(examples) < 5:
                        examples.append(
                            {
                                "timestamp": s.simulation_time.isoformat(),
                                "room": room.room_name,
                                "printer_state": p.state,
                                "prev_toner": prev_levels[0],
                                "prev_paper": prev_levels[1],
                                "toner": cur_levels[0],
                                "paper": cur_levels[1],
                            }
                        )

            prev_levels = cur_levels
            prev_state = p.state

        dur_min = sim_duration_minutes(snapshots)
        avg = (total_penalty / dur_min) if dur_min > 0 else total_penalty
        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg,
            details={"illegal_ticks": ticks, "examples": examples, "sim_duration_minutes": dur_min},
        )


