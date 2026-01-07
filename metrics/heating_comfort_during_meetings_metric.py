from typing import List

from evaluation.utils import sim_duration_minutes
from models.data_models import EnvironmentSnapshot, MetricScore, Meeting, Subject, SubjectKind
from metrics.base_metric import BaseMetric


class HeatingComfortDuringMeetingsMetric(BaseMetric):
    """
    Ocena komfortu: podczas spotkań temperatura w pokoju powinna być >= comfort_min_c.

    Punktacja (v2):
    - kara per tick (snapshot) w trakcie spotkania, gdy temperatura < comfort_min_c
    - wynik raportowany jako penalty_total oraz penalty_avg_per_sim_minute
    """

    def __init__(
        self,
        comfort_min_c: float = 21.0,
        penalty_per_meeting: float = 0.0,  # legacy; v2 preferuje per-tick
        penalty_per_tick: float = 1.0,
    ):
        super().__init__(
            name="heating_comfort_during_meetings",
            description="Sprawdza czy temperatura podczas spotkań jest >= zadany próg komfortu",
        )
        self.comfort_min_c = comfort_min_c
        self.penalty_per_meeting = penalty_per_meeting
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

        all_meetings = self._extract_all_meetings(snapshots)
        if not all_meetings:
            return MetricScore(
                metric_name=self.name,
                subject=subject,
                penalty_total=0.0,
                penalty_avg_per_sim_minute=0.0,
                details={"message": "No meetings found during test period"},
            )

        violations = []
        total_penalty = 0.0

        for meeting in all_meetings:
            meeting_violations = self._check_meeting_temperature(meeting, snapshots)
            if meeting_violations:
                violations.append(
                    {
                        "meeting": {
                            "title": meeting.title,
                            "room": meeting.room_name,
                            "start": meeting.start_time.isoformat(),
                            "end": meeting.end_time.isoformat(),
                        },
                        "violations": meeting_violations,
                    }
                )
                total_penalty += len(meeting_violations) * self.penalty_per_tick

        dur_min = sim_duration_minutes(snapshots)
        avg_per_min = (total_penalty / dur_min) if dur_min > 0 else total_penalty

        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=avg_per_min,
            details={
                "comfort_min_c": self.comfort_min_c,
                "total_meetings": len(all_meetings),
                "meetings_with_violations": len(violations),
                "violations": violations,
                "sim_duration_minutes": dur_min,
            },
        )

    def _extract_all_meetings(self, snapshots: List[EnvironmentSnapshot]) -> List[Meeting]:
        meetings_by_id: dict[str, Meeting] = {}
        for snapshot in snapshots:
            for room in snapshot.rooms:
                for meeting in room.meetings:
                    meeting_key = f"{meeting.room_id}_{meeting.start_time}_{meeting.end_time}"
                    if meeting_key not in meetings_by_id:
                        meetings_by_id[meeting_key] = meeting
        return list(meetings_by_id.values())

    def _check_meeting_temperature(
        self, meeting: Meeting, snapshots: List[EnvironmentSnapshot]
    ) -> List[dict]:
        violations: List[dict] = []

        relevant_snapshots = [
            s for s in snapshots if meeting.start_time <= s.simulation_time <= meeting.end_time
        ]
        if not relevant_snapshots:
            return violations

        for snapshot in relevant_snapshots:
            room = next((r for r in snapshot.rooms if r.room_id == meeting.room_id), None)
            if not room:
                continue

            if room.temperature_c < self.comfort_min_c:
                violations.append(
                    {
                        "timestamp": snapshot.simulation_time.isoformat(),
                        "room": room.room_name,
                        "issue": "Temperature below comfort threshold during meeting",
                        "temperature_c": room.temperature_c,
                        "comfort_min_c": self.comfort_min_c,
                    }
                )

        return violations


