from uuid import uuid4

from intake.inbox_store import InboxStore
from links.catalog import build_link_list
from links.catalog_store import CatalogStore
from links.endpoint_checks import check_link_endpoints


def freeze_links(inbox: InboxStore, catalog: CatalogStore, batch: str, rows: object) -> str:
    link_list = build_link_list(f'list-{uuid4().hex}', batch, rows)
    check_link_endpoints(link_list, inbox.get_manifest(link_list.batch))
    return catalog.save_list(link_list)
