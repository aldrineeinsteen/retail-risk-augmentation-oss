from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from retail_risk_aug.models import SimilarResult, Transaction

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


CHANNELS = ["POS", "ONLINE", "MOBILE", "BRANCH"]
TXN_TYPES = ["POS_PURCHASE", "ONLINE_PURCHASE", "P2P_TRANSFER", "BILL_PAYMENT"]


@dataclass(slots=True)
class TransactionVectorIndex:
    txn_ids: list[str]
    vectors: np.ndarray
    backend: str
    id_to_position: dict[str, int]
    faiss_index: Any | None = None

    def search_similar(self, txn_id: str, k: int) -> list[SimilarResult]:
        if txn_id not in self.id_to_position:
            return []

        position = self.id_to_position[txn_id]
        query = self.vectors[position : position + 1]

        if self.backend == "faiss" and self.faiss_index is not None:
            scores, indices = self.faiss_index.search(query, min(k + 1, len(self.txn_ids)))
            output: list[SimilarResult] = []
            for score, index in zip(scores[0], indices[0], strict=False):
                if index < 0:
                    continue
                candidate_id = self.txn_ids[int(index)]
                if candidate_id == txn_id:
                    continue
                output.append(SimilarResult(txn_id=candidate_id, score=float(score)))
                if len(output) >= k:
                    break
            return output

        dot_products = self.vectors @ query.T
        similarities = dot_products.reshape(-1)
        ranked_indices = np.argsort(-similarities)
        output = []
        for index in ranked_indices:
            candidate_id = self.txn_ids[int(index)]
            if candidate_id == txn_id:
                continue
            output.append(SimilarResult(txn_id=candidate_id, score=float(similarities[int(index)])))
            if len(output) >= k:
                break
        return output


def build_index(transactions: list[Transaction]) -> TransactionVectorIndex:
    txn_ids = [txn.txn_id for txn in transactions]
    vectors = np.vstack([_embed_transaction(txn) for txn in transactions]).astype(np.float32)
    vectors = _normalize(vectors)
    id_to_position = {txn_id: index for index, txn_id in enumerate(txn_ids)}

    if faiss is not None:
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return TransactionVectorIndex(
            txn_ids=txn_ids,
            vectors=vectors,
            backend="faiss",
            id_to_position=id_to_position,
            faiss_index=index,
        )

    return TransactionVectorIndex(
        txn_ids=txn_ids,
        vectors=vectors,
        backend="numpy",
        id_to_position=id_to_position,
    )


def search_similar(index: TransactionVectorIndex, txn_id: str, k: int) -> list[SimilarResult]:
    return index.search_similar(txn_id=txn_id, k=k)


def _embed_transaction(txn: Transaction) -> np.ndarray:
    channel_vec = [1.0 if txn.channel == channel else 0.0 for channel in CHANNELS]
    txn_type_vec = [1.0 if txn.txn_type == txn_type else 0.0 for txn_type in TXN_TYPES]
    amount_feature = min(txn.amount / 10000.0, 1.0)
    injected_feature = 1.0 if txn.is_injected else 0.0

    return np.array([
        amount_feature,
        injected_feature,
        *channel_vec,
        *txn_type_vec,
    ])


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms
