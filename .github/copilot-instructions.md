# GitHub Copilot Instructions
Project: retail-risk-augmentation-oss
Purpose: Kubernetes-first open-source reference implementation for retail banking risk augmentation.
Language: Python 3.11+ (ALL application logic must be Python)

Core capabilities:
- Transactional store: OSS Cassandra (required)
- Graph: JanusGraph backed by Cassandra (required) + optional NetworkX dev fallback
- Lakehouse: Apache Iceberg on MinIO (required) + optional Nessie catalog
- SQL analytics: Trino (Presto-compatible) querying Iceberg (required)
- Vector similarity: FAISS (preferred) with numpy fallback (required)
- Serving: FastAPI (API) + Streamlit (UI)
- Orchestration: Kubernetes (required); data generation + pipelines run as Jobs/CronJobs

This repo is the SOURCE OF TRUTH for:
- generator, scoring, vector embedding, graph modeling
- API contracts and UI behavior
- Presto/Trino SQL workbook
- Kubernetes manifests and job specs
- tests and local dev workflows

-------------------------------------------------------
NON-NEGOTIABLE REQUIREMENTS
-------------------------------------------------------
1) Must run in Kubernetes as the primary execution model.
2) Data generation MUST run as a Kubernetes Job:
   - generates X customers, Y transactions, Z injected suspicious patterns
3) Pipeline MUST run as a Kubernetes Job (and optionally CronJob):
   - scoring/alerts
   - embeddings + vector index build
   - graph loader into JanusGraph
   - curated Iceberg writes
4) Must provide:
   - unit tests (fast)
   - integration tests (docker/kind)
   - smoke tests for API endpoints

-------------------------------------------------------
KUBERNETES ARCHITECTURE
-------------------------------------------------------
Cluster services:
- Cassandra: StatefulSet + headless Service
- JanusGraph: Deployment + Service (uses Cassandra backend)
- MinIO: StatefulSet + Service (S3-compatible)
- Trino: Deployment + Service (coordinator is enough for demo)
- (Optional) Nessie: Deployment + Service (Iceberg catalog)
App services:
- FastAPI: Deployment + Service
- Streamlit: Deployment + Service
Jobs:
- generate-data Job
- run-pipeline Job
- (optional) refresh-views Job
CronJobs (optional):
- pipeline refresh schedule

All Kubernetes manifests must be under:
- `/k8s/base/*` and optional overlays under `/k8s/overlays/*`
Prefer Kustomize, but Helm charts are acceptable for third-party services (Cassandra/MinIO/Trino).

-------------------------------------------------------
EXECUTION MODES
-------------------------------------------------------
A) PRIMARY: Kubernetes execution
- Jobs run generator and pipeline
- Deploy API + UI
- Store data:
  - Cassandra for operational tables
  - Iceberg on MinIO for analytical tables
  - Vector index artifacts stored in MinIO (e.g., s3://demo/indices/...)

B) SECONDARY: Local developer mode (for fast iteration)
- Provide `docker compose` or `make dev` for services
- Provide CLI:
  - `python -m retail_risk_aug.cli generate ...`
  - `python -m retail_risk_aug.cli pipeline run-all`
  - `python -m retail_risk_aug.cli serve`
Local mode must mimic K8s job behavior and write to same backends.

-------------------------------------------------------
CONFIGURATION RULES
-------------------------------------------------------
- All configuration via env vars; no hardcoded endpoints.
- Use Pydantic Settings in `retail_risk_aug/config.py`.
- Provide `.env.template`.
- K8s ConfigMaps for non-secret config; Secrets for creds.

Required env vars (examples):
- CASSANDRA_CONTACT_POINTS
- CASSANDRA_USERNAME / CASSANDRA_PASSWORD
- JANUSGRAPH_GREMLIN_ENDPOINT
- MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
- ICEBERG_CATALOG_TYPE (nessie|jdbc|hms)
- TRINO_HOST, TRINO_PORT, TRINO_CATALOG, TRINO_SCHEMA
- VECTOR_INDEX_BUCKET_PATH
- MODEL_VERSION
- RNG_SEED

-------------------------------------------------------
CLI REQUIREMENTS
-------------------------------------------------------
Provide a CLI entrypoint:
- `python -m retail_risk_aug.cli generate --customers X --transactions Y --inject Z --seed N`
- `python -m retail_risk_aug.cli pipeline run-all`
- `python -m retail_risk_aug.cli serve`

These commands must be used by Kubernetes Jobs as the container command.

-------------------------------------------------------
DATA MODEL (CANONICAL)
-------------------------------------------------------
customers(
  customer_id, name, dob, segment, risk_band, home_geo
)
accounts(
  account_id, customer_id, opened_date, account_type
)
merchants(
  merchant_id, name, mcc, geo
)
devices(
  device_id, device_type
)
transactions(
  txn_id, ts, account_id, counterparty_account_id, merchant_id,
  amount, currency, channel, txn_type,
  device_id, ip, geo, narrative,
  is_injected, pattern_tag
)
alerts(
  case_id, txn_id, score, reason_codes,
  status, created_ts, resolution, resolution_ts
)
embeddings(
  embedding_id, entity_type, entity_id,
  vector, model_version, created_ts
)

-------------------------------------------------------
CASSANDRA TABLE GUIDELINES
-------------------------------------------------------
Operational tables optimized for reads:
- transactions_by_account ((account_id), ts DESC, txn_id, ...)
- transactions_by_merchant ((merchant_id), ts DESC, txn_id, ...)
- alerts_by_status ((status), created_ts DESC, case_id, score, txn_id, reason_codes, ...)
Include TTL optional for demo environments.

-------------------------------------------------------
SYNTHETIC DATA + INJECTION PATTERNS
-------------------------------------------------------
Generate baseline traffic:
- POS_PURCHASE
- ONLINE_PURCHASE
- P2P_TRANSFER
- BILL_PAYMENT

Injected suspicious patterns (Z total injections, traceable):
1) RING_TRANSFER: funnel or circular transfers in short window
2) SHARED_DEVICE: multiple customers share same device_id
3) SHARED_IP: multiple customers share same ip
4) MERCHANT_BURST: new merchant + velocity + high spend

Injected rows must include:
- is_injected = True
- pattern_tag in {RING_TRANSFER, SHARED_DEVICE, SHARED_IP, MERCHANT_BURST}
Also add `injection_group_id` to correlate related injected events.

-------------------------------------------------------
SCORING REQUIREMENTS (EXPLAINABLE)
-------------------------------------------------------
Deterministic heuristic scoring only:
- output `score` in [0,1]
- output `reason_codes` list[str]
Reason codes examples:
- NEW_DEVICE, AMOUNT_SPIKE, VELOCITY_SPIKE, SHARED_IP, SHARED_DEVICE, RING_TRANSFER, NEW_MERCHANT_BURST

Scoring must reliably flag the injected events.

-------------------------------------------------------
VECTOR REQUIREMENTS
-------------------------------------------------------
- Create embeddings for transactions and merchants using feature vectors.
- Store embeddings to Iceberg.
- Build FAISS index; fallback to numpy cosine similarity for small datasets.
- Persist FAISS index artifacts to MinIO:
  - indices/txn.index
  - indices/txn_ids.parquet
API must load/cache index on startup and support refresh.

Endpoints:
- GET /similar/transaction/{txn_id}?k=10
- GET /similar/merchant/{merchant_id}?k=10

-------------------------------------------------------
GRAPH REQUIREMENTS
-------------------------------------------------------
Vertices: Customer, Account, Merchant, Device, IP, Transaction
Edges:
- OWNS (Customer->Account)
- SENT_TO (Account->Account)
- PAID_AT (Account->Merchant)
- USES_DEVICE (Account->Device)
- SEEN_ON_IP (Device->IP)

Prefer JanusGraph Gremlin queries.
Only allow NetworkX fallback in explicit DEV mode.

Endpoints:
- GET /graph/txn/{txn_id}
- GET /graph/account/{account_id}/neighborhood?hops=2
- GET /graph/account/{account_id}/paths?to={account_id}&max_hops=4

-------------------------------------------------------
TRINO/PRESTO SQL WORKBOOK
-------------------------------------------------------
Provide Presto-compatible SQL files under `/retail_risk_aug/sql/`:
- vw_open_alerts_by_typology
- vw_top_risky_merchants
- vw_shared_device_hotspots
- vw_ring_transfer_candidates
- vw_daily_anomaly_trend

UI must show/copy SQL, and execute it if Trino is reachable.

-------------------------------------------------------
RISK CONSOLE UI (STREAMLIT)
-------------------------------------------------------
Must include investigation links for each alert:
- Investigate -> alert detail
- Similar -> vector top-K
- Graph -> neighborhood graph
- SQL -> show/copy + execute query

Screens:
1) Admin dashboard (counts, freshness, model_version, last job runs)
2) Alerts list (filter/sort)
3) Alert detail (reasons + txn + similar + graph + timeline)
4) Analyst workbook (browse SQL, execute, export CSV)

-------------------------------------------------------
TESTING REQUIREMENTS
-------------------------------------------------------
Testing pyramid:
1) Unit tests (fast; no external services):
   - generator: deterministic output with seed
   - scoring: injected events should score above threshold and include correct reason codes
   - vector: similarity returns expected neighbors for controlled fixtures
   - SQL: validate queries parse/contain expected fields (string tests) and optionally run via DuckDB in CI

2) Integration tests (services required):
   - Use Docker Compose OR kind-based tests
   - Validate:
     - generator writes to Cassandra and Iceberg/MinIO
     - pipeline writes alerts + embeddings and produces FAISS index in MinIO
     - API endpoints return 200 and non-empty responses

3) Smoke tests:
   - `GET /admin/health`
   - `GET /alerts?status=open`
   - `GET /alert/{case_id}`
   - `GET /similar/transaction/{txn_id}?k=5`
   - `GET /graph/txn/{txn_id}`

Tooling:
- pytest
- pytest-xdist optional
- httpx for API tests
- testcontainers-python optional for Cassandra/MinIO/Trino

Provide Makefile targets:
- `make test` (unit)
- `make test-integration` (requires services)
- `make k8s-up` (kind)
- `make k8s-deploy`
- `make k8s-generate`
- `make k8s-pipeline`
- `make k8s-smoke`

-------------------------------------------------------
DELIVERABLE QUALITY
-------------------------------------------------------
- Type hints everywhere
- Pydantic models for API IO
- Clear separation of concerns
- Structured logging
- Deterministic runs with seed
- Minimal but complete docs in `/docs`

This is a practical use case: prioritize reliability, clarity, and explainability.