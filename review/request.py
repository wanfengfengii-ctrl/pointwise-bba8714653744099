from dataclasses import dataclass

from survey.terminals import validate_name


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    receipt_ids: tuple[str, str]
    list_id: str
    selected: tuple[str, str]


def _distinct_pair(items: object, label: str) -> tuple[str, str]:
    if not isinstance(items, (list, tuple)) or len(items) != 2:
        raise ValueError(f'exactly two {label} are required')
    first, second = (validate_name(item, label) for item in items)
    if first == second:
        raise ValueError(f'{label} must be distinct')
    return first, second


def validate_request(receipt_ids: object, list_id: str, selected: object) -> ReviewRequest:
    return ReviewRequest(
        _distinct_pair(receipt_ids, 'receipt numbers'),
        validate_name(list_id, 'fixed list number'),
        _distinct_pair(selected, 'selected link numbers'),
    )
