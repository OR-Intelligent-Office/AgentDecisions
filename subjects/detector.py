from __future__ import annotations

from typing import Dict, List

from models.data_models import EnvironmentSnapshot, Subject, SubjectKind


def detect_active_subjects(snapshots: List[EnvironmentSnapshot]) -> List[Subject]:
    """
    Detects "active" controllers based on device state changes.
    This is intentionally heuristic (there is no direct process telemetry).
    """
    if not snapshots:
        return []

    subjects: List[Subject] = []

    # Heating (global)
    heating_values = [s.is_heating for s in snapshots]
    if any(heating_values) or any(
        heating_values[i] != heating_values[i - 1] for i in range(1, len(heating_values))
    ):
        subjects.append(Subject(kind=SubjectKind.HEATING, subject_id="heating"))

    # Per-room lights and blinds, per-printer
    last_light: Dict[str, Dict[str, str]] = {}   # lightId -> {"state":..., "brightness":...}
    last_blinds: Dict[str, str] = {}            # blindsId -> state
    last_printer: Dict[str, Dict[str, int | str]] = {}  # printerId -> state/toner/paper

    active_rooms_lights: Dict[str, Subject] = {}
    active_rooms_blinds: Dict[str, Subject] = {}
    active_printers: Dict[str, Subject] = {}

    for s in snapshots:
        for room in s.rooms:
            # Lights (grouped per room)
            room_lights_changed = False
            room_any_light_on = False
            for l in room.lights:
                if l.state == "ON":
                    room_any_light_on = True
                cur = {"state": l.state, "brightness": str(l.brightness)}
                prev = last_light.get(l.light_id)
                if prev is None:
                    last_light[l.light_id] = cur
                    continue
                if cur != prev:
                    room_lights_changed = True
                    last_light[l.light_id] = cur
            if room_lights_changed or room_any_light_on:
                active_rooms_lights[room.room_id] = Subject(
                    kind=SubjectKind.LIGHTS,
                    subject_id=f"lights_{room.room_id}",
                    room_id=room.room_id,
                    room_name=room.room_name,
                )

            # Blinds
            if room.blinds:
                b = room.blinds
                prev_state = last_blinds.get(b.blinds_id)
                if prev_state is None:
                    last_blinds[b.blinds_id] = b.state
                elif prev_state != b.state:
                    active_rooms_blinds[room.room_id] = Subject(
                        kind=SubjectKind.BLINDS,
                        subject_id=b.blinds_id,
                        room_id=room.room_id,
                        room_name=room.room_name,
                    )
                    last_blinds[b.blinds_id] = b.state
                elif b.state == "OPEN":
                    active_rooms_blinds[room.room_id] = Subject(
                        kind=SubjectKind.BLINDS,
                        subject_id=b.blinds_id,
                        room_id=room.room_id,
                        room_name=room.room_name,
                    )

            # Printer
            if room.printer:
                p = room.printer
                curp = {"state": p.state, "toner": p.toner_level, "paper": p.paper_level}
                prevp = last_printer.get(p.printer_id)
                if prevp is None:
                    last_printer[p.printer_id] = curp
                else:
                    if curp != prevp:
                        active_printers[p.printer_id] = Subject(
                            kind=SubjectKind.PRINTER,
                            subject_id=p.printer_id,
                            room_id=room.room_id,
                            room_name=room.room_name,
                        )
                        last_printer[p.printer_id] = curp
                    elif p.state == "ON":
                        active_printers[p.printer_id] = Subject(
                            kind=SubjectKind.PRINTER,
                            subject_id=p.printer_id,
                            room_id=room.room_id,
                            room_name=room.room_name,
                        )

    subjects.extend(active_rooms_lights.values())
    subjects.extend(active_rooms_blinds.values())
    subjects.extend(active_printers.values())

    subjects.sort(key=lambda x: (x.kind.value, x.subject_id))
    return subjects


