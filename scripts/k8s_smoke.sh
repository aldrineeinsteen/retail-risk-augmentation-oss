#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:18000}"

echo "Smoke: GET /admin/health"
curl -fsS "${BASE_URL}/admin/health" >/dev/null

echo "Smoke: GET /alerts?status=open"
alerts_json="$(curl -fsS "${BASE_URL}/alerts?status=open")"

read -r case_id txn_id < <(printf '%s' "${alerts_json}" | python -c 'import json,sys; data=json.load(sys.stdin); print((data[0]["case_id"] if data else ""), (data[0]["txn_id"] if data else ""))')

if [[ -z "${case_id}" || -z "${txn_id}" ]]; then
  echo "Smoke failed: no open alerts returned"
  exit 1
fi

echo "Smoke: GET /alert/${case_id}"
curl -fsS "${BASE_URL}/alert/${case_id}" >/dev/null

echo "Smoke: GET /similar/transaction/${txn_id}?k=5"
curl -fsS "${BASE_URL}/similar/transaction/${txn_id}?k=5" >/dev/null

echo "Smoke: GET /graph/txn/${txn_id}"
curl -fsS "${BASE_URL}/graph/txn/${txn_id}" >/dev/null

echo "Smoke checks passed"
