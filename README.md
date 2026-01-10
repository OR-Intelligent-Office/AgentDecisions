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

---

### Metryki

Wynik każdej metryki:
- **penalty_total** – suma kar w całym oknie pomiaru
- **penalty_avg_per_sim_minute** – średnia kara na minutę symulacji (to jest główny “score”)

#### HeatingAgent

- **heating_comfort_during_meetings**
  - **Cel**: komfort cieplny podczas spotkań.
  - **Kara**: za każdy tick (snapshot) w trakcie spotkania, gdy temperatura w pokoju spotkania jest **< 21°C**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

- **heating_waste**
  - **Cel**: wykrywanie “marnowania” ogrzewania.
  - **Kara**: za każdy tick, gdy **is_heating == True** oraz jednocześnie:
    - w żadnym pokoju nie ma osób,
    - w żadnym pokoju nie trwa spotkanie,
    - wszystkie pokoje mają temperaturę **>= 18°C**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

#### PrinterAgent (per drukarka)

- **printer_availability**
  - **Cel**: dostępność drukarki podczas aktywności.
  - **Kara**: za każdy tick, gdy w pokoju jest aktywność (**osoby > 0 lub trwa spotkanie**), drukarka ma zasoby (**toner>0 i paper>0**), nie ma **power_outage**, a drukarka **nie jest ON**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

- **printer_waste**
  - **Cel**: wykrywanie “marnowania” pracy drukarki.
  - **Kara**: za każdy tick, gdy **brak osób** i **nie trwa spotkanie**, a drukarka jest **ON**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

- **printer_illegal_consumption**
  - **Cel**: wykrywanie nielegalnego zużycia zasobów.
  - **Kara**: za każdy tick, gdy (między kolejnymi snapshotami) **toner lub papier spada**, mimo że drukarka **nie jest ON**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

#### LightAgent (per pokój)

- **lights_coverage**
  - **Cel**: zapewnienie światła podczas aktywności.
  - **Kara**: za każdy tick, gdy w pokoju jest aktywność (**osoby > 0 lub trwa spotkanie**), a naświetlenie pokoju (`illumination`, lux) jest **< 300 lux**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

- **lights_waste**
  - **Cel**: wykrywanie marnowania energii na oświetlenie.
  - **Kara**: za każdy tick, gdy **brak osób** i **nie trwa spotkanie**, a **jakiekolwiek** światło w pokoju jest **ON**.
  - **Punktowanie**: **+1.0** za tick naruszenia.

#### WindowBlindsAgent (per pokój)

- **blinds_daylight**
  - **Cel**: sensowne ustawienie rolet w zależności od światła dziennego i aktywności.
  - **Heurystyka**:
    - jeśli **externalLightLux >= 6000** i pokój jest aktywny (**osoby > 0 lub trwa spotkanie**) → rolety powinny być **OPEN**
    - jeśli **externalLightLux <= 3000** i pokój jest nieaktywny (**brak osób i brak spotkania**) → rolety powinny być **CLOSED**
  - **Kara**: **+1.0** za każdy tick naruszenia.