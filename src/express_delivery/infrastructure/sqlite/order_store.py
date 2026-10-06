"""Implémentation SQLite de OrderStore (ADR-0001).

Une connexion par opération : sûr avec les threads de FastAPI, et le mode WAL
permet des lectures pendant une écriture.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from express_delivery.abstractions.order_store import OrderStore
from express_delivery.domain.models import Order, OrderStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id   TEXT PRIMARY KEY,
    features   TEXT NOT NULL,           -- JSON des 12 variables du modèle
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL            -- ISO 8601 UTC
);
"""


class SqliteOrderStore(OrderStore):
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path, timeout=5.0)

    def save(self, order: Order) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO orders (order_id, features, status, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    order.order_id,
                    json.dumps(dict(order.features)),
                    order.status.value,
                    order.created_at.isoformat(),
                ),
            )

    def get(self, order_id: str) -> Order | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT order_id, features, status, created_at FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        if row is None:
            return None
        return Order(
            order_id=row[0],
            features=json.loads(row[1]),
            status=OrderStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
        )

    def is_reachable(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
