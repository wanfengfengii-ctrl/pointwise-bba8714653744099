from issue.evidence import Evidence
from survey.revisions import Revision
from survey.wiring import Wire


def determinant(matrix: list[list[int]]) -> int:
    """Exact integer determinant by fraction-free (Bareiss) elimination."""
    size = len(matrix)
    if size == 0:
        return 1
    working = [row[:] for row in matrix]
    sign = 1
    previous = 1
    for pivot_column in range(size - 1):
        if working[pivot_column][pivot_column] == 0:
            swap = next((row for row in range(pivot_column + 1, size)
                         if working[row][pivot_column] != 0), None)
            if swap is None:
                return 0
            working[pivot_column], working[swap] = working[swap], working[pivot_column]
            sign = -sign
        pivot = working[pivot_column][pivot_column]
        for row in range(pivot_column + 1, size):
            for column in range(pivot_column + 1, size):
                working[row][column] = (
                    working[row][column] * pivot
                    - working[row][pivot_column] * working[pivot_column][column]
                ) // previous
            working[row][pivot_column] = 0
        previous = pivot
    return sign * working[size - 1][size - 1]


def _laplacian(vertices: tuple[str, ...], wires: tuple[Wire, ...]) -> list[list[int]]:
    columns = {vertex: index for index, vertex in enumerate(vertices)}
    size = len(vertices)
    matrix = [[0] * size for _ in range(size)]
    for wire in wires:
        if wire.a == wire.b:
            continue  # a loop can never appear in an acyclic selection
        a, b = columns[wire.a], columns[wire.b]
        matrix[a][a] += 1
        matrix[b][b] += 1
        matrix[a][b] -= 1
        matrix[b][a] -= 1
    return matrix


def _mobius_coefficients(values: dict[int, int]) -> dict[int, int]:
    coefficients = {}
    for mask in range(1 << 3):
        total = 0
        subset = mask
        while True:
            total += (-1) ** (bin(mask).count('1') - bin(subset).count('1')) * values[subset]
            if subset == 0:
                break
            subset = (subset - 1) & mask
        coefficients[mask] = total
    return coefficients


def _forest_partitions(revision: Revision) -> tuple[tuple[tuple[tuple[str, ...], ...], int], ...]:
    terminals = revision.terminals.names
    vertices = terminals + revision.wiring.junctions
    laplacian = _laplacian(vertices, revision.wiring.wires)

    values = {}
    for mask in range(1 << 3):
        matrix = [row[:] for row in laplacian]
        for index in range(3):
            if mask >> index & 1:
                matrix[index][index] += 1
        values[mask] = determinant(matrix)

    # Coefficient c[mask] counts rooted forests whose chosen roots (one per
    # component) are exactly the terminals in ``mask``.  Solving the small
    # linear system recovers the count of forests per terminal partition.
    c = _mobius_coefficients(values)
    split = c[0b111]
    connected = c[0b001]
    ab = (c[0b101] + c[0b110] - c[0b011]) // 2
    ac = (c[0b011] + c[0b110] - c[0b101]) // 2
    bc = (c[0b011] + c[0b101] - c[0b110]) // 2

    first, second, third = terminals
    rows = {
        ((first,), (second,), (third,)): split,
        ((first, second), (third,)): ab,
        ((first, third), (second,)): ac,
        ((first,), (second, third)): bc,
        ((first, second, third),): connected,
    }
    return tuple(sorted((partition, count) for partition, count in rows.items() if count > 0))


def count_local_contributions(revision: Revision) -> Evidence:
    return Evidence(_forest_partitions(revision))
