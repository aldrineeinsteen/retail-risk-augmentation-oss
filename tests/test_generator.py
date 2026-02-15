from retail_risk_aug.generator import generate_dataset
from retail_risk_aug.models import PatternTag


def test_generator_is_deterministic_for_same_seed() -> None:
    first = generate_dataset(customers=20, transactions=120, inject=12, seed=123)
    second = generate_dataset(customers=20, transactions=120, inject=12, seed=123)

    assert first.model_dump() == second.model_dump()


def test_injected_events_are_flagged_with_required_fields() -> None:
    dataset = generate_dataset(customers=15, transactions=80, inject=16, seed=7)

    injected = [txn for txn in dataset.transactions if txn.is_injected]
    assert len(injected) == 16

    allowed = {
        PatternTag.RING_TRANSFER,
        PatternTag.SHARED_DEVICE,
        PatternTag.SHARED_IP,
        PatternTag.MERCHANT_BURST,
    }
    for txn in injected:
        assert txn.pattern_tag in allowed
        assert txn.injection_group_id is not None
