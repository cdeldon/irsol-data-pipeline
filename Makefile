.PHONY: lint test help

help:
	@echo "Available targets:"
	@echo "  lint  - Run pre-commit checks"
	@echo "  test  - Run pytest with coverage"
	@echo "  clean - Removes temporary python artifacts"

lint:
	uv run pre-commit run --all-files

test:
	uv run pytest --cov=src --cov-report=html --cov-report=term tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete


.DEFAULT_GOAL := help
