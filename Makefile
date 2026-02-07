.PHONY: help install dev-install test lint format type-check clean docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  install       - Install production dependencies"
	@echo "  dev-install   - Install development dependencies"
	@echo "  test          - Run tests with coverage"
	@echo "  lint          - Run linting checks"
	@echo "  format        - Format code with black"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  clean         - Remove build artifacts"
	@echo "  docker-up     - Start Docker services"
	@echo "  docker-down   - Stop Docker services"
	@echo "  migrate       - Run database migrations"

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements-dev.txt
	pre-commit install

test:
	pytest tests/ -v --cov=src/foundry --cov-report=term --cov-report=html

lint:
	ruff check src tests
	black --check src tests

format:
	black src tests
	ruff check --fix src tests

type-check:
	mypy src

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf htmlcov .coverage

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

migrate:
	alembic upgrade head
