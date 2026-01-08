from typing import List
from models.data_models import (
    EnvironmentSnapshot,
    MetricScore,
    Meeting,
    LightState,
)
from metrics.base_metric import BaseMetric


class LightsDuringMeetingsMetric(BaseMetric):
    def __init__(
        self,
        penalty_per_meeting: float = 10.0,
        penalty_per_minute: float = 1.0,
    ):
        super().__init__(
            name="lights_during_meetings",
            description="Checks whether lights are turned on during meetings (legacy metric)",
        )
        self.penalty_per_meeting = penalty_per_meeting
        self.penalty_per_minute = penalty_per_minute

    def calculate(
        self,
        snapshots: List[EnvironmentSnapshot],
        subject,
    ) -> MetricScore:
        # Legacy metric kept for reference; not used in v2 auto mode.
        if not snapshots:
            return MetricScore(self.name, subject, 0.0, 0.0, {"error": "No snapshots provided"})

        all_meetings = self._extract_all_meetings(snapshots)
        if not all_meetings:
            return MetricScore(self.name, subject, 0.0, 0.0, {"message": "No meetings found"})

        violations = []
        total_penalty = 0.0

        for meeting in all_meetings:
            meeting_violations = self._check_meeting_lights(meeting, snapshots)
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
                total_penalty += self.penalty_per_meeting
                total_penalty += len(meeting_violations) * self.penalty_per_minute

        return MetricScore(
            metric_name=self.name,
            subject=subject,
            penalty_total=total_penalty,
            penalty_avg_per_sim_minute=0.0,
            details={
                "legacy": True,
                "total_meetings": len(all_meetings),
                "meetings_with_violations": len(violations),
                "violations": violations,
            },
        )

    def _extract_all_meetings(
        self, snapshots: List[EnvironmentSnapshot]
    ) -> List[Meeting]:
        meetings_by_id: dict[str, Meeting] = {}

        for snapshot in snapshots:
            for room in snapshot.rooms:
                for meeting in room.meetings:
                    meeting_key = f"{meeting.room_id}_{meeting.start_time}_{meeting.end_time}"
                    if meeting_key not in meetings_by_id:
                        meetings_by_id[meeting_key] = meeting

        return list(meetings_by_id.values())

    def _check_meeting_lights(
        self, meeting: Meeting, snapshots: List[EnvironmentSnapshot]
    ) -> List[dict]:
        violations = []

        relevant_snapshots = [
            s
            for s in snapshots
            if meeting.start_time <= s.simulation_time <= meeting.end_time
        ]

        if not relevant_snapshots:
            return violations

        for snapshot in relevant_snapshots:
            room = next(
                (r for r in snapshot.rooms if r.room_id == meeting.room_id), None
            )
            if not room:
                continue

            all_lights_off = all(light.state != "ON" for light in room.lights)
            if all_lights_off and room.lights:
                violations.append(
                    {
                        "timestamp": snapshot.simulation_time.isoformat(),
                        "room": room.room_name,
                        "issue": "All lights are OFF during meeting",
                        "lights_count": len(room.lights),
                    }
                )

        return violations

