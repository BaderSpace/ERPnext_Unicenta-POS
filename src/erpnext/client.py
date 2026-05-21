import json
import logging
from typing import Any, Optional

import requests

from src.config import ERPNextConfig

logger = logging.getLogger(__name__)


class ERPNextClient:
    def __init__(self, config: ERPNextConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {config.api_key}:{config.api_secret}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.config.url}/api/resource/{path}"

    def _method_url(self, path: str) -> str:
        return f"{self.config.url}/api/method/{path}"

    def _request(self, method: str, url: str, **kwargs) -> dict:
        resp = self.session.request(method, url, timeout=60, **kwargs)
        if not resp.ok:
            logger.error("ERPNext API error %s %s: %s", method, url, resp.text)
            resp.raise_for_status()
        return resp.json()

    def get_list(self, doctype: str, fields: list[str] | None = None, filters: list | None = None, limit: int = 1000) -> list[dict]:
        params = {"limit_page_length": limit}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        url = self._url(doctype)
        resp = self.session.get(url, params=params, timeout=60)
        if not resp.ok:
            logger.error("ERPNext get_list error: %s", resp.text)
            resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def get_doc(self, doctype: str, name: str) -> Optional[dict]:
        try:
            resp = self.session.get(self._url(f"{doctype}/{name}"), timeout=60)
            if resp.status_code == 404:
                return None
            if not resp.ok:
                logger.error("ERPNext get_doc error: %s", resp.text)
                resp.raise_for_status()
            return resp.json().get("data")
        except requests.HTTPError:
            return None

    def create_doc(self, doctype: str, data: dict) -> dict:
        resp = self.session.post(self._url(doctype), json=data, timeout=60)
        if not resp.ok:
            logger.error("ERPNext create %s error: %s", doctype, resp.text)
            resp.raise_for_status()
        return resp.json().get("data", {})

    def update_doc(self, doctype: str, name: str, data: dict) -> dict:
        resp = self.session.put(self._url(f"{doctype}/{name}"), json=data, timeout=60)
        if not resp.ok:
            logger.error("ERPNext update %s error: %s", doctype, resp.text)
            resp.raise_for_status()
        return resp.json().get("data", {})

    def find_item_by_code(self, item_code: str) -> Optional[dict]:
        items = self.get_list("Item", filters=[["item_code", "=", item_code]], limit=1)
        return items[0] if items else None

    def find_customer_by_name(self, customer_name: str) -> Optional[dict]:
        customers = self.get_list("Customer", filters=[["customer_name", "=", customer_name]], limit=1)
        return customers[0] if customers else None

    def find_customer_by_erpnext_id(self, name: str) -> Optional[dict]:
        return self.get_doc("Customer", name)

    def create_item(self, item_data: dict) -> dict:
        return self.create_doc("Item", item_data)

    def create_customer(self, customer_data: dict) -> dict:
        return self.create_doc("Customer", customer_data)

    def create_sales_invoice(self, invoice_data: dict) -> dict:
        return self.create_doc("Sales Invoice", invoice_data)

    def find_tax_template(self, rate: float) -> Optional[str]:
        templates = self.get_list(
            "Item Tax Template",
            fields=["name", "taxes"],
            limit=100,
        )
        for t in templates:
            taxes = t.get("taxes", [])
            for tax in taxes:
                tax_rate = tax.get("tax_rate", 0)
                if abs(tax_rate - rate * 100) < 0.5:
                    return t["name"]
        return None

    def list_mode_of_payments(self) -> list[str]:
        mops = self.get_list("Mode of Payment", fields=["name"], limit=100)
        return [m["name"] for m in mops]

    def create_mode_of_payment(self, name: str, kind: str = "Cash") -> dict:
        data = {
            "mode_of_payment": name,
            "type": kind,
        }
        if kind == "Cash":
            data["custom_zatca_payment_means_code"] = "10"
        elif kind == "Credit":
            data["custom_zatca_payment_means_code"] = "30"
        else:
            data["custom_zatca_payment_means_code"] = "30"
        return self.create_doc("Mode of Payment", data)

    def list_item_groups(self) -> list[str]:
        groups = self.get_list("Item Group", fields=["name"], limit=1000)
        return [g["name"] for g in groups]

    def create_item_group(self, name: str, parent: str = "All Item Groups") -> dict:
        return self.create_doc("Item Group", {
            "item_group_name": name,
            "parent_item_group": parent,
            "is_group": 0,
        })
