from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class PatternTag(str, Enum):
    RING_TRANSFER = "RING_TRANSFER"
    SHARED_DEVICE = "SHARED_DEVICE"
    SHARED_IP = "SHARED_IP"
    MERCHANT_BURST = "MERCHANT_BURST"


class ReasonCode(str, Enum):
    NEW_DEVICE = "NEW_DEVICE"
    AMOUNT_SPIKE = "AMOUNT_SPIKE"
    VELOCITY_SPIKE = "VELOCITY_SPIKE"
    SHARED_IP = "SHARED_IP"
    SHARED_DEVICE = "SHARED_DEVICE"
    RING_TRANSFER = "RING_TRANSFER"
    NEW_MERCHANT_BURST = "NEW_MERCHANT_BURST"


class Customer(BaseModel):
    customer_id: str
    name: str
    dob: date
    segment: str
    risk_band: str
    home_geo: str


class Transaction(BaseModel):
    txn_id: str
    ts: datetime
    account_id: str
    counterparty_account_id: str | None = None
    merchant_id: str
    amount: float = Field(ge=0)
    currency: str = "USD"
    channel: str
    txn_type: str
    device_id: str
    ip: str
    geo: str
    narrative: str
    is_injected: bool = False
    pattern_tag: PatternTag | None = None
    injection_group_id: str | None = None


class Alert(BaseModel):
    case_id: str
    txn_id: str
    score: float = Field(ge=0, le=1)
    reason_codes: list[str]
    status: str = "open"
    created_ts: datetime
    resolution: str | None = None
    resolution_ts: datetime | None = None


class ScoredTransaction(BaseModel):
    txn_id: str
    score: float = Field(ge=0, le=1)
    reason_codes: list[str]


class SimilarResult(BaseModel):
    txn_id: str
    score: float


class GeneratedDataset(BaseModel):
    customers: list[Customer]
    transactions: list[Transaction]
