#!/usr/bin/env python3
"""
AgentDecisions: analiza decyzji agentów na podstawie stanu OrSimulator.

Nie rozróżniamy "AI vs classic" — oceniamy efekt w środowisku.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set

# Dodaj katalog AgentDecisions do ścieżki
sys.path.insert(0, str(Path(__file__).parent))

from evaluation.evaluator import EvaluationRunner, MetricSet
from metrics.heating_comfort_during_meetings_metric import HeatingComfortDuringMeetingsMetric
from metrics.heating_waste_metric import HeatingWasteMetric
from metrics.lights_coverage_metric import LightsCoverageMetric
from metrics.lights_waste_metric import LightsWasteMetric
from metrics.printer_availability_metric import PrinterAvailabilityMetric
from metrics.printer_waste_metric import PrinterWasteMetric
from metrics.printer_illegal_consumption_metric import PrinterIllegalConsumptionMetric
from metrics.blinds_daylight_metric import BlindsDaylightMetric
from models.data_models import AgentKind, SubjectKind
from orchestrator.process_manager import (
    ManagedProcess,
    ProcessManager,
    default_env,
    kill_process_on_port,
    project_root,
    python_cmd,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_auto(duration_seconds: int, simulator_url: str, collection_interval: float) -> None:
    runner = EvaluationRunner(simulator_url)
    try:
        logger.info(f"Collecting snapshots for {duration_seconds}s (interval={collection_interval}s)...")
        snapshots = await runner.collect_snapshots(
            duration_seconds=duration_seconds,
            collection_interval_seconds=collection_interval,
        )

        metric_sets = [
            MetricSet(
                kind=SubjectKind.HEATING,
                metrics=[
                    HeatingComfortDuringMeetingsMetric(comfort_min_c=21.0, penalty_per_meeting=0.0, penalty_per_tick=1.0),
                    HeatingWasteMetric(min_temp_ok_c=18.0, penalty_per_tick=0.5),
                ],
            ),
            MetricSet(
                kind=SubjectKind.PRINTER,
                metrics=[
                    PrinterAvailabilityMetric(penalty_per_tick=1.0),
                    PrinterWasteMetric(penalty_per_tick=0.5),
                    PrinterIllegalConsumptionMetric(penalty_per_tick=2.0),
                ],
            ),
            MetricSet(
                kind=SubjectKind.LIGHTS,
                metrics=[
                    LightsCoverageMetric(penalty_per_tick=1.0),
                    LightsWasteMetric(penalty_per_tick=0.5),
                ],
            ),
            MetricSet(
                kind=SubjectKind.BLINDS,
                metrics=[
                    BlindsDaylightMetric(open_threshold=0.6, close_threshold=0.3, penalty_per_tick=0.5),
                ],
            ),
        ]

        run = runner.evaluate(
            test_name="auto_active_agents",
            snapshots=snapshots,
            metric_sets=metric_sets,
        )

        print_agent_results(run)
    finally:
        await runner.close()

def build_metric_sets() -> list[MetricSet]:
    return [
        MetricSet(
            kind=SubjectKind.HEATING,
            metrics=[
                HeatingComfortDuringMeetingsMetric(comfort_min_c=21.0, penalty_per_meeting=0.0, penalty_per_tick=1.0),
                HeatingWasteMetric(min_temp_ok_c=18.0, penalty_per_tick=0.5),
            ],
        ),
        MetricSet(
            kind=SubjectKind.PRINTER,
            metrics=[
                PrinterAvailabilityMetric(penalty_per_tick=1.0),
                PrinterWasteMetric(penalty_per_tick=0.5),
                PrinterIllegalConsumptionMetric(penalty_per_tick=2.0),
            ],
        ),
        MetricSet(
            kind=SubjectKind.LIGHTS,
            metrics=[
                LightsCoverageMetric(penalty_per_tick=1.0),
                LightsWasteMetric(penalty_per_tick=0.5),
            ],
        ),
        MetricSet(
            kind=SubjectKind.BLINDS,
            metrics=[
                BlindsDaylightMetric(open_threshold=0.6, close_threshold=0.3, penalty_per_tick=0.5),
            ],
        ),
    ]


def print_metrics_and_criteria() -> None:
    print("METRYKI (kara/min = penalty_avg_per_sim_minute):")
    print("- HeatingAgent: heating_comfort_during_meetings, heating_waste")
    print("- PrinterAgent: printer_availability, printer_waste, printer_illegal_consumption")
    print("- LightAgent: lights_coverage, lights_waste")
    print("- WindowBlindsAgent: blinds_daylight")


def _subject_kind_to_agent_kind(subject_kind: SubjectKind) -> AgentKind:
    """Map SubjectKind to AgentKind."""
    mapping = {
        SubjectKind.HEATING: AgentKind.HEATING,
        SubjectKind.PRINTER: AgentKind.PRINTER,
        SubjectKind.LIGHTS: AgentKind.LIGHT,
        SubjectKind.BLINDS: AgentKind.BLINDS,
    }
    return mapping.get(subject_kind, AgentKind.HEATING)


def aggregate_results_by_agent(run) -> dict[AgentKind, dict]:
    """Aggregate subject results by agent type."""
    aggregated: dict[AgentKind, dict] = {}
    sim_minutes = float(run.summary.get("sim_duration_minutes", 0.0)) or 0.0
    
    for sr in run.subjects:
        agent_kind = _subject_kind_to_agent_kind(sr.subject.kind)
        
        if agent_kind not in aggregated:
            aggregated[agent_kind] = {
                "penalty_total": 0.0,
                "penalty_avg_per_sim_minute": 0.0,
                "subjects_count": 0,
                "metrics": {},  # metric_name -> {total, avg, count}
            }
        
        agg = aggregated[agent_kind]
        agg["penalty_total"] += sr.penalty_total
        agg["subjects_count"] += 1
        
        # Aggregate metrics
        for metric in sr.metrics:
            if metric.metric_name not in agg["metrics"]:
                agg["metrics"][metric.metric_name] = {
                    "penalty_total": 0.0,
                    "penalty_avg_per_sim_minute": 0.0,
                    "count": 0,
                }
            m = agg["metrics"][metric.metric_name]
            m["penalty_total"] += metric.penalty_total
            m["count"] += 1
    
    # Calculate averages
    if sim_minutes > 0:
        for _, agg in aggregated.items():
            agg["penalty_avg_per_sim_minute"] = agg["penalty_total"] / sim_minutes
            for _, m in agg["metrics"].items():
                m["penalty_avg_per_sim_minute"] = m["penalty_total"] / sim_minutes
    
    return aggregated


def print_agent_results(run, only_kinds: Optional[Set[AgentKind]] = None, header: str | None = None) -> None:
    """Print results aggregated by agent type."""
    aggregated = aggregate_results_by_agent(run)

    if only_kinds is not None:
        aggregated = {k: v for k, v in aggregated.items() if k in only_kinds}

    print("\n" + "=" * 72)
    print(header or "WYNIKI (aktywni agenci, agregowane per typ)")
    print("=" * 72)
    print(f"snapshots={run.snapshots_collected}  sim_min={run.summary.get('sim_duration_minutes', 0.0):.2f}")
    
    if not aggregated:
        print("Brak wyników do pokazania (agent nie został wykryty jako aktywny w oknie pomiaru).")
        return

    for agent_kind in sorted(aggregated.keys(), key=lambda x: x.value):
        agg = aggregated[agent_kind]
        print("-" * 72)
        print(
            f"{agent_kind.value}: subjects={agg['subjects_count']}  "
            f"total={agg['penalty_total']:.2f}  avg/min={agg['penalty_avg_per_sim_minute']:.4f}"
        )
        for metric_name in sorted(agg["metrics"].keys()):
            m = agg["metrics"][metric_name]
            print(
                f"  - {metric_name}: total={m['penalty_total']:.2f}  avg/min={m['penalty_avg_per_sim_minute']:.4f}"
            )


@dataclass(frozen=True)
class Scenario:
    name: str
    processes: list[ManagedProcess]
    kinds: Set[AgentKind]
    warmup_seconds: float


async def run_phase(
    simulator_url: str,
    duration_seconds: int,
    collection_interval: float,
    warmup_seconds: float,
    processes: list[ManagedProcess],
) -> object:
    mgr = ProcessManager(show_logs=any(p.show_logs for p in processes))
    for p in processes:
        mgr.add(p)

    runner = EvaluationRunner(simulator_url)
    try:
        if processes:
            logger.info(f"Starting processes: {[p.name for p in processes]}")
        mgr.start_all()
        if warmup_seconds > 0:
            await asyncio.sleep(warmup_seconds)

        logger.info(f"Collecting snapshots for {duration_seconds}s...")
        snapshots = await runner.collect_snapshots(
            duration_seconds=duration_seconds,
            collection_interval_seconds=collection_interval,
        )
        run = runner.evaluate(
            test_name="auto_active_agents",
            snapshots=snapshots,
            metric_sets=build_metric_sets(),
        )
        return run
    finally:
        mgr.stop_all()
        await runner.close()


def build_processes(simulator_url: str, show_logs: bool) -> list[ManagedProcess]:
    root = project_root()
    env = default_env()
    py = python_cmd()

    # Classic processes (Python agents) - only add if files exist
    classic = []
    
    heating_agent_path = root / "HeatingAgent" / "simple_agent.py"
    if heating_agent_path.exists():
        classic.append(
            ManagedProcess(
                name="HeatingAgent",
                cmd=[py, "simple_agent.py", simulator_url],
                cwd=root / "HeatingAgent",
                env=env,
                show_logs=show_logs,
            )
        )
    else:
        logger.warning(f"Skipping HeatingAgent: {heating_agent_path} not found")
    
    printer_agent_path = root / "PrinterAgent" / "main.py"
    if printer_agent_path.exists():
        classic.append(
            ManagedProcess(
                name="PrinterAgent",
                cmd=[py, "main.py", simulator_url],
                cwd=root / "PrinterAgent",
                env=env,
                show_logs=show_logs,
            )
        )
    else:
        logger.warning(f"Skipping PrinterAgent: {printer_agent_path} not found")
    
    light_agent_path = root / "LightAgent" / "simple_agent.py"
    if light_agent_path.exists():
        classic.append(
            ManagedProcess(
                name="LightAgent",
                cmd=[py, "simple_agent.py", simulator_url],
                cwd=root / "LightAgent",
                env=env,
                show_logs=show_logs,
            )
        )
    else:
        logger.warning(f"Skipping LightAgent: {light_agent_path} not found")
    
    blinds_agent_path = root / "WindowBlindsAgent" / "simple_agent.py"
    if blinds_agent_path.exists():
        classic.append(
            ManagedProcess(
                name="WindowBlindsAgent",
                cmd=[py, "simple_agent.py", simulator_url],
                cwd=root / "WindowBlindsAgent",
                env=env,
                show_logs=show_logs,
            )
        )
    else:
        logger.warning(f"Skipping WindowBlindsAgent: {blinds_agent_path} not found")

    return classic


def build_scenarios(simulator_url: str, show_logs: bool, warmup_seconds: float) -> list[Scenario]:
    """
    Scenariusze uruchamiane sekwencyjnie: jeden agent na raz, pomiar, stop.
    Pomija agenta, jeśli nie ma pliku/entrypointa.
    """
    root = project_root()
    env = default_env()
    py = python_cmd()

    scenarios: list[Scenario] = []

    # Heating classic (Python)
    heating_py = root / "HeatingAgent" / "simple_agent.py"
    if heating_py.exists():
        scenarios.append(
            Scenario(
                name="HeatingAgent (classic)",
                processes=[
                    ManagedProcess(
                        name="HeatingAgent",
                        cmd=[py, "simple_agent.py", simulator_url],
                        cwd=root / "HeatingAgent",
                        env=env,
                        show_logs=show_logs,
                    )
                ],
                kinds={AgentKind.HEATING},
                warmup_seconds=warmup_seconds,
            )
        )

    # Heating AI (Kotlin/Gradle)
    heating_ai_gradlew = root / "HeatingAgentAI" / "gradlew"
    if heating_ai_gradlew.exists():
        scenarios.append(
            Scenario(
                name="HeatingAgentAI",
                processes=[
                    ManagedProcess(
                        name="HeatingAgentAI",
                        cmd=["./gradlew", "run"],
                        cwd=root / "HeatingAgentAI",
                        env=env,
                        show_logs=show_logs,
                    )
                ],
                kinds={AgentKind.HEATING},
                warmup_seconds=max(10.0, warmup_seconds),  # Gradle start is slower
            )
        )

    # Printer classic
    printer_main = root / "PrinterAgent" / "main.py"
    if printer_main.exists():
        scenarios.append(
            Scenario(
                name="PrinterAgent",
                processes=[
                    ManagedProcess(
                        name="PrinterAgent",
                        cmd=[py, "main.py", simulator_url],
                        cwd=root / "PrinterAgent",
                        env=env,
                        show_logs=show_logs,
                    )
                ],
                kinds={AgentKind.PRINTER},
                warmup_seconds=warmup_seconds,
            )
        )

    # Light classic
    light_py = root / "LightAgent" / "simple_agent.py"
    if light_py.exists():
        scenarios.append(
            Scenario(
                name="LightAgent",
                processes=[
                    ManagedProcess(
                        name="LightAgent",
                        cmd=[py, "simple_agent.py", simulator_url],
                        cwd=root / "LightAgent",
                        env=env,
                        show_logs=show_logs,
                    )
                ],
                kinds={AgentKind.LIGHT},
                warmup_seconds=warmup_seconds,
            )
        )

    # Blinds classic
    blinds_py = root / "WindowBlindsAgent" / "simple_agent.py"
    if blinds_py.exists():
        scenarios.append(
            Scenario(
                name="WindowBlindsAgent",
                processes=[
                    ManagedProcess(
                        name="WindowBlindsAgent",
                        cmd=[py, "simple_agent.py", simulator_url],
                        cwd=root / "WindowBlindsAgent",
                        env=env,
                        show_logs=show_logs,
                    )
                ],
                kinds={AgentKind.BLINDS},
                warmup_seconds=warmup_seconds,
            )
        )

    return scenarios


async def run_sequence(
    simulator_url: str,
    duration_seconds: int,
    collection_interval: float,
    warmup_seconds: float,
    show_logs: bool,
) -> None:
    scenarios = build_scenarios(simulator_url, show_logs=show_logs, warmup_seconds=warmup_seconds)
    if not scenarios:
        print("Brak scenariuszy do uruchomienia (brak agentów w repo).")
        return

    for s in scenarios:
        # Ensure HeatingAgentAI port is free
        if s.name == "HeatingAgentAI":
            kill_process_on_port(8061)

        run = await run_phase(
            simulator_url=simulator_url,
            duration_seconds=duration_seconds,
            collection_interval=collection_interval,
            warmup_seconds=s.warmup_seconds,
            processes=s.processes,
        )
        print_agent_results(run, only_kinds=s.kinds, header=f"WYNIKI: {s.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-analiza aktywnych agentów (heating/printers/lights/blinds) jako średnia kara w czasie"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Czas trwania testu w sekundach (domyślnie: 300)",
    )
    parser.add_argument(
        "--simulator-url",
        type=str,
        default="http://localhost:8080",
        help="URL symulatora (domyślnie: http://localhost:8080)",
    )
    parser.add_argument(
        "--collection-interval",
        type=float,
        default=2.0,
        help="Interwał zbierania danych w sekundach (domyślnie: 2.0)",
    )
    parser.add_argument(
        "--start-agents",
        action="store_true",
        help="Spróbuj uruchomić lokalne agenty (jeśli pliki istnieją).",
    )
    parser.add_argument(
        "--sequence",
        action="store_true",
        help="Uruchom sekwencyjnie: jeden agent -> pomiar -> stop -> następny (auto-skip gdy brak).",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=5.0,
        help="Czas rozgrzewki po starcie procesów przed pomiarem (sekundy).",
    )
    parser.add_argument(
        "--show-agent-logs",
        action="store_true",
        help="Jeśli ustawione, logi agentów lecą do konsoli (domyślnie wyciszone).",
    )
    parser.add_argument(
        "--describe-metrics",
        action="store_true",
        help="Wypisz listę metryk i wyjdź.",
    )

    args = parser.parse_args()

    if args.describe_metrics:
        print_metrics_and_criteria()
        return

    if args.sequence:
        asyncio.run(
            run_sequence(
                simulator_url=args.simulator_url,
                duration_seconds=args.duration,
                collection_interval=args.collection_interval,
                warmup_seconds=args.warmup,
                show_logs=args.show_agent_logs,
            )
        )
        return

    if args.start_agents:
        async def _run():
            run = await run_phase(
                simulator_url=args.simulator_url,
                duration_seconds=args.duration,
                collection_interval=args.collection_interval,
                warmup_seconds=args.warmup,
                processes=build_processes(args.simulator_url, args.show_agent_logs),
            )
            print_agent_results(run)

        asyncio.run(_run())
        return

    # Single-phase (no process orchestration)
    asyncio.run(run_auto(args.duration, args.simulator_url, args.collection_interval))


if __name__ == "__main__":
    main()

