import logging
from datetime import datetime, timedelta
from typing import Optional

import pymysql

from src.config import UnicentaDBConfig
from src.unicenta.models import (
    UnicentaCategory,
    UnicentaCustomer,
    UnicentaPayment,
    UnicentaProduct,
    UnicentaTax,
    UnicentaTaxLine,
    UnicentaTicket,
    UnicentaTicketLine,
)

logger = logging.getLogger(__name__)


class UnicentaDB:
    def __init__(self, config: UnicentaDBConfig):
        self.config = config
        self._conn: Optional[pymysql.Connection] = None

    def connect(self):
        self._conn = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset="utf8",
            cursorclass=pymysql.cursors.DictCursor,
        )
        logger.info("Connected to Unicenta MySQL at %s:%s", self.config.host, self.config.port)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Unicenta DB connection closed")

    @property
    def conn(self) -> pymysql.Connection:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn

    def get_categories(self) -> list[UnicentaCategory]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT ID, NAME, PARENTID FROM CATEGORIES ORDER BY NAME")
            return [
                UnicentaCategory(id=r["ID"], name=r["NAME"], parent_id=r.get("PARENTID"))
                for r in cur.fetchall()
            ]

    def get_taxes(self) -> list[UnicentaTax]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT ID, NAME, CATEGORY, RATE FROM TAXES ORDER BY NAME")
            return [
                UnicentaTax(id=r["ID"], name=r["NAME"], category=r["CATEGORY"], rate=r["RATE"])
                for r in cur.fetchall()
            ]

    def get_products(self) -> list[UnicentaProduct]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT p.ID, p.REFERENCE, p.CODE, p.CODETYPE, p.NAME,
                       p.PRICEBUY, p.PRICESELL,
                       p.CATEGORY, c.NAME AS CATEGORY_NAME,
                       p.TAXCAT, p.ISCOM, p.ISSCALE, p.ISSERVICE, p.DISPLAY
                FROM PRODUCTS p
                LEFT JOIN CATEGORIES c ON c.ID = p.CATEGORY
                ORDER BY p.NAME
            """)
            return [
                UnicentaProduct(
                    id=r["ID"],
                    reference=r["REFERENCE"],
                    code=r["CODE"],
                    code_type=r.get("CODETYPE"),
                    name=r["NAME"],
                    price_buy=r["PRICEBUY"] or 0.0,
                    price_sell=r["PRICESELL"] or 0.0,
                    category_id=r["CATEGORY"],
                    category_name=r.get("CATEGORY_NAME"),
                    tax_category_id=r["TAXCAT"],
                    is_com=bool(r["ISCOM"]),
                    is_scale=bool(r["ISSCALE"]),
                    is_service=bool(r["ISSERVICE"]),
                    display=r.get("DISPLAY"),
                )
                for r in cur.fetchall()
            ]

    def get_customers(self) -> list[UnicentaCustomer]:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT ID, SEARCHKEY, NAME, TAXID, ADDRESS, ADDRESS2,
                       CITY, EMAIL, PHONE, PHONE2, FIRSTNAME, LASTNAME
                FROM CUSTOMERS
                WHERE VISIBLE = 1
                ORDER BY NAME
            """)
            return [
                UnicentaCustomer(
                    id=r["ID"],
                    search_key=r["SEARCHKEY"],
                    name=r["NAME"],
                    tax_id=r.get("TAXID"),
                    address=r.get("ADDRESS"),
                    address2=r.get("ADDRESS2"),
                    city=r.get("CITY"),
                    email=r.get("EMAIL"),
                    phone=r.get("PHONE"),
                    phone2=r.get("PHONE2"),
                    firstname=r.get("FIRSTNAME"),
                    lastname=r.get("LASTNAME"),
                )
                for r in cur.fetchall()
            ]

    def get_completed_tickets(self, since_days: int = 7) -> list[UnicentaTicket]:
        cutoff = datetime.now() - timedelta(days=since_days)
        return self._fetch_tickets(cutoff)

    def get_tickets_since(self, since: datetime) -> list[UnicentaTicket]:
        return self._fetch_tickets(since)

    def _fetch_tickets(self, since: datetime) -> list[UnicentaTicket]:
        tickets = []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.ID, r.DATENEW, r.PERSON,
                       t.TICKETTYPE, t.TICKETID, t.CUSTOMER, t.STATUS
                FROM RECEIPTS r
                INNER JOIN TICKETS t ON t.ID = r.ID
                WHERE r.DATENEW >= %s
                ORDER BY r.DATENEW
                """,
                (since,),
            )
            ticket_rows = cur.fetchall()

            for tr in ticket_rows:
                ticket_id = tr["ID"]
                customer = None
                if tr.get("CUSTOMER"):
                    customer = self._get_customer(tr["CUSTOMER"])

                lines = self._get_ticket_lines(ticket_id)
                payments = self._get_payments(ticket_id)
                tax_lines = self._get_tax_lines(ticket_id)

                tickets.append(
                    UnicentaTicket(
                        id=ticket_id,
                        ticket_id=tr["TICKETID"],
                        ticket_type=tr["TICKETTYPE"],
                        person=tr["PERSON"],
                        customer=customer,
                        date=tr["DATENEW"],
                        status=tr["STATUS"],
                        lines=lines,
                        payments=payments,
                        tax_lines=tax_lines,
                    )
                )
        logger.info("Fetched %d completed tickets since %s", len(tickets), since)
        return tickets

    def _get_customer(self, customer_id: str) -> Optional[UnicentaCustomer]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT ID, SEARCHKEY, NAME, TAXID, ADDRESS, ADDRESS2,
                       CITY, EMAIL, PHONE, PHONE2, FIRSTNAME, LASTNAME
                FROM CUSTOMERS WHERE ID = %s
                """,
                (customer_id,),
            )
            r = cur.fetchone()
            if r:
                return UnicentaCustomer(
                    id=r["ID"],
                    search_key=r["SEARCHKEY"],
                    name=r["NAME"],
                    tax_id=r.get("TAXID"),
                    address=r.get("ADDRESS"),
                    address2=r.get("ADDRESS2"),
                    city=r.get("CITY"),
                    email=r.get("EMAIL"),
                    phone=r.get("PHONE"),
                    phone2=r.get("PHONE2"),
                    firstname=r.get("FIRSTNAME"),
                    lastname=r.get("LASTNAME"),
                )
        return None

    def _get_ticket_lines(self, ticket_id: str) -> list[UnicentaTicketLine]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT tl.LINE, tl.PRODUCT, p.NAME AS PRODUCT_NAME,
                       tl.UNITS, tl.PRICE, tl.TAXID, tx.RATE, tx.NAME AS TAX_NAME
                FROM TICKETLINES tl
                LEFT JOIN PRODUCTS p ON p.ID = tl.PRODUCT
                LEFT JOIN TAXES tx ON tx.ID = tl.TAXID
                WHERE tl.TICKET = %s
                ORDER BY tl.LINE
                """,
                (ticket_id,),
            )
            return [
                UnicentaTicketLine(
                    line=r["LINE"],
                    product_id=r.get("PRODUCT"),
                    product_name=r.get("PRODUCT_NAME"),
                    units=r["UNITS"],
                    price=r["PRICE"],
                    tax_id=r["TAXID"],
                    tax_rate=r["RATE"],
                    tax_name=r.get("TAX_NAME"),
                )
                for r in cur.fetchall()
            ]

    def _get_payments(self, ticket_id: str) -> list[UnicentaPayment]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT ID, PAYMENT, TOTAL
                FROM PAYMENTS
                WHERE RECEIPT = %s
                """,
                (ticket_id,),
            )
            return [
                UnicentaPayment(
                    payment_id=r["ID"],
                    payment_method=r["PAYMENT"],
                    total=r["TOTAL"],
                )
                for r in cur.fetchall()
            ]

    def _get_tax_lines(self, ticket_id: str) -> list[UnicentaTaxLine]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT tl.TAXID, tx.NAME AS TAX_NAME, tl.BASE, tl.AMOUNT
                FROM TAXLINES tl
                LEFT JOIN TAXES tx ON tx.ID = tl.TAXID
                WHERE tl.RECEIPT = %s
                """,
                (ticket_id,),
            )
            return [
                UnicentaTaxLine(
                    tax_id=r["TAXID"],
                    tax_name=r.get("TAX_NAME"),
                    base=r["BASE"],
                    amount=r["AMOUNT"],
                )
                for r in cur.fetchall()
            ]
