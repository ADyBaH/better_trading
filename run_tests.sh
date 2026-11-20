.PHONY: test test-integration test-all

test:
	pytest tests/ -v -m "not integration"

test-integration:
	pytest tests/ -v -m integration

test-all:
	pytest tests/ -v -m ""