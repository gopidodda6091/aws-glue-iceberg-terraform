SHELL := /bin/bash
PYTHON ?= python3.11
VENV := .venv
BIN := $(VENV)/bin
TF ?= terraform
ENV_DIR := terraform/envs/dev
LOCALSTACK_ENV := AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1

.PHONY: help setup test lint data validate fmt plan-local localstack-up localstack-down clean

help:
	@echo "setup       create .venv and install pinned dev deps"
	@echo "test        pytest: Glue job transform logic on local PySpark"
	@echo "lint        ruff check"
	@echo "data        generate synthetic raw shipment events into data/raw"
	@echo "validate    terraform fmt -check, init -backend=false, validate, tflint"
	@echo "plan-local  terraform plan against LocalStack (docker compose)"
	@echo "clean       remove venv, terraform caches and generated files"

$(BIN)/activate: requirements-dev.txt
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements-dev.txt
	touch $(BIN)/activate

setup: $(BIN)/activate

test: setup
	$(BIN)/pytest

lint: setup
	$(BIN)/ruff check glue_jobs scripts tests
	$(BIN)/ruff format --check glue_jobs scripts tests

data: setup
	$(BIN)/python scripts/generate_shipments.py --out data/raw

fmt:
	$(TF) fmt -recursive terraform

validate:
	$(TF) fmt -check -recursive terraform
	$(TF) -chdir=$(ENV_DIR) init -backend=false -input=false
	$(TF) -chdir=$(ENV_DIR) validate
	tflint --init --config=$(CURDIR)/.tflint.hcl
	tflint --recursive --config=$(CURDIR)/.tflint.hcl

localstack-up:
	docker compose up -d --wait localstack

localstack-down:
	docker compose down -v

plan-local: localstack-up
	$(LOCALSTACK_ENV) $(TF) -chdir=$(ENV_DIR) init -backend=false -input=false
	$(LOCALSTACK_ENV) $(TF) -chdir=$(ENV_DIR) plan -input=false -lock=false -var use_localstack=true

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache spark-warehouse metastore_db derby.log data
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find terraform -name .terraform -type d -prune -exec rm -rf {} +
	find terraform -name .terraform.lock.hcl -delete
