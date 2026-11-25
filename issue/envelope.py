import json
from dataclasses import dataclass

from issue.evidence import Evidence, decode_evidence, encode_evidence
from survey.terminals import TerminalSet, validate_name, validate_terminal_set


@dataclass(frozen=True, slots=True)
class PackageEnvelope:
    freeze_id: str
    batch: str
    station: str
    revision_id: str
    terminals: TerminalSet
    evidence: Evidence


def encode_package(package: PackageEnvelope) -> bytes:
    body = encode_evidence(package.evidence)
    decode_evidence(body, package.terminals)
    document = {
        'version': 1,
        'freeze_id': validate_name(package.freeze_id, 'freeze number'),
        'batch': validate_name(package.batch, 'batch'),
        'station': validate_name(package.station, 'station'),
        'revision_id': validate_name(package.revision_id, 'revision number'),
        'terminals': package.terminals.names,
        'evidence': body,
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate package field: {key}')
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f'invalid package constant: {value}')


def decode_package(raw: bytes) -> PackageEnvelope:
    if not isinstance(raw, bytes):
        raise ValueError('station package must be bytes')
    try:
        document = json.loads(
            raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError('invalid station package JSON') from error
    fields = {'version', 'freeze_id', 'batch', 'station', 'revision_id', 'terminals', 'evidence'}
    if not isinstance(document, dict) or set(document) != fields:
        raise ValueError('invalid V1 package envelope')
    if type(document['version']) is not int or document['version'] != 1:
        raise ValueError('unsupported station package version')
    terminals = validate_terminal_set(document['terminals'])
    return PackageEnvelope(
        validate_name(document['freeze_id'], 'freeze number'),
        validate_name(document['batch'], 'batch'),
        validate_name(document['station'], 'station'),
        validate_name(document['revision_id'], 'revision number'),
        terminals,
        decode_evidence(document['evidence'], terminals),
    )
