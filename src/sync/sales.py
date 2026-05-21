import logging

from src.erpnext.client import ERPNextClient
from src.sync.tracker import SyncTracker
from src.unicenta.db import UnicentaDB
from src.unicenta.models import UnicentaTicket

logger = logging.getLogger(__name__)

TENDER_MAP = {
    "cash": "Cash",
    "card": "Bank",
    "credit card": "Bank",
    "debit card": "Bank",
    "cheque": "Bank",
    "check": "Bank",
    "mobile": "Bank",
    "credit": "Credit",
    "voucher": "Cash",
    "other": "Cash",
}


def _map_payment_mode(mode: str) -> str:
    key = mode.strip().lower()
    return TENDER_MAP.get(key, "Cash")


POS_CUSTOMER = "POS Customer"


def _ensure_pos_customer(erpnext: ERPNextClient) -> str:
    try:
        existing = erpnext.find_customer_by_name(POS_CUSTOMER)
        if existing:
            return existing["name"]
        cust_data = {
            "customer_name": POS_CUSTOMER,
            "customer_type": "Individual",
            "territory": "All Territories",
            "customer_group": "All Customer Groups",
        }
        new_cust = erpnext.create_customer(cust_data)
        logger.info("Created default POS Customer")
        return new_cust["name"]
    except Exception as e:
        logger.warning("Failed to ensure POS Customer, using fallback: %s", e)
        return POS_CUSTOMER


def _sync_customer(unicenta: UnicentaDB, erpnext: ERPNextClient, ticket) -> str:
    if not ticket.customer:
        return _ensure_pos_customer(erpnext)

    customer_name = ticket.customer.name
    try:
        existing = erpnext.find_customer_by_name(customer_name)
        if existing:
            return existing["name"]

        cust_data = {
            "customer_name": customer_name,
            "customer_type": "Company" if ticket.customer.tax_id else "Individual",
            "tax_id": ticket.customer.tax_id or "",
            "email_id": ticket.customer.email or "",
            "mobile_no": ticket.customer.phone or "",
            "city": ticket.customer.city or "",
            "territory": "All Territories",
            "customer_group": "All Customer Groups",
        }

        if ticket.customer.address:
            cust_data["primary_address"] = ticket.customer.address
            if ticket.customer.city:
                cust_data["primary_address"] += f", {ticket.customer.city}"

        new_cust = erpnext.create_customer(cust_data)
        logger.info("Created ERPNext customer: %s", customer_name)
        return new_cust["name"]
    except Exception as e:
        logger.warning("Error syncing customer %s, falling back to POS Customer: %s", customer_name, e)
        return _ensure_pos_customer(erpnext)


def _resolve_product_reference(unicenta: UnicentaDB, product_id: str | None) -> str | None:
    if not product_id:
        return None
    with unicenta.conn.cursor() as cur:
        cur.execute("SELECT REFERENCE FROM PRODUCTS WHERE ID = %s", (product_id,))
        row = cur.fetchone()
        return row["REFERENCE"] if row else None


REQUIRED_PAYMENT_MODES = {"Cash": "Cash", "Bank": "Bank", "Credit": "General"}


def _invoice_exists(erpnext: ERPNextClient, invoice_name: str, ticket_uuid: str, tracker: SyncTracker | None) -> bool:
    if tracker:
        mapped_name = tracker.get_invoice_erpnext_name(ticket_uuid)
        if mapped_name:
            try:
                doc = erpnext.get_doc("Sales Invoice", mapped_name)
                if doc:
                    return True
            except Exception:
                pass

    try:
        doc = erpnext.get_doc("Sales Invoice", invoice_name)
        if doc:
            if tracker:
                tracker.mark_invoice_synced(ticket_uuid, doc["name"])
            return True
    except Exception:
        pass

    return False


def _ensure_payment_modes(erpnext: ERPNextClient) -> set[str]:
    existing = set(erpnext.list_mode_of_payments())
    for name, kind in REQUIRED_PAYMENT_MODES.items():
        if name not in existing:
            try:
                erpnext.create_mode_of_payment(name, kind)
                existing.add(name)
                logger.info("Created Mode of Payment: %s", name)
            except Exception as e:
                logger.warning("Could not create Mode of Payment %s: %s", name, e)
    return existing


def sync_sales(unicenta: UnicentaDB, erpnext: ERPNextClient, since_days: int = 7, tracker: SyncTracker | None = None) -> dict[str, int]:
    stats: dict[str, int] = {"synced": 0, "skipped": 0, "errors": 0}

    _ensure_payment_modes(erpnext)

    tickets = unicenta.get_completed_tickets(since_days)
    logger.info("Starting sales sync: %d tickets since %d days", len(tickets), since_days)

    for ticket in tickets:
        try:
            ticket_uuid = str(ticket.id)
            ticket_number = f"POS-{ticket.ticket_id}"
            invoice_name = f"{ticket_number}-{ticket_uuid[:8]}"

            if _invoice_exists(erpnext, invoice_name, ticket_uuid, tracker):
                stats["skipped"] += 1
                continue

            customer_name = _sync_customer(unicenta, erpnext, ticket)

            items = []
            for line in ticket.lines:
                item_code = _resolve_product_reference(unicenta, line.product_id)

                if not item_code:
                    logger.warning("Skipping line with no product ref on ticket %s", ticket.id)
                    continue

                items.append({
                    "item_code": item_code,
                    "qty": line.units,
                    "rate": line.price,
                })

            if not items:
                stats["skipped"] += 1
                continue

            invoice_data = {
                "name": invoice_name,
                "idempotency_key": f"unicenta-{ticket.id}",
                "posting_date": ticket.date.strftime("%Y-%m-%d"),
                "posting_time": ticket.date.strftime("%H:%M:%S"),
                "customer": customer_name or "POS Customer",
                "items": items,
            }

            if ticket.payments:
                total_paid = ticket.gross_total
                payments_data = []
                for pmt in ticket.payments:
                    mode = _map_payment_mode(pmt.payment_method)
                    payments_data.append({
                        "mode_of_payment": mode,
                        "amount": pmt.total,
                    })
                invoice_data["payments"] = payments_data
                invoice_data["paid_amount"] = total_paid

            created = erpnext.create_sales_invoice(invoice_data)
            stats["synced"] += 1
            if tracker:
                tracker.mark_invoice_synced(ticket_uuid, created["name"])
            logger.info("Synced ticket %d as Sales Invoice %s", ticket.ticket_id, created.get("name", "?"))

        except Exception as e:
            logger.error("Error syncing ticket %s: %s", ticket.id, e)
            stats["errors"] += 1

    logger.info(
        "Sales sync complete: %d synced, %d skipped, %d errors",
        stats["synced"],
        stats["skipped"],
        stats["errors"],
    )
    return stats
