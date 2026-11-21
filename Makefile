.PHONY: up down build test

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

test:
	python -m pytest backend/tests -v
