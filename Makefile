.PHONY: install test lint migrate worker run
install:
	python -m pip install -r requirements.txt
run:
	python -m flask --app wsgi run --host 0.0.0.0 --port 8000
migrate:
	python -m flask --app wsgi db upgrade
worker:
	python -m flask --app wsgi worker
test:
	python -m pytest -q
lint:
	python -m ruff check app tests
