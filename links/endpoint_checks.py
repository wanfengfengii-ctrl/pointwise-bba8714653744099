from intake.manifest import BatchManifest
from links.catalog import LinkList


def check_link_endpoints(link_list: LinkList, manifest: BatchManifest) -> None:
    if link_list.batch != manifest.batch:
        raise ValueError('link list and batch manifest disagree')
    for link in link_list.links:
        for endpoint in (link.a, link.b):
            entry = manifest.find_station(endpoint.station)
            if entry is None or endpoint.terminal not in entry.terminals.names:
                raise ValueError(f'unknown public endpoint on {link.link_id}: {endpoint}')
