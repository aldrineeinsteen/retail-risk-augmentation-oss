from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from retail_risk_aug.models import Customer, GeneratedDataset, PatternTag, Transaction


SEGMENTS = ["mass", "affluent", "small_business"]
RISK_BANDS = ["low", "medium", "high"]
GEOS = ["US-NY", "US-CA", "US-TX", "US-FL"]
CHANNELS = ["POS", "ONLINE", "MOBILE", "BRANCH"]
TXN_TYPES = ["POS_PURCHASE", "ONLINE_PURCHASE", "P2P_TRANSFER", "BILL_PAYMENT"]


def generate_dataset(
    customers: int,
    transactions: int,
    inject: int,
    seed: int,
) -> GeneratedDataset:
    if customers <= 0:
        raise ValueError("customers must be > 0")
    if transactions <= 0:
        raise ValueError("transactions must be > 0")
    if inject < 0:
        raise ValueError("inject must be >= 0")
    if inject > transactions:
        raise ValueError("inject cannot exceed transactions")

    rng = random.Random(seed)
    generated_customers = _generate_customers(customers, rng)
    account_ids = [f"A{index:05d}" for index in range(1, customers + 1)]
    merchant_ids = [f"M{index:04d}" for index in range(1, max(10, customers // 2) + 1)]

    rows: list[Transaction] = []
    base_ts = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    for index in range(transactions):
        account_id = account_ids[index % len(account_ids)]
        counterparty = account_ids[(index + 7) % len(account_ids)]
        if counterparty == account_id:
            counterparty = None

        rows.append(
            Transaction(
                txn_id=f"T{index + 1:07d}",
                ts=base_ts + timedelta(minutes=index),
                account_id=account_id,
                counterparty_account_id=counterparty,
                merchant_id=rng.choice(merchant_ids),
                amount=round(rng.uniform(8.0, 850.0), 2),
                currency="USD",
                channel=rng.choice(CHANNELS),
                txn_type=rng.choice(TXN_TYPES),
                device_id=f"D{rng.randint(1, customers * 2):05d}",
                ip=f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                geo=rng.choice(GEOS),
                narrative="baseline synthetic transaction",
            )
        )

    _inject_patterns(rows, inject, rng, account_ids)
    return GeneratedDataset(customers=generated_customers, transactions=rows)


def _generate_customers(count: int, rng: random.Random) -> list[Customer]:
    output: list[Customer] = []
    for index in range(count):
        customer_number = index + 1
        output.append(
            Customer(
                customer_id=f"C{customer_number:05d}",
                name=f"Customer {customer_number}",
                dob=date(1970 + (customer_number % 25), ((customer_number % 12) + 1), ((customer_number % 27) + 1)),
                segment=rng.choice(SEGMENTS),
                risk_band=rng.choice(RISK_BANDS),
                home_geo=rng.choice(GEOS),
            )
        )
    return output


def _inject_patterns(rows: list[Transaction], inject: int, rng: random.Random, account_ids: list[str]) -> None:
    if inject == 0:
        return

    selected_indices = sorted(rng.sample(range(len(rows)), inject))
    patterns = [
        PatternTag.RING_TRANSFER,
        PatternTag.SHARED_DEVICE,
        PatternTag.SHARED_IP,
        PatternTag.MERCHANT_BURST,
    ]

    for injection_number, row_index in enumerate(selected_indices):
        pattern = patterns[injection_number % len(patterns)]
        row = rows[row_index]
        row.is_injected = True
        row.pattern_tag = pattern
        row.injection_group_id = f"IG-{injection_number // len(patterns) + 1:04d}"

        if pattern == PatternTag.RING_TRANSFER:
            row.txn_type = "P2P_TRANSFER"
            row.channel = "MOBILE"
            row.counterparty_account_id = account_ids[(row_index + 1) % len(account_ids)]
            row.amount = 1800.0 + (injection_number % 5) * 175.0
            row.narrative = "Injected ring transfer pattern"
        elif pattern == PatternTag.SHARED_DEVICE:
            row.device_id = "D-SHARED-0001"
            row.channel = "ONLINE"
            row.narrative = "Injected shared device pattern"
        elif pattern == PatternTag.SHARED_IP:
            row.ip = "172.16.10.10"
            row.channel = "ONLINE"
            row.narrative = "Injected shared IP pattern"
        elif pattern == PatternTag.MERCHANT_BURST:
            row.merchant_id = "M-BURST-0001"
            row.amount = 7000.0 + (injection_number % 7) * 225.0
            row.channel = "POS"
            row.txn_type = "POS_PURCHASE"
            row.narrative = "Injected merchant burst pattern"
