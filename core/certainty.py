from __future__ import annotations

import warnings
from dataclasses import dataclass
from math import log2
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

type Coordinate = tuple[int, int]


class CellPayload(TypedDict):
    x: int
    y: int
    certainty: float
    entropy: float
    last_updated_ms: int
    updated_by: str
    decay_rate: float
    owner: NotRequired[str]


type GridPayload = list[list[CellPayload]]


@dataclass(slots=True)
class CellState:
    x: int
    y: int
    certainty: float
    last_updated_ms: int
    updated_by: str
    decay_rate: float

    @property
    def coordinate(self) -> Coordinate:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class CellScore:
    coordinate: Coordinate
    certainty: float
    entropy: float


def clamp_certainty(value: float) -> float:
    return max(0.0, min(1.0, value))


def shannon_entropy(certainty: float) -> float:
    probability = clamp_certainty(certainty)
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(probability * log2(probability) + (1.0 - probability) * log2(1.0 - probability))


def _payload_float(payload: CellPayload, key: str, default: float = 0.0) -> float:
    value = cast("float | int | str | None", payload.get(key, default))
    return default if value is None else float(value)


def _payload_int(payload: CellPayload, key: str, default: int = 0) -> int:
    value = cast("float | int | str | None", payload.get(key, default))
    return default if value is None else int(value)


class CertaintyMap:
    __slots__ = ("_grid", "decay_rate", "size")

    def __init__(
        self,
        size: int,
        *,
        initial_certainty: float = 0.5,
        decay_rate: float = 0.001,
        now_ms: int = 0,
    ) -> None:
        self.size = size
        self.decay_rate = decay_rate
        self._grid: list[list[CellState]] = [
            [
                CellState(
                    x=x,
                    y=y,
                    certainty=clamp_certainty(initial_certainty),
                    last_updated_ms=now_ms,
                    updated_by="bootstrap",
                    decay_rate=decay_rate,
                )
                for x in range(size)
            ]
            for y in range(size)
        ]

    def __iter__(self) -> Iterator[CellState]:
        for row in self._grid:
            yield from row

    def cell(self, coordinate: Coordinate) -> CellState:
        x, y = coordinate
        if x < 0 or y < 0:
            _msg = f"Coordinate {coordinate} out of bounds"
            raise IndexError(_msg)
        return self._grid[y][x]

    def set_certainty(
        self,
        coordinate: Coordinate,
        certainty: float,
        *,
        updated_by: str,
        now_ms: int,
    ) -> CellState:
        cell = self.cell(coordinate)
        cell.certainty = clamp_certainty(certainty)
        cell.updated_by = updated_by
        cell.last_updated_ms = now_ms
        return cell

    def update_cell(
        self,
        coordinate: Coordinate,
        *,
        updated_by: str,
        increment: float = 0.05,
        now_ms: int,
    ) -> CellState:
        cell = self.cell(coordinate)
        return self.set_certainty(
            coordinate,
            cell.certainty + increment,
            updated_by=updated_by,
            now_ms=now_ms,
        )

    def decay_all(
        self,
        *,
        seconds: float,
        now_ms: int,
        skip: set[Coordinate] | None = None,
    ) -> None:
        skipped = skip or set()
        for cell in self:
            if cell.coordinate in skipped:
                continue
            self.set_certainty(
                cell.coordinate,
                cell.certainty * (1.0 - cell.decay_rate * seconds),
                updated_by=cell.updated_by,
                now_ms=now_ms,
            )

    def entropy_at(self, coordinate: Coordinate) -> float:
        return shannon_entropy(self.cell(coordinate).certainty)

    def ranked_cells(self, claimed_zones: set[Coordinate] | None = None) -> list[CellScore]:
        claimed = claimed_zones or set()
        scores = [
            CellScore(
                coordinate=cell.coordinate,
                certainty=cell.certainty,
                entropy=shannon_entropy(cell.certainty),
            )
            for cell in self
            if cell.coordinate not in claimed
        ]
        return sorted(
            scores,
            key=lambda item: (-item.entropy, item.coordinate[1], item.coordinate[0]),
        )

    def average_entropy(self) -> float:
        total = sum(shannon_entropy(cell.certainty) for cell in self)
        return total / (self.size * self.size)

    def coverage(self, *, threshold: float = 0.95) -> float:
        searched = sum(1 for cell in self if cell.certainty >= threshold)
        return searched / (self.size * self.size)

    def clone(self) -> CertaintyMap:
        copy = CertaintyMap(self.size, initial_certainty=0.0, decay_rate=self.decay_rate, now_ms=0)
        for cell in self:
            c = copy.cell(cell.coordinate)
            c.certainty = cell.certainty
            c.updated_by = cell.updated_by
            c.last_updated_ms = cell.last_updated_ms
            c.decay_rate = cell.decay_rate
        return copy

    def reset_from(self, source: CertaintyMap) -> None:
        for cell in source:
            target = self.cell(cell.coordinate)
            target.certainty = clamp_certainty(cell.certainty)
            target.last_updated_ms = cell.last_updated_ms
            target.updated_by = cell.updated_by
            target.decay_rate = cell.decay_rate

    def replace_from_rows(self, rows: GridPayload) -> None:
        for y, row in enumerate(rows):
            for x, payload in enumerate(row):
                self.set_certainty(
                    (x, y),
                    _payload_float(payload, "certainty"),
                    updated_by=str(payload.get("updated_by", "peer")),
                    now_ms=_payload_int(payload, "last_updated_ms"),
                )

    def merge_max_from(self, other: CertaintyMap) -> None:
        warnings.warn(
            "merge_max_from is not decay-safe; use merge_timestamped_from instead. "
            "This method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._merge_max_from(other)

    def _merge_max_from(self, other: CertaintyMap) -> None:
        for cell in other:
            current = self.cell(cell.coordinate)
            if cell.certainty > current.certainty:
                self.set_certainty(
                    cell.coordinate,
                    cell.certainty,
                    updated_by=cell.updated_by,
                    now_ms=cell.last_updated_ms,
                )

    def merge_timestamped_from(self, other: CertaintyMap) -> None:
        for cell in other:
            current = self.cell(cell.coordinate)
            if cell.last_updated_ms > current.last_updated_ms or (
                cell.last_updated_ms == current.last_updated_ms
                and cell.certainty > current.certainty
            ):
                self.set_certainty(
                    cell.coordinate,
                    cell.certainty,
                    updated_by=cell.updated_by,
                    now_ms=cell.last_updated_ms,
                )

    def to_rows(self, owners: Mapping[Coordinate, str] | None = None) -> GridPayload:
        rows: GridPayload = []
        for row in self._grid:
            row_payload: list[CellPayload] = []
            for cell in row:
                payload: CellPayload = {
                    "x": cell.x,
                    "y": cell.y,
                    "certainty": round(cell.certainty, 4),
                    "entropy": round(shannon_entropy(cell.certainty), 4),
                    "last_updated_ms": cell.last_updated_ms,
                    "updated_by": cell.updated_by,
                    "decay_rate": cell.decay_rate,
                }
                if owners and cell.coordinate in owners:
                    payload["owner"] = owners[cell.coordinate]
                row_payload.append(payload)
            rows.append(row_payload)
        return rows

    def merge_rows_timestamped(
        self,
        rows: GridPayload,
        *,
        now_ms: int,
        updated_by: str,
    ) -> None:
        for row in rows:
            for payload in row:
                coordinate = (_payload_int(payload, "x"), _payload_int(payload, "y"))
                incoming_certainty = _payload_float(payload, "certainty")
                incoming_ts = _payload_int(payload, "last_updated_ms", default=now_ms)
                current = self.cell(coordinate)
                if incoming_ts > current.last_updated_ms or (
                    incoming_ts == current.last_updated_ms
                    and incoming_certainty > current.certainty
                ):
                    self.set_certainty(
                        coordinate,
                        incoming_certainty,
                        updated_by=updated_by,
                        now_ms=incoming_ts,
                    )

    def merge_rows_max(
        self,
        rows: GridPayload,
        *,
        now_ms: int,
        updated_by: str,
    ) -> None:
        warnings.warn(
            "merge_rows_max is not decay-safe; use merge_rows_timestamped instead. "
            "This method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._merge_rows_max(rows, now_ms=now_ms, updated_by=updated_by)

    def _merge_rows_max(
        self,
        rows: GridPayload,
        *,
        now_ms: int,
        updated_by: str,
    ) -> None:
        for row in rows:
            for payload in row:
                coordinate = (_payload_int(payload, "x"), _payload_int(payload, "y"))
                self.set_certainty(
                    coordinate,
                    max(self.cell(coordinate).certainty, _payload_float(payload, "certainty")),
                    updated_by=updated_by,
                    now_ms=now_ms,
                )
