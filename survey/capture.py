from uuid import uuid4

from survey.revision_store import RevisionStore
from survey.revisions import build_revision
from survey.terminals import validate_name, validate_terminal_set
from survey.wiring import validate_wiring


def record_revision(
    store: RevisionStore,
    station: str,
    batch: str,
    parent_id: str | None,
    terminals: object,
    line_table: object,
) -> str:
    validate_name(station, 'station')
    validate_name(batch, 'batch')
    terminal_set = validate_terminal_set(terminals)
    wiring = validate_wiring(terminal_set, line_table)
    parent = None
    if parent_id is not None:
        parent = store.get_revision(validate_name(parent_id, 'parent revision'))
    revision = build_revision(f'rev-{uuid4().hex}', station, batch, parent, terminal_set, wiring)
    return store.append_revision(revision)
