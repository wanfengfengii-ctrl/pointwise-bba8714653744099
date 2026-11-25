from math import prod

from issue.evidence import Evidence
from survey.revisions import Revision
from survey.wiring import Wire


def _local_islands(vertices: tuple[str, ...], wires: tuple[Wire, ...]) -> list[set[str]]:
    neighbours: dict[str, set[str]] = {vertex: set() for vertex in vertices}
    for wire in wires:
        neighbours[wire.a].add(wire.b)
        neighbours[wire.b].add(wire.a)

    unvisited = set(vertices)
    islands = []
    while unvisited:
        first = unvisited.pop()
        island = {first}
        pending = [first]
        while pending:
            reached = neighbours[pending.pop()] & unvisited
            unvisited.difference_update(reached)
            island.update(reached)
            pending.extend(reached)
        islands.append(island)
    return islands


def _tree_count(island: set[str], wires: tuple[Wire, ...]) -> int:
    # Ground one vertex and count complete local wirings by the reduced Laplacian.
    columns = {vertex: index for index, vertex in enumerate(sorted(island)[1:])}
    size = len(columns)
    if size == 0:
        return 1
    matrix = [[0] * size for _ in range(size)]
    for wire in wires:
        if wire.a == wire.b or wire.a not in island or wire.b not in island:
            continue
        a, b = columns.get(wire.a), columns.get(wire.b)
        if a is not None:
            matrix[a][a] += 1
        if b is not None:
            matrix[b][b] += 1
        if a is not None and b is not None:
            matrix[a][b] -= 1
            matrix[b][a] -= 1

    # The grounded Laplacian of a connected island has positive leading minors.
    divisor = 1
    for k in range(size - 1):
        pivot = matrix[k][k]
        for row in range(k + 1, size):
            for col in range(k + 1, size):
                matrix[row][col] = (pivot * matrix[row][col] - matrix[row][k] * matrix[k][col]) // divisor
            matrix[row][k] = 0
        divisor = pivot
    return matrix[-1][-1]


def count_local_contributions(revision: Revision) -> Evidence:
    terminals = revision.terminals.names
    wiring = revision.wiring
    islands = _local_islands(terminals + wiring.junctions, wiring.wires)
    boundary = set(terminals)
    groups = tuple(sorted(tuple(sorted(island & boundary)) for island in islands))
    count = prod(_tree_count(island, wiring.wires) for island in islands)
    return Evidence(((groups, count),))
