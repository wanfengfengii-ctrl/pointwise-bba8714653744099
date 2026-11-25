from intake.inbox_store import InboxStore
from survey.terminals import validate_name


def receive_package(inbox: InboxStore, batch: str, station: str, raw: bytes) -> str:
    batch = validate_name(batch, 'batch')
    station = validate_name(station, 'expected station')
    return inbox.record_arrival(batch, station, raw).receipt_id
