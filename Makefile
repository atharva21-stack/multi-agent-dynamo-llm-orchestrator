.PHONY: setup dev test docker-build docker-up docker-down deploy lint format typecheck check clean

PYTHON := python3
PIP := pip3
APP_NAME := agent-inference-stack
DOCKER_REGISTRY := ghcr.io/your-org
VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "0.1.0")

# Setup
setup:
	$(PIP) install -r requirements-dev.txt
	cp -n .env.example .env || true
	@echo "Setup complete. Edit .env with your credentials."

# Development server
dev:
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# Run tests
test:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html -x

test-unit:
	pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

# Code quality
lint:
	ruff check src/ tests/
	pylint src/ --fail-under=8.0

format:
	black src/ tests/
	isort src/ tests/

typecheck:
	mypy src/ --ignore-missing-imports

check: format lint typecheck test

# Docker
docker-build:
	docker build -f docker/Dockerfile.api -t $(DOCKER_REGISTRY)/$(APP_NAME)-api:$(VERSION) .
	docker build -f docker/Dockerfile.agent -t $(DOCKER_REGISTRY)/$(APP_NAME)-agent:$(VERSION) .

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

docker-logs:
	docker-compose -f docker/docker-compose.yml logs -f

# Database migrations
db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

db-revision:
	alembic revision --autogenerate -m "$(msg)"

# Kubernetes deployment
deploy-dev:
	kubectl apply -f kubernetes/ -n agent-inference-stack-dev

deploy-prod:
	kubectl apply -f kubernetes/ -n agent-inference-stack-prod

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts."

# Help
help:
	@echo "Available targets:"
	@echo "  setup          - Install dependencies and configure environment"
	@echo "  dev            - Start development server"
	@echo "  test           - Run full test suite with coverage"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests"
	@echo "  lint           - Run linters"
	@echo "  format         - Format code with black and isort"
	@echo "  typecheck      - Run mypy type checking"
	@echo "  check          - Run all quality checks"
	@echo "  docker-build   - Build Docker images"
	@echo "  docker-up      - Start Docker Compose stack"
	@echo "  docker-down    - Stop Docker Compose stack"
	@echo "  deploy-dev     - Deploy to dev Kubernetes cluster"
	@echo "  deploy-prod    - Deploy to prod Kubernetes cluster"
	@echo "  clean          - Remove build artifacts"
