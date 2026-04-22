
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roles.drone import DroneState

@dataclass(frozen=True, slots=True)
class FailurePlan:

    drone_id: str | None = None
    fail_at_seconds: int | None = None
    mode: str = "scheduled"

    @property
    def enabled(self) -> bool:
        return self.drone_id is not None and self.fail_at_seconds is not None

@dataclass(frozen=True, slots=True)
class FailureEvent:

    drone_id: str
    now_seconds: int
    mode: str

FailureSchedule = FailurePlan

class FailureInjector:

    def __init__(self, plan: FailurePlan) -> None:
        self.plan = plan
        self._triggered = False

    @property
    def triggered(self) -> bool:
        return self._triggered

    def should_trigger(self, *, now_seconds: int) -> bool:
        return (
            self.plan.enabled
            and not self._triggered
            and self.plan.fail_at_seconds is not None
            and now_seconds >= self.plan.fail_at_seconds
        )

    def maybe_trigger(self, drones: list[DroneState], *, now_seconds: int) -> FailureEvent | None:
        if not self.should_trigger(now_seconds=now_seconds) or self.plan.drone_id is None:
            return None
        for drone in drones:
            if drone.drone_id == self.plan.drone_id and drone.alive and drone.reachable:
                drone.reachable = False
                self._triggered = True
                return FailureEvent(
                    drone_id=drone.drone_id,
                    now_seconds=now_seconds,
                    mode=self.plan.mode,
                )
        self._triggered = True
        return None

    def inject(self, drones: list[DroneState], *, now_second: int) -> DroneState | None:
        event = self.maybe_trigger(drones, now_seconds=now_second)
        if event is None:
            return None
        return next((drone for drone in drones if drone.drone_id == event.drone_id), None)
