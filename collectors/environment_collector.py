import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional, List
from models.data_models import (
    EnvironmentSnapshot,
    RoomState,
    LightState,
    PrinterState,
    BlindsState,
    Meeting,
)

logger = logging.getLogger(__name__)


class EnvironmentCollector:
    def __init__(self, simulator_url: str = "http://localhost:8080"):
        self.simulator_url = simulator_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def collect_snapshot(self) -> Optional[EnvironmentSnapshot]:
        try:
            session = await self._get_session()
            async with session.get(f"{self.simulator_url}/api/environment/state") as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch environment state: {response.status}")
                    return None

                data = await response.json()
                return await self._parse_environment_state(data)
        except Exception as e:
            logger.error(f"Error collecting snapshot: {e}")
            return None

    async def _parse_environment_state(self, data: dict) -> EnvironmentSnapshot:
        try:
            sim_time_str = data.get("simulationTime", "")
            simulation_time = datetime.fromisoformat(sim_time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            simulation_time = datetime.now()

        external_temperature_c = float(data.get("externalTemperature", 0.0) or 0.0)
        external_light_lux = float(data.get("externalLightLux", 0.0) or 0.0)
        daylight_intensity = max(0.0, min(1.0, external_light_lux / 10000.0))
        rooms_data = data.get("rooms", [])
        rooms: List[RoomState] = []

        # Fetch per-room heating states (OrSimulator doesn't include them in /state).
        heating_by_room: dict[str, bool] = {}
        try:
            session = await self._get_session()
            async def _fetch(room_id: str) -> None:
                try:
                    async with session.get(f"{self.simulator_url}/api/environment/heating/rooms/{room_id}") as resp:
                        if resp.status == 200:
                            payload = await resp.json()
                            heating_by_room[room_id] = bool(payload.get("isHeating", False))
                except Exception:
                    return

            await asyncio.gather(*[_fetch(r.get("id", "")) for r in rooms_data if r.get("id")])
        except Exception:
            pass

        for room_data in rooms_data:
            room_id = room_data.get("id", "")
            room_name = room_data.get("name", "")

            lights_data = room_data.get("lights", [])
            lights: List[LightState] = []
            for light_data in lights_data:
                light_state = LightState(
                    light_id=light_data.get("id", ""),
                    room_id=room_id,
                    room_name=room_name,
                    state=str(light_data.get("state", "OFF")),
                    brightness=light_data.get("brightness", 0),
                    timestamp=simulation_time,
                )
                lights.append(light_state)

            blinds_state: Optional[BlindsState] = None
            blinds_data = room_data.get("blinds")
            if isinstance(blinds_data, dict) and blinds_data:
                blinds_state = BlindsState(
                    blinds_id=blinds_data.get("id", ""),
                    room_id=room_id,
                    room_name=room_name,
                    state=str(blinds_data.get("state", "CLOSED")),
                    timestamp=simulation_time,
                )

            printer_state: Optional[PrinterState] = None
            printer_data = room_data.get("printer")
            if isinstance(printer_data, dict) and printer_data:
                try:
                    printer_state = PrinterState(
                        printer_id=printer_data.get("id", ""),
                        room_id=room_id,
                        room_name=room_name,
                        state=str(printer_data.get("state", "OFF")),
                        toner_level=int(printer_data.get("tonerLevel", 0)),
                        paper_level=int(printer_data.get("paperLevel", 0)),
                        timestamp=simulation_time,
                    )
                except (TypeError, ValueError):
                    printer_state = None

            meetings_data = room_data.get("scheduledMeetings", [])
            meetings: List[Meeting] = []
            for meeting_data in meetings_data:
                try:
                    start_time = datetime.fromisoformat(
                        meeting_data.get("startTime", "").replace("Z", "+00:00")
                    )
                    end_time = datetime.fromisoformat(
                        meeting_data.get("endTime", "").replace("Z", "+00:00")
                    )
                    meeting = Meeting(
                        start_time=start_time,
                        end_time=end_time,
                        title=meeting_data.get("title", "Spotkanie"),
                        room_id=room_id,
                        room_name=room_name,
                    )
                    meetings.append(meeting)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse meeting: {e}")
                    continue

            temp_sensor = room_data.get("temperatureSensor", {}) or {}
            try:
                temperature_c = float(temp_sensor.get("temperature", 0.0))
            except (TypeError, ValueError):
                temperature_c = 0.0

            room_state = RoomState(
                room_id=room_id,
                room_name=room_name,
                lights=lights,
                blinds=blinds_state,
                printer=printer_state,
                people_count=room_data.get("peopleCount", 0),
                meetings=meetings,
                temperature_c=temperature_c,
                illumination_lux=float(room_data.get("illumination", 0.0) or 0.0),
                is_heating=heating_by_room.get(room_id, False),
                timestamp=simulation_time,
            )
            rooms.append(room_state)

        is_heating_any = any(r.is_heating for r in rooms)
        return EnvironmentSnapshot(
            simulation_time=simulation_time,
            rooms=rooms,
            external_temperature_c=external_temperature_c,
            power_outage=data.get("powerOutage", False),
            external_light_lux=external_light_lux,
            is_heating=is_heating_any,
            daylight_intensity=daylight_intensity,
            timestamp=datetime.now(),
        )

