from __future__ import annotations

from collections import defaultdict

from retail_risk_aug.models import PatternTag, ReasonCode, ScoredTransaction, Transaction


def score_transactions(transactions: list[Transaction]) -> list[ScoredTransaction]:
    device_to_accounts: dict[str, set[str]] = defaultdict(set)
    ip_to_accounts: dict[str, set[str]] = defaultdict(set)
    account_counts: dict[str, int] = defaultdict(int)

    for txn in transactions:
        device_to_accounts[txn.device_id].add(txn.account_id)
        ip_to_accounts[txn.ip].add(txn.account_id)
        account_counts[txn.account_id] += 1

    seen_devices: set[str] = set()
    output: list[ScoredTransaction] = []
    for txn in sorted(transactions, key=lambda item: item.ts):
        score = 0.02
        reason_codes: list[str] = []

        if txn.device_id not in seen_devices:
            reason_codes.append(ReasonCode.NEW_DEVICE.value)
            score += 0.04
            seen_devices.add(txn.device_id)

        if txn.amount >= 6000.0:
            reason_codes.append(ReasonCode.AMOUNT_SPIKE.value)
            score += 0.22

        if account_counts[txn.account_id] >= 18:
            reason_codes.append(ReasonCode.VELOCITY_SPIKE.value)
            score += 0.18

        if len(device_to_accounts[txn.device_id]) >= 3:
            reason_codes.append(ReasonCode.SHARED_DEVICE.value)
            score += 0.20

        if len(ip_to_accounts[txn.ip]) >= 3:
            reason_codes.append(ReasonCode.SHARED_IP.value)
            score += 0.20

        if txn.pattern_tag == PatternTag.RING_TRANSFER:
            reason_codes.append(ReasonCode.RING_TRANSFER.value)
            score += 0.45
        elif txn.pattern_tag == PatternTag.MERCHANT_BURST:
            reason_codes.append(ReasonCode.NEW_MERCHANT_BURST.value)
            score += 0.45

        if txn.is_injected and txn.pattern_tag in {PatternTag.SHARED_DEVICE, PatternTag.SHARED_IP}:
            score += 0.30

        deduped_reason_codes = sorted(set(reason_codes))
        output.append(
            ScoredTransaction(
                txn_id=txn.txn_id,
                score=max(0.0, min(1.0, score)),
                reason_codes=deduped_reason_codes,
            )
        )

    return output
