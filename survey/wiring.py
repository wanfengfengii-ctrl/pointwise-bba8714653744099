from collections import deque
from dataclasses import dataclass

from survey.terminals import TerminalSet, validate_name


@dataclass(frozen=True, slots=True)
class Wire:
    wire_id: str
    a: str
    b: str


@dataclass(frozen=True, slots=True)
class Wiring:
    junctions: tuple[str, ...]
    wires: tuple[Wire, ...]

    def to_line_table(self) -> dict:
        return {
            'junctions': list(self.junctions),
            'wires': [[wire.wire_id, wire.a, wire.b] for wire in self.wires],
        }


def validate_wiring(terminals: TerminalSet, line_table: object) -> Wiring:
    if not isinstance(line_table, dict) or set(line_table) != {'junctions', 'wires'}:
        raise ValueError('line table requires junctions and wires')
    junction_rows = line_table['junctions']
    wire_rows = line_table['wires']
    if not isinstance(junction_rows, (list, tuple)) or not isinstance(wire_rows, (list, tuple)):
        raise ValueError('junctions and wires must be sequences')

    junctions = tuple(validate_name(name, 'junction') for name in junction_rows)
    vertices = set(terminals.names)
    for name in junctions:
        if name in vertices:
            raise ValueError(f'duplicate junction or public terminal name: {name}')
        vertices.add(name)

    neighbours: dict[str, list[str]] = {name: [] for name in vertices}
    wires = []
    seen_ids = set()
    for row in wire_rows:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError('a wire requires its original number and two endpoints')
        wire_id = validate_name(row[0], 'wire number')
        a = validate_name(row[1], 'wire endpoint')
        b = validate_name(row[2], 'wire endpoint')
        if wire_id in seen_ids:
            raise ValueError(f'duplicate wire number: {wire_id}')
        if a not in vertices or b not in vertices:
            raise ValueError(f'undeclared endpoint on {wire_id}')
        seen_ids.add(wire_id)
        wires.append(Wire(wire_id, a, b))
        neighbours[a].append(b)
        neighbours[b].append(a)

    reached = set(terminals.names)
    frontier = deque(terminals.names)
    while frontier:
        for neighbour in neighbours[frontier.popleft()]:
            if neighbour not in reached:
                reached.add(neighbour)
                frontier.append(neighbour)
    if reached != vertices:
        raise ValueError(f'junctions cannot reach a public terminal: {sorted(vertices - reached)}')
    return Wiring(junctions, tuple(wires))
