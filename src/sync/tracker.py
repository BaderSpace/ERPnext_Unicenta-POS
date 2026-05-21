import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class SyncTracker:
    """Tracks which Unicenta records have been synced to ERPNext to prevent duplicates."""

    def __init__(self, path: str = "projects/sync_mapping.json"):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load sync mapping, starting fresh: %s", e)
        return {"items": {}, "invoices": {}}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def is_item_synced(self, item_code: str) -> bool:
        return item_code in self._data.get("items", {})

    def mark_item_synced(self, item_code: str, erpnext_name: str):
        self._data.setdefault("items", {})[item_code] = erpnext_name
        self.save()

    def get_item_erpnext_name(self, item_code: str) -> Optional[str]:
        return self._data.get("items", {}).get(item_code)

    def is_invoice_synced(self, ticket_id: str) -> bool:
        return ticket_id in self._data.get("invoices", {})

    def mark_invoice_synced(self, ticket_id: str, erpnext_name: str):
        self._data.setdefault("invoices", {})[ticket_id] = erpnext_name
        self.save()

    def get_invoice_erpnext_name(self, ticket_id: str) -> Optional[str]:
        return self._data.get("invoices", {}).get(ticket_id)