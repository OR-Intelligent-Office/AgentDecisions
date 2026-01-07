from models.data_models import RunResult, SubjectResult, MetricScore


class ConsoleReporter:
    def print_run(self, run: RunResult) -> None:
        print("\n" + "=" * 80)
        print(f"TEST: {run.test_name}")
        print("=" * 80)
        print(f"Start Time: {run.start_time.isoformat()}")
        print(f"End Time: {run.end_time.isoformat()}")
        print(f"Snapshots Collected: {run.snapshots_collected}")
        print(f"Subjects Detected: {run.summary.get('subjects_count', 0)}")
        if "sim_duration_minutes" in run.summary:
            print(f"Sim duration: {run.summary.get('sim_duration_minutes'):.2f} min")
        print()
        print("=" * 80)
        print()

    def print_subject(self, result: SubjectResult) -> None:
        subj = result.subject
        print("-" * 80)
        print(f"SUBJECT: {subj.kind.value} :: {subj.subject_id}")
        if subj.room_name:
            print(f"ROOM: {subj.room_name} ({subj.room_id})")
        print(f"penalty_total: {result.penalty_total:.2f}")
        print(f"penalty_avg_per_sim_minute: {result.penalty_avg_per_sim_minute:.4f}")
        for metric in result.metrics:
            self._print_metric(metric)
        print()

    def _print_metric(self, score: MetricScore) -> None:
        print(f"  METRIC: {score.metric_name}")
        print(f"    penalty_total: {score.penalty_total:.2f}")
        print(f"    penalty_avg_per_sim_minute: {score.penalty_avg_per_sim_minute:.4f}")

