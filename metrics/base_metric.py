from abc import ABC, abstractmethod
from typing import List
from models.data_models import (
    EnvironmentSnapshot,
    Subject,
    MetricScore,
)


class BaseMetric(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def calculate(
        self,
        snapshots: List[EnvironmentSnapshot],
        subject: Subject,
    ) -> MetricScore:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"

