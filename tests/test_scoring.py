from retail_risk_aug.generator import generate_dataset
from retail_risk_aug.scoring import score_transactions


def test_injected_transactions_score_higher_than_baseline() -> None:
    dataset = generate_dataset(customers=30, transactions=200, inject=40, seed=42)
    scored = {item.txn_id: item for item in score_transactions(dataset.transactions)}

    injected_scores = [scored[txn.txn_id].score for txn in dataset.transactions if txn.is_injected]
    baseline_scores = [scored[txn.txn_id].score for txn in dataset.transactions if not txn.is_injected]

    assert min(injected_scores) >= 0.2
    assert (sum(injected_scores) / len(injected_scores)) > (sum(baseline_scores) / len(baseline_scores))
    assert all(0.0 <= item.score <= 1.0 for item in scored.values())
