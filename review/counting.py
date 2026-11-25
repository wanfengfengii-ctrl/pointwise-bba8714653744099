from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from issue.evidence import Evidence, Partition
from review.parents import BoundParents


@dataclass(frozen=True, slots=True)
class ReviewCounts:
    total: int
    together: int

    def __post_init__(self) -> None:
        if type(self.total) is not int or type(self.together) is not int or not 0 <= self.together <= self.total:
            raise ValueError("report counts must be integers with 0 <= together <= total")


def _completed_layouts(evidence: Evidence) -> tuple[tuple[Partition, int], ...]:
    minimum_groups = min(len(groups) for groups, _ in evidence.forests)
    return tuple((groups, count) for groups, count in evidence.forests
                 if len(groups) == minimum_groups)


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


def count_review(parents: BoundParents) -> ReviewCounts:
    first, second = (receipt.envelope for receipt in parents.receipts)
    first_layouts = _completed_layouts(first.evidence)
    second_layouts = _completed_layouts(second.evidence)
    selected = set(parents.selected)
    total = together = 0
    for left, left_count in first_layouts:
        for right, right_count in second_layouts:
            regions = _islands((*left, *right))
            multiplicity = left_count * right_count
            for chosen in combinations(parents.link_list.links, len(regions) - 1):
                additions = tuple((link.a.terminal, link.b.terminal) for link in chosen)
                if len(_islands((*regions, *additions))) != 1:
                    continue
                total += multiplicity
                if selected.issubset(link.link_id for link in chosen):
                    together += multiplicity
    return ReviewCounts(total, together)
