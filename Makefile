.PHONY: up down migrate seed test

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	alembic upgrade head

makemigrations:
	alembic revision --autogenerate -m "$(MSG)"

seed:
	python -m scripts.seed

test:
	pytest
