#!/usr/bin/env python3
"""
Unicenta POS → ERPNext Integration
Syncs products and sales from Unicenta POS to ERPNext via REST API.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from src.config import AppConfig
from src.erpnext.client import ERPNextClient
from src.sync.products import sync_products
from src.sync.sales import sync_sales
from src.sync.tracker import SyncTracker
from src.unicenta.db import UnicentaDB

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("unicenta-erpnext")


def main():
    parser = argparse.ArgumentParser(
        description="Sync Unicenta POS data to ERPNext"
    )
    parser.add_argument(
        "--sync",
        choices=["products", "sales", "all"],
        default="all",
        help="What to sync (default: all)",
    )
    parser.add_argument(
        "--sales-since",
        type=int,
        default=None,
        help="Sync sales from last N days (overrides env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read data but do not push to ERPNext",
    )
    args = parser.parse_args()

    config = AppConfig.from_env()

    has_erpnext_creds = bool(config.erpnext.url and config.erpnext.api_key and config.erpnext.api_secret)

    if not has_erpnext_creds and not args.dry_run:
        logger.error(
            "ERPNext credentials not configured. "
            "Set ERPNEXT_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET in .env"
        )
        sys.exit(1)

    unicenta = UnicentaDB(config.unicenta_db)
    erpnext = ERPNextClient(config.erpnext) if has_erpnext_creds else None
    tracker = SyncTracker() if not args.dry_run else None

    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")

    try:
        unicenta.connect()

        if args.sync in ("all", "products"):
            logger.info("=" * 60)
            logger.info("SYNC PHASE 1: Products")
            logger.info("=" * 60)
            if not args.dry_run:
                stats = sync_products(unicenta, erpnext, tracker=tracker)
                logger.info("Product sync stats: %s", stats)
            else:
                products = unicenta.get_products()
                categories = unicenta.get_categories()
                logger.info("Would sync %d products across %d categories", len(products), len(categories))

        if args.sync in ("all", "sales"):
            logger.info("=" * 60)
            logger.info("SYNC PHASE 2: Sales Invoices")
            logger.info("=" * 60)
            since_days = args.sales_since or config.sync.sales_since_days
            if not args.dry_run:
                stats = sync_sales(unicenta, erpnext, since_days=since_days, tracker=tracker)
                logger.info("Sales sync stats: %s", stats)
            else:
                tickets = unicenta.get_completed_tickets(since_days)
                total_lines = sum(len(t.lines) for t in tickets)
                logger.info(
                    "Would sync %d tickets (%d lines, %d payments)",
                    len(tickets),
                    total_lines,
                    sum(len(t.payments) for t in tickets),
                )

        logger.info("=" * 60)
        logger.info("SYNC COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("Sync failed: %s", e)
        sys.exit(1)
    finally:
        unicenta.close()


if __name__ == "__main__":
    main()
