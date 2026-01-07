from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from collectors.environment_collector import EnvironmentCollector
from evaluation.utils import sim_duration_minutes
from metrics.base_metric import BaseMetric
from models.data_models import (
    EnvironmentSnapshot,
    MetricScore,
    RunResult,
    Subject,
    SubjectKind,
    SubjectResult,
)
from subjects.detector import detect_active_subjects

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricSet:
    kind: SubjectKind
    metrics: List[BaseMetric]


class EvaluationRunner:
    def __init__(self, simulator_url: str):
        self.collector = EnvironmentCollector(simulator_url)

    async def close(self) -> None:
        await self.collector.close()

    async def collect_snapshots(
        self,
        duration_seconds: int,
        collection_interval_seconds: float,
    ) -> List[EnvironmentSnapshot]:
        snapshots: List[EnvironmentSnapshot] = []
        end_time = datetime.now() + timedelta(seconds=duration_seconds)

        while datetime.now() < end_time:
            snap = await self.collector.collect_snapshot()
            if snap:
                snapshots.append(snap)
            await asyncio.sleep(collection_interval_seconds)

        return snapshots

    def evaluate(
        self,
        test_name: str,
        snapshots: List[EnvironmentSnapshot],
        metric_sets: List[MetricSet],
        subjects: Optional[List[Subject]] = None,
    ) -> RunResult:
        start = datetime.now()
        subjects_final = subjects or detect_active_subjects(snapshots)

        metrics_by_kind: Dict[SubjectKind, List[BaseMetric]] = {
            ms.kind: ms.metrics for ms in metric_sets
        }

        dur_min = sim_duration_minutes(snapshots)
        subject_results: List[SubjectResult] = []

        for subj in subjects_final:
            metric_list = metrics_by_kind.get(subj.kind, [])
            metric_scores: List[MetricScore] = []
            for metric in metric_list:
                metric_scores.append(metric.calculate(snapshots, subj))

            penalty_total = sum(ms.penalty_total for ms in metric_scores)
            penalty_avg = (penalty_total / dur_min) if dur_min > 0 else penalty_total

            subject_results.append(
                SubjectResult(
                    subject=subj,
                    metrics=metric_scores,
                    penalty_total=penalty_total,
                    penalty_avg_per_sim_minute=penalty_avg,
                    details={"sim_duration_minutes": dur_min},
                )
            )

        end = datetime.now()
        return RunResult(
            test_name=test_name,
            start_time=start,
            end_time=end,
            snapshots_collected=len(snapshots),
            subjects=subject_results,
            summary={
                "subjects_count": len(subject_results),
                "sim_duration_minutes": dur_min,
            },
        )


