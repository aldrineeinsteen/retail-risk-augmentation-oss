from __future__ import annotations

import argparse

import uvicorn

from retail_risk_aug.api.app import app as api_app
from retail_risk_aug.generator import generate_dataset
from retail_risk_aug.graph import build_graph
from retail_risk_aug.scoring import score_transactions
from retail_risk_aug.vector import build_index


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        dataset = generate_dataset(
            customers=args.customers,
            transactions=args.transactions,
            inject=args.inject,
            seed=args.seed,
        )
        injected_count = sum(1 for txn in dataset.transactions if txn.is_injected)
        print(f"Generated customers={len(dataset.customers)} transactions={len(dataset.transactions)} injected={injected_count}")
        return

    if args.command == "pipeline" and args.pipeline_command == "run-all":
        dataset = generate_dataset(
            customers=args.customers,
            transactions=args.transactions,
            inject=args.inject,
            seed=args.seed,
        )
        scored = score_transactions(dataset.transactions)
        index = build_index(dataset.transactions)
        graph = build_graph(dataset.transactions)
        print(
            "Pipeline completed "
            f"transactions={len(dataset.transactions)} "
            f"alerts={len([item for item in scored if item.score >= 0.5])} "
            f"vector_backend={index.backend} "
            f"graph_nodes={graph.graph.number_of_nodes()}"
        )
        return

    if args.command == "serve":
        if args.target == "api":
            uvicorn.run(api_app, host=args.host, port=args.port)
            return
        print("Run UI with: streamlit run retail_risk_aug/ui/app.py")
        return

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="retail-risk-aug")
    subparsers = parser.add_subparsers(dest="command")

    generate_parser = subparsers.add_parser("generate", help="Generate synthetic dataset")
    _add_generation_args(generate_parser)

    pipeline_parser = subparsers.add_parser("pipeline", help="Run local pipeline")
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command")
    run_all_parser = pipeline_subparsers.add_parser("run-all", help="Run scoring + vector + graph")
    _add_generation_args(run_all_parser)

    serve_parser = subparsers.add_parser("serve", help="Serve API or UI")
    serve_parser.add_argument("--target", choices=["api", "ui"], default="api")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    return parser


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--customers", type=int, default=100)
    parser.add_argument("--transactions", type=int, default=1000)
    parser.add_argument("--inject", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)


if __name__ == "__main__":
    main()
