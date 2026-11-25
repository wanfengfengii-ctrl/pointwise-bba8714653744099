import json
import sqlite3
from contextlib import closing
from pathlib import Path

from links.catalog import LinkList, build_link_list


class CatalogStore:
    def __init__(self, path: str | Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS link_lists (
                    id TEXT PRIMARY KEY, batch TEXT NOT NULL, links TEXT NOT NULL
                )
            ''')

    def save_list(self, link_list: LinkList) -> str:
        rows = [link.to_row() for link in link_list.links]
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO link_lists VALUES (?, ?, ?)',
                       (link_list.list_id, link_list.batch, json.dumps(rows)))
        return link_list.list_id

    def find_list(self, list_id: str) -> LinkList | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT batch, links FROM link_lists WHERE id = ?', (list_id,)).fetchone()
        if row is None:
            return None
        batch, links = row
        return build_link_list(list_id, batch, json.loads(links))
