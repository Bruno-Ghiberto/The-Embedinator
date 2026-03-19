.PHONY: help setup build-rust dev-infra dev-backend dev-frontend dev up down pull-models test test-cov test-frontend clean clean-all

help:  ## Show all available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup:  ## Install all dependencies (Python pip, Node npm, Rust binary)
	pip install -r requirements.txt
	cd frontend && npm install
	$(MAKE) build-rust

build-rust:  ## Compile the Rust ingestion worker binary
	cd ingestion-worker && cargo build --release

dev-infra:  ## Start Qdrant + Ollama in Docker (infrastructure only, for dev mode)
	docker compose up -d qdrant ollama

dev-backend:  ## Start Python backend with hot reload (uvicorn --reload)
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## Start Next.js frontend with hot reload (next dev)
	cd frontend && npm run dev

dev: dev-infra  ## Start dev-infra then print instructions for backend + frontend
	@echo "Run in separate terminals: make dev-backend  /  make dev-frontend"

up:  ## Build and start all 4 production Docker services
	docker compose up --build -d

down:  ## Stop all Docker services
	docker compose down

pull-models:  ## Pull default Ollama models (qwen2.5:7b + nomic-embed-text)
	docker exec $$(docker compose ps -q ollama) ollama pull qwen2.5:7b
	docker exec $$(docker compose ps -q ollama) ollama pull nomic-embed-text

test:  ## Run backend tests (no coverage threshold)
	zsh scripts/run-tests-external.sh -n make-test --no-cov tests/

test-cov:  ## Run backend tests with >=80% coverage gate (exits non-zero if below threshold)
	zsh scripts/run-tests-external.sh -n make-test-cov tests/

test-frontend:  ## Run frontend tests (vitest)
	cd frontend && npm run test

clean:  ## Remove runtime data (data/ directory contents)
	rm -rf data/

clean-all: down  ## Full teardown: stop containers, remove volumes and build outputs
	docker compose down -v
	rm -rf data/ ingestion-worker/target/ frontend/.next/
