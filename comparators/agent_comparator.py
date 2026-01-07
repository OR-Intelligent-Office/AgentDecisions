import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from models.data_models import (
    EnvironmentSnapshot,
    AgentType,
    ComparisonResult,
    MetricScore,
)
from metrics.base_metric import BaseMetric
from collectors.environment_collector import EnvironmentCollector

logger = logging.getLogger(__name__)


class AgentComparator:
    def __init__(
        self,
        simulator_url: str = "http://localhost:8080",
        metrics: Optional[List[BaseMetric]] = None,
    ):
        self.collector = EnvironmentCollector(simulator_url)
        self.metrics = metrics or []

    async def run_comparison(
        self,
        test_name: str,
        agent_type: AgentType,
        start_time: datetime,
        duration_seconds: int,
        collection_interval_seconds: float = 2.0,
        agent_name: Optional[str] = None,
    ) -> ComparisonResult:
        logger.info(
            f"Starting comparison test '{test_name}' for {agent_type.value} agent"
        )
        logger.info(
            f"Duration: {duration_seconds}s, Collection interval: {collection_interval_seconds}s"
        )

        snapshots: List[EnvironmentSnapshot] = []
        end_time = start_time + timedelta(seconds=duration_seconds)

        try:
            while datetime.now() < end_time:
                snapshot = await self.collector.collect_snapshot()
                if snapshot:
                    snapshots.append(snapshot)
                    logger.debug(
                        f"Collected snapshot at {snapshot.simulation_time.isoformat()}"
                    )
                await asyncio.sleep(collection_interval_seconds)
        except Exception as e:
            logger.error(f"Error during data collection: {e}")

        logger.info(f"Collected {len(snapshots)} snapshots")

        scores: List[MetricScore] = []
        for metric in self.metrics:
            try:
                score = metric.calculate(snapshots, agent_type)
                scores.append(score)
                logger.info(
                    f"Metric '{metric.name}': score={score.score:.2f}, penalty={score.penalty_points:.2f}"
                )
            except Exception as e:
                logger.error(f"Error calculating metric '{metric.name}': {e}")

        total_score = sum(score.score for score in scores)
        total_penalty = sum(score.penalty_points for score in scores)

        return ComparisonResult(
            test_name=test_name,
            start_time=start_time,
            end_time=datetime.now(),
            agent_type=agent_type,
            agent_name=agent_name,
            scores=scores,
            total_score=total_score,
            total_penalty=total_penalty,
            summary={
                "snapshots_collected": len(snapshots),
                "metrics_count": len(scores),
                "average_score": total_score / len(scores) if scores else 0.0,
            },
        )

    async def close(self):
        await self.collector.close()

