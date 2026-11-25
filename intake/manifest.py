from dataclasses import dataclass

from survey.terminals import TerminalSet, validate_name, validate_terminal_set


@dataclass(frozen=True, slots=True)
class StationEntry:
    station: str
    terminals: TerminalSet

    def __post_init__(self) -> None:
        validate_name(self.station, 'station')
        if not isinstance(self.terminals, TerminalSet):
            raise ValueError('station entry requires a terminal set')


@dataclass(frozen=True, slots=True)
class BatchManifest:
    batch: str
    stations: tuple[StationEntry, StationEntry]

    def __post_init__(self) -> None:
        validate_name(self.batch, 'batch')
        if not isinstance(self.stations, tuple) or len(self.stations) != 2:
            raise ValueError('batch manifest requires exactly two stations')
        first, second = self.stations
        if not isinstance(first, StationEntry) or not isinstance(second, StationEntry):
            raise ValueError('invalid station entries in batch manifest')
        if first.station == second.station:
            raise ValueError('batch station names must be distinct')
        if set(first.terminals.names) != set(second.terminals.names):
            raise ValueError('both stations must declare the same three terminal names')

    @classmethod
    def from_mapping(cls, batch: str, stations: object) -> 'BatchManifest':
        if not isinstance(stations, dict) or len(stations) != 2:
            raise ValueError('batch manifest requires a mapping of two stations to terminal names')
        entries = tuple(StationEntry(name, validate_terminal_set(terms)) for name, terms in stations.items())
        return cls(batch, entries)

    def to_mapping(self) -> dict[str, tuple[str, ...]]:
        return {entry.station: entry.terminals.names for entry in self.stations}

    def find_station(self, station: str) -> StationEntry | None:
        return next((entry for entry in self.stations if entry.station == station), None)
