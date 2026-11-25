import re
from dataclasses import dataclass

from survey.terminals import TerminalSet, validate_name

Partition = tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class Evidence:
    forests: tuple[tuple[Partition, int], ...]


def encode_evidence(evidence: Evidence) -> dict:
    return {
        'forests': [
            {'groups': [list(group) for group in partition], 'count': hex(count)}
            for partition, count in evidence.forests
        ]
    }


def _decode_partition(groups: object, terminals: TerminalSet) -> Partition:
    if not isinstance(groups, list) or not groups:
        raise ValueError('a forest requires nonempty terminal groups')
    names = []
    partition = []
    for group in groups:
        if not isinstance(group, list) or not group:
            raise ValueError('each terminal group must be a nonempty array')
        parsed = tuple(sorted(validate_name(name, 'group terminal') for name in group))
        names.extend(parsed)
        partition.append(parsed)
    if sorted(names) != sorted(terminals.names):
        raise ValueError('a forest must partition the three declared terminals exactly once')
    return tuple(sorted(partition))


def decode_evidence(body: object, terminals: TerminalSet) -> Evidence:
    if not isinstance(body, dict) or set(body) != {'forests'}:
        raise ValueError('invalid station evidence object')
    rows = body['forests']
    if not isinstance(rows, list) or not rows:
        raise ValueError('station evidence requires at least one forest row')
    forests = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'groups', 'count'}:
            raise ValueError('invalid station forest row')
        partition = _decode_partition(row['groups'], terminals)
        if partition in forests:
            raise ValueError('duplicate terminal partition')
        count = row['count']
        if not isinstance(count, str) or re.fullmatch(r'0x[1-9a-f][0-9a-f]*', count) is None:
            raise ValueError('forest count must be a positive hexadecimal integer')
        forests[partition] = int(count, 16)
    return Evidence(tuple(sorted(forests.items())))
