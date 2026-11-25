from dataclasses import dataclass
from hashlib import sha256

from intake.inbox_store import InboxStore, ReceiptRecord
from links.catalog import LinkList
from links.catalog_store import CatalogStore
from review.request import ReviewRequest


@dataclass(frozen=True, slots=True)
class ParentReference:
    receipt_id: str
    freeze_id: str
    station: str
    revision_id: str
    package_sha256: str

    @classmethod
    def from_receipt(cls, receipt: ReceiptRecord) -> 'ParentReference':
        package = receipt.envelope
        return cls(receipt.receipt_id, package.freeze_id, package.station,
                   package.revision_id, sha256(receipt.raw).hexdigest())


@dataclass(frozen=True, slots=True)
class BoundParents:
    receipts: tuple[ReceiptRecord, ReceiptRecord]
    link_list: LinkList
    selected: tuple[str, str]

    def references(self) -> tuple[ParentReference, ParentReference]:
        first, second = self.receipts
        return ParentReference.from_receipt(first), ParentReference.from_receipt(second)


def _require_receipt(inbox: InboxStore, receipt_id: str) -> ReceiptRecord:
    receipt = inbox.find_receipt(receipt_id)
    if receipt is None:
        raise LookupError(f'unknown station receipt: {receipt_id}')
    return receipt


def bind_review_parents(inbox: InboxStore, catalog: CatalogStore, request: ReviewRequest) -> BoundParents:
    first_id, second_id = request.receipt_ids
    first = _require_receipt(inbox, first_id)
    second = _require_receipt(inbox, second_id)
    link_list = catalog.find_list(request.list_id)
    if link_list is None:
        raise LookupError(f'unknown fixed link list: {request.list_id}')

    left, right = first.envelope, second.envelope
    if left.batch != link_list.batch or right.batch != link_list.batch or left.station == right.station:
        raise ValueError('review requires two different stations and a single batch')
    declared = {left.station: set(left.terminals.names), right.station: set(right.terminals.names)}
    if declared[left.station] != declared[right.station]:
        raise ValueError('received station packages disagree on public terminals')
    if not set(request.selected).issubset(link.link_id for link in link_list.links):
        raise ValueError('selected link numbers must belong to the fixed list')
    for link in link_list.links:
        for endpoint in (link.a, link.b):
            if endpoint.station not in declared or endpoint.terminal not in declared[endpoint.station]:
                raise ValueError(f'fixed list endpoint is absent from the selected receipts: {link.link_id}')
    return BoundParents((first, second), link_list, request.selected)
