# Developer shortcuts. On Windows without make, run the commands shown in README.md directly.
.PHONY: setup db api worker web migrate bootstrap seed-demo admin test test-api test-web lint build up down

setup:            ## install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync
	cd frontend && npm ci
	@test -f backend/.env || cp backend/.env.example backend/.env

db:               ## start the local PostgreSQL container
	docker compose up -d --wait

migrate:          ## apply database migrations
	cd backend && uv run python -m app.cli migrate

bootstrap:        ## sync permission catalogue, roles and reference data (safe to repeat)
	cd backend && uv run python -m app.cli bootstrap

seed-demo:        ## load the demo campus and demo accounts (development only)
	cd backend && uv run python -m app.cli seed-demo

admin:            ## create a super administrator (reads SIMS_BOOTSTRAP_ADMIN_* or prompts)
	cd backend && uv run python -m app.cli create-admin

api:              ## run the API with auto-reload on http://127.0.0.1:8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

worker:           ## run the background job worker
	cd backend && uv run python -m app.cli worker

web:              ## run the UI dev server on http://localhost:5173 (proxies /api to the API)
	cd frontend && npm run dev

test: test-api test-web

test-api:
	cd backend && uv run pytest -q

test-web:
	cd frontend && npm test

loadtest:         ## load test a running API (needs SIMS_LOAD_PASSWORD; HOST optional)
	cd backend && uv run locust -f loadtest/locustfile.py --headless -u 40 -r 8 -t 60s --host $${HOST:-http://localhost:8010} --only-summary

lint:
	cd backend && uv run ruff check app tests tools
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

up:               ## full stack in Docker
	docker compose --profile app up -d --build

down:
	docker compose --profile app down
