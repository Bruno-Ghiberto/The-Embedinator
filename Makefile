.PHONY: dev build test lint docker-up docker-down clean

# Start all services in development mode with hot reload
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Build all Docker images
build:
	docker compose build

# Run test suite
test:
	pytest tests/ -v

# Run backend tests only
test-unit:
	pytest tests/unit/ -v

# Run integration tests
test-integration:
	pytest tests/integration/ -v

# Lint backend + frontend
lint:
	ruff check backend/ tests/
	cd frontend && npm run lint

# Format code
format:
	ruff format backend/ tests/

# Start Docker services (detached)
docker-up:
	docker compose up -d

# Stop Docker services
docker-down:
	docker compose down

# Stop and remove volumes (WARNING: removes data)
docker-clean:
	docker compose down -v

# View logs
logs:
	docker compose logs -f

# View backend logs
logs-backend:
	docker compose logs -f backend

# View frontend logs
logs-frontend:
	docker compose logs -f frontend

# Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
