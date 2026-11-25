from dataclasses import dataclass

from survey.terminals import validate_name


@dataclass(frozen=True, slots=True)
class Endpoint:
    station: str
    terminal: str

    @classmethod
    def from_row(cls, row: object) -> 'Endpoint':
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('a link endpoint requires a station and public terminal')
        return cls(validate_name(row[0], 'endpoint station'), validate_name(row[1], 'endpoint terminal'))


@dataclass(frozen=True, slots=True)
class CrossLink:
    link_id: str
    a: Endpoint
    b: Endpoint

    def to_row(self) -> dict:
        return {'id': self.link_id, 'a': [self.a.station, self.a.terminal],
                'b': [self.b.station, self.b.terminal]}


@dataclass(frozen=True, slots=True)
class LinkList:
    list_id: str
    batch: str
    links: tuple[CrossLink, ...]


def build_link_list(list_id: str, batch: str, rows: object) -> LinkList:
    validate_name(list_id, 'list number')
    validate_name(batch, 'batch')
    if not isinstance(rows, (list, tuple)):
        raise ValueError('link list must be a sequence')
    links = []
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id', 'a', 'b'}:
            raise ValueError('a link requires its original number and two endpoints')
        link_id = validate_name(row['id'], 'link number')
        if link_id in ids:
            raise ValueError(f'duplicate link number: {link_id}')
        ids.add(link_id)
        links.append(CrossLink(link_id, Endpoint.from_row(row['a']), Endpoint.from_row(row['b'])))
    return LinkList(list_id, batch, tuple(links))
