from dataclasses import dataclass

from survey.terminals import TerminalSet, validate_name
from survey.wiring import Wiring


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: str
    station: str
    batch: str
    parent_id: str | None
    terminals: TerminalSet
    wiring: Wiring


def build_revision(
    revision_id: str,
    station: str,
    batch: str,
    parent: Revision | None,
    terminals: TerminalSet,
    wiring: Wiring,
) -> Revision:
    validate_name(revision_id, 'revision number')
    validate_name(station, 'station')
    validate_name(batch, 'batch')
    parent_id = None
    if parent is not None:
        if (parent.station, parent.batch) != (station, batch):
            raise ValueError('parent revision belongs to a different station or batch')
        parent_id = parent.revision_id
    return Revision(revision_id, station, batch, parent_id, terminals, wiring)
