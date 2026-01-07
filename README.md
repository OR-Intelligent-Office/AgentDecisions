### Uruchom OrSimulator

```
cd OrSimulator
./gradlew run
```

### Program

```
cd AgentDecisions
source venv/bin/activate
python main.py --sequence --duration 300
```
Zwiększyć duration w miare potrzeby

### Kolejni agenci

Dopisywać w main.py w AgentDecisions:
```
def build_scenarios(simulator_url: str, show_logs: bool, warmup_seconds: float) -> list[Scenario]:
    # ...
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
                warmup_seconds=max(10.0, warmup_seconds),
            )
        )
    # ...
```