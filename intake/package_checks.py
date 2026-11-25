from intake.manifest import BatchManifest
from issue.envelope import PackageEnvelope, decode_package
from survey.terminals import validate_name


def check_arrival(manifest: BatchManifest, station: str, raw: bytes) -> PackageEnvelope:
    entry = manifest.find_station(validate_name(station, 'expected station'))
    if entry is None:
        raise ValueError(f'station {station} is absent from batch {manifest.batch}')
    envelope = decode_package(raw)
    if envelope.batch != manifest.batch or envelope.station != entry.station:
        raise ValueError('station package does not match the requested batch and station')
    if set(envelope.terminals.names) != set(entry.terminals.names):
        raise ValueError('station package terminals do not match the batch manifest')
    return envelope
