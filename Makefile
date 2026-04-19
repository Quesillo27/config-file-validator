.PHONY: install dev test lint docker setup clean

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt pytest
	pip install -e .

test:
	python3 -m pytest tests/ -v --tb=short

lint:
	python -m py_compile src/cli.py src/validators.py src/parsers.py src/diffing.py src/config.py src/logger.py
	@echo "Syntax OK"

docker:
	docker build -t config-file-validator .
	@echo "Run: docker run --rm -v \$$(pwd):/data config-file-validator validate /data/.env"

setup:
	bash setup.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache dist *.egg-info
