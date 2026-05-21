from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UnicentaCategory:
    id: str
    name: str
    parent_id: Optional[str] = None


@dataclass
class UnicentaTax:
    id: str
    name: str
    category: str
    rate: float


@dataclass
class UnicentaProduct:
    id: str
    reference: str
    code: str
    code_type: Optional[str]
    name: str
    price_buy: float
    price_sell: float
    category_id: str
    category_name: Optional[str]
    tax_category_id: str
    is_com: bool
    is_scale: bool
    is_service: bool
    display: Optional[str]


@dataclass
class UnicentaCustomer:
    id: str
    search_key: str
    name: str
    tax_id: Optional[str]
    address: Optional[str]
    address2: Optional[str]
    city: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    phone2: Optional[str]
    firstname: Optional[str]
    lastname: Optional[str]


@dataclass
class UnicentaTicketLine:
    line: int
    product_id: Optional[str]
    product_name: Optional[str]
    units: float
    price: float
    tax_id: str
    tax_rate: float
    tax_name: Optional[str]


@dataclass
class UnicentaPayment:
    payment_id: str
    payment_method: str
    total: float


@dataclass
class UnicentaTaxLine:
    tax_id: str
    tax_name: Optional[str]
    base: float
    amount: float


@dataclass
class UnicentaTicket:
    id: str
    ticket_id: int
    ticket_type: int
    person: str
    customer: Optional[UnicentaCustomer]
    date: datetime
    status: int
    lines: list[UnicentaTicketLine]
    payments: list[UnicentaPayment]
    tax_lines: list[UnicentaTaxLine]

    @property
    def gross_total(self) -> float:
        return sum(p.total for p in self.payments)

    @property
    def net_total(self) -> float:
        return sum(l.price * l.units for l in self.lines)

    @property
    def tax_total(self) -> float:
        return sum(t.amount for t in self.tax_lines)
