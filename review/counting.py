from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from issue.evidence import Evidence
from review.parents import BoundParents


@dataclass(frozen=True, slots=True)
class ReviewCounts:
    total: int
    together: int

    def __post_init__(self) -> None:
        if type(self.total) is not int or type(self.together) is not int or not 0 <= self.together <= self.total:
            raise ValueError("report counts must be integers with 0 <= together <= total")


def _layouts(evidence: Evidence) -> tuple[tuple[tuple[tuple[str, ...], ...], int], ...]:
    # Every forest row is a distinct local selection; parallel original wires are
    # already folded into the row multiplicity, so none may be discarded.
    return evidence.forests


def _islands(groups: Iterable[Iterable[str]]) -> list[set[str]]:
    merged: list[set[str]] = []
    for group in groups:
        current = set(group)
        disjoint = []
        for island in merged:
            if current & island:
                current.update(island)
            else:
                disjoint.append(island)
        merged = [*disjoint, current]
    return merged


def _cross_links_needed(left_groups: int, right_groups: int) -> int:
    # A local forest with ``g`` components on three terminals plus its private
    # junctions uses ``three + junctions - g`` wires.  Writing ``J`` for the two
    # stations' private junction totals, a global scheme is a tree on ``3 + J``
    # vertices, so it needs ``2 + J`` wires in all.  The number of cross links is
    # therefore fixed by the two terminal counts and cannot be chosen freely:
    #   (3 - left) + (3 - right) + links = 2   ->   links = left + right - 4.
    return left_groups + right_groups - 4


def count_review(parents: BoundParents) -> ReviewCounts:
    first, second = (receipt.envelope for receipt in parents.receipts)
    first_layouts = _layouts(first.evidence)
    second_layouts = _layouts(second.evidence)
    selected = set(parents.selected)
    total = together = 0
    for left, left_count in first_layouts:
        for right, right_count in second_layouts:
            required = _cross_links_needed(len(left), len(right))
            if required < 0:
                continue  # too many local wires already: any union would cycle
            regions = _islands((*left, *right))
            if len(regions) - 1 != required:
                continue  # the fixed cross-link budget cannot join these regions
            multiplicity = left_count * right_count
            for chosen in combinations(parents.link_list.links, required):
                additions = tuple((link.a.terminal, link.b.terminal) for link in chosen)
                if len(_islands((*regions, *additions))) != 1:
                    continue
                total += multiplicity
                if selected.issubset(link.link_id for link in chosen):
                    together += multiplicity
    return ReviewCounts(total, together)
