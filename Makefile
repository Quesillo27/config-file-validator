.PHONY: install run test lint

install:
	pip install -r requirements.txt

run:
	python -m src.cli --help

test:
	python3 -m pytest tests/ -v --tb=short

lint:
	python -m py_compile src/cli.py src/validators.py src/parsers.py
	echo "Syntax OK"
