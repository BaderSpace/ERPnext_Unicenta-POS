import logging

from src.erpnext.client import ERPNextClient
from src.sync.tracker import SyncTracker
from src.unicenta.db import UnicentaDB

logger = logging.getLogger(__name__)


def sync_products(unicenta: UnicentaDB, erpnext: ERPNextClient, tracker: SyncTracker | None = None) -> dict[str, int]:
    stats: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    categories = {c.id: c.name for c in unicenta.get_categories()}
    products = unicenta.get_products()

    existing_groups = set(erpnext.list_item_groups())
    for cat_name in categories.values():
        if cat_name not in existing_groups:
            try:
                erpnext.create_item_group(cat_name)
                existing_groups.add(cat_name)
                logger.info("Created Item Group: %s", cat_name)
            except Exception as e:
                logger.warning("Could not create Item Group %s: %s", cat_name, e)

    logger.info("Starting product sync: %d products from Unicenta", len(products))

    for prod in products:
        item_code = prod.reference or prod.code

        if tracker and tracker.is_item_synced(item_code):
            stats["skipped"] += 1
            continue

        try:
            existing = erpnext.find_item_by_code(item_code)
        except Exception as e:
            logger.error("Error checking item %s: %s", item_code, e)
            stats["errors"] += 1
            continue

        item_data = {
            "item_code": item_code,
            "item_name": prod.name,
            "item_group": categories.get(prod.category_id, "Products"),
            "stock_uom": "Nos",
            "is_stock_item": 0 if prod.is_service else 1,
            "is_service_item": 1 if prod.is_service else 0,
            "standard_rate": prod.price_sell,
            "valuation_rate": prod.price_buy if prod.price_buy else 0,
            "description": prod.name,
        }

        if prod.is_com:
            item_data["is_composite"] = 1

        try:
            if existing:
                erpnext.update_doc("Item", existing["name"], item_data)
                stats["updated"] += 1
                logger.debug("Updated item %s (%s)", item_code, prod.name)
            else:
                erpnext.create_item(item_data)
                stats["created"] += 1
                logger.debug("Created item %s (%s)", item_code, prod.name)
            if tracker:
                tracker.mark_item_synced(item_code, item_code)
        except Exception as e:
            logger.error("Error syncing item %s: %s", item_code, e)
            stats["errors"] += 1

    logger.info(
        "Product sync complete: %d created, %d updated, %d skipped, %d errors",
        stats["created"],
        stats["updated"],
        stats["skipped"],
        stats["errors"],
    )
    return stats
