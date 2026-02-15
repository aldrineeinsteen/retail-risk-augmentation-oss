SHELL := /bin/bash

KIND ?= kind
KUBECTL ?= kubectl
DOCKER ?= docker
PYTHON ?= .venv/bin/python

KIND_CLUSTER_NAME ?= retail-risk-demo
KIND_CONFIG ?= k8s/kind-config.yaml
NAMESPACE ?= retail-risk
KUSTOMIZE_DIR ?= k8s/base
IMAGE_NAME ?= retail-risk-augmentation-oss:dev
API_PORT ?= 18000

.PHONY: help check-tools test test-integration k8s-up k8s-down k8s-build-image k8s-deploy k8s-generate k8s-pipeline k8s-smoke k8s-status

help:
	@echo "Targets:"
	@echo "  test               - run fast unit + smoke tests"
	@echo "  test-integration   - run integration scaffolding (RUN_INTEGRATION=1)"
	@echo "  k8s-up             - create kind cluster"
	@echo "  k8s-build-image    - build local image and load into kind"
	@echo "  k8s-deploy         - apply k8s/base and wait for core deployments"
	@echo "  k8s-generate       - run generate-data job"
	@echo "  k8s-pipeline       - run run-pipeline job"
	@echo "  k8s-smoke          - port-forward API and run smoke checks"
	@echo "  k8s-status         - show pods/jobs/services"
	@echo "  k8s-down           - delete kind cluster"

check-tools:
	@command -v $(KIND) >/dev/null 2>&1 || (echo "Missing tool: $(KIND)" && exit 1)
	@command -v $(KUBECTL) >/dev/null 2>&1 || (echo "Missing tool: $(KUBECTL)" && exit 1)
	@command -v $(DOCKER) >/dev/null 2>&1 || (echo "Missing tool: $(DOCKER)" && exit 1)

test:
	$(PYTHON) -m pytest -q

test-integration:
	RUN_INTEGRATION=1 $(PYTHON) -m pytest -q -m integration

k8s-up: check-tools
	@if $(KIND) get clusters | grep -q "^$(KIND_CLUSTER_NAME)$$"; then \
		echo "kind cluster '$(KIND_CLUSTER_NAME)' already exists"; \
	else \
		$(KIND) create cluster --name $(KIND_CLUSTER_NAME) --config $(KIND_CONFIG); \
	fi

k8s-down:
	@if $(KIND) get clusters | grep -q "^$(KIND_CLUSTER_NAME)$$"; then \
		$(KIND) delete cluster --name $(KIND_CLUSTER_NAME); \
	else \
		echo "kind cluster '$(KIND_CLUSTER_NAME)' not found"; \
	fi

k8s-build-image: check-tools
	$(DOCKER) build -t $(IMAGE_NAME) .
	$(KIND) load docker-image $(IMAGE_NAME) --name $(KIND_CLUSTER_NAME)

k8s-deploy:
	$(KUBECTL) apply -k $(KUSTOMIZE_DIR)
	$(KUBECTL) -n $(NAMESPACE) rollout status statefulset/cassandra --timeout=300s
	$(KUBECTL) -n $(NAMESPACE) rollout status statefulset/minio --timeout=300s
	$(KUBECTL) -n $(NAMESPACE) rollout status deployment/trino --timeout=300s
	$(KUBECTL) -n $(NAMESPACE) rollout status deployment/retail-risk-api --timeout=300s

k8s-generate:
	$(KUBECTL) -n $(NAMESPACE) delete job generate-data --ignore-not-found=true
	$(KUBECTL) apply -f k8s/base/job-generate-data.yaml
	$(KUBECTL) -n $(NAMESPACE) wait --for=condition=complete job/generate-data --timeout=600s

k8s-pipeline:
	$(KUBECTL) -n $(NAMESPACE) delete job run-pipeline --ignore-not-found=true
	$(KUBECTL) apply -f k8s/base/job-run-pipeline.yaml
	$(KUBECTL) -n $(NAMESPACE) wait --for=condition=complete job/run-pipeline --timeout=600s

k8s-smoke:
	@set -euo pipefail; \
	$(KUBECTL) -n $(NAMESPACE) port-forward svc/retail-risk-api $(API_PORT):8000 >/tmp/retail-risk-port-forward.log 2>&1 & \
	PF_PID=$$!; \
	trap 'kill $$PF_PID >/dev/null 2>&1 || true' EXIT; \
	sleep 4; \
	bash scripts/k8s_smoke.sh http://127.0.0.1:$(API_PORT)

k8s-status:
	$(KUBECTL) -n $(NAMESPACE) get pods
	$(KUBECTL) -n $(NAMESPACE) get jobs
	$(KUBECTL) -n $(NAMESPACE) get svc
