# Suzerain Makefile
# "Whatever exists without my knowledge exists without my consent."

.PHONY: install dev test lint clean run wake help health

# Default target
help:
	@echo "Suzerain Commands"
	@echo "═══════════════════════════════════════════"
	@echo "  make install    Install dependencies"
	@echo "  make dev        Install in development mode"
	@echo "  make test       Run test suite"
	@echo "  make lint       Run linter"
	@echo "  make clean      Clear caches and build artifacts"
	@echo "  make run        Start push-to-talk mode"
	@echo "  make wake       Start wake word mode"
	@echo "  make health     Run health check"
	@echo "  make list       List grimoire commands"
	@echo "═══════════════════════════════════════════"

# Installation
install:
	@echo "Installing system dependencies..."
	brew install portaudio || true
	@echo "Installing Python dependencies..."
	pip install -e .

dev:
	@echo "Installing in development mode..."
	pip install -e ".[dev]"

# Testing
test:
	python -m pytest tests/ -v

test-fast:
	python -m pytest tests/ -v -x --tb=short

test-cov:
	python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Code quality
lint:
	@echo "Running ruff..."
	ruff check src/ tests/ || true
	@echo "Running type check..."
	mypy src/ --ignore-missing-imports || true

format:
	ruff format src/ tests/

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."

# Run modes
run:
	python src/main.py

wake:
	python src/main.py --wake

test-mode:
	python src/main.py --test

sandbox:
	python src/main.py --test --sandbox

# Utilities
list:
	python src/main.py --list

validate:
	python src/main.py --validate

health:
	python src/main.py --health 2>/dev/null || echo "Health check not yet implemented"

# Quick iterations
watch:
	@echo "Watching for changes..."
	watchmedo auto-restart --patterns="*.py;*.yaml" --recursive -- python src/main.py --test --sandbox

# Git shortcuts
commit:
	git add -A && git status

push:
	git push origin main
