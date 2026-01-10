from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum


class AgentKind(str, Enum):
    PRINTER = "PrinterAgent"
    HEATING = "HeatingAgent"
    LIGHT = "LightAgent"
    BLINDS = "WindowBlindsAgent"


class SubjectKind(str, Enum):
    HEATING = "heating"
    PRINTER = "printer"
    LIGHTS = "lights"
    BLINDS = "blinds"


@dataclass(frozen=True)
class Subject:
    kind: SubjectKind
    subject_id: str  # e.g. "heating", "printer_208", "room_208_lights", "blinds_room_208"
    room_id: Optional[str] = None
    room_name: Optional[str] = None


@dataclass
class Meeting:
    start_time: datetime
    end_time: datetime
    title: str
    room_id: str
    room_name: str


@dataclass
class LightState:
    light_id: str
    room_id: str
    room_name: str
    state: str  # "ON" | "OFF" | "BROKEN"
    brightness: int
    timestamp: datetime


@dataclass
class BlindsState:
    blinds_id: str
    room_id: str
    room_name: str
    state: str  # "OPEN" | "CLOSED"
    timestamp: datetime


@dataclass
class PrinterState:
    printer_id: str
    room_id: str
    room_name: str
    state: str  # "ON" | "OFF" | "BROKEN"
    toner_level: int
    paper_level: int
    timestamp: datetime


@dataclass
class RoomState:
    room_id: str
    room_name: str
    lights: List[LightState]
    blinds: Optional[BlindsState]
    printer: Optional[PrinterState]
    people_count: int
    meetings: List[Meeting]
    temperature_c: float
    illumination_lux: float = 0.0
    is_heating: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EnvironmentSnapshot:
    simulation_time: datetime
    rooms: List[RoomState]
    external_temperature_c: float
    power_outage: bool
    # Global/derived values (for backwards-compatible metrics):
    # - external_light_lux comes from OrSimulator's externalLightLux (0..10000)
    # - daylight_intensity is a normalized proxy in range 0..1 (external_light_lux/10000)
    external_light_lux: float = 0.0
    is_heating: bool = False
    daylight_intensity: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MetricScore:
    metric_name: str
    subject: Subject
    penalty_total: float
    penalty_avg_per_sim_minute: float
    details: Dict[str, Any]


@dataclass
class SubjectResult:
    subject: Subject
    metrics: List[MetricScore]
    penalty_total: float
    penalty_avg_per_sim_minute: float
    details: Dict[str, Any]


@dataclass
class RunResult:
    test_name: str
    start_time: datetime
    end_time: datetime
    snapshots_collected: int
    subjects: List[SubjectResult]
    summary: Dict[str, Any]

