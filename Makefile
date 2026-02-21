.PHONY: help install bundles serve test-local test-bundles clean

help:
	@echo "Available commands:"
	@echo "  make install         - Install Python dependencies"
	@echo "  make bundles         - Generate bundle recommendations (requires branch_item_sales.csv)"
	@echo "  make serve           - Run Flask server locally"
	@echo "  make test-local      - Test endpoints locally (requires server running)"
	@echo "  make test-bundles    - Test bundles endpoint"
	@echo "  make clean           - Remove __pycache__ and .pyc files"

install:
	pip install -r requirements.txt

bundles:
	python scripts/run_bundles.py

serve:
	python app.py

test-local:
	@echo "Testing /health..."
	@curl -s http://127.0.0.1:5001/health | python -m json.tool
	@echo "\nTesting /api/branches..."
	@curl -s http://127.0.0.1:5001/api/branches | python -m json.tool | head -50

test-bundles:
	@echo "Testing /api/bundles/1..."
	@curl -s http://127.0.0.1:5001/api/bundles/1 | python -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete || true
