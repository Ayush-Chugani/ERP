#!/usr/bin/env bash
# One-command local setup for SIMS (Linux / macOS / Git Bash).
#   ./scripts/setup.sh [--seed-demo] [--skip-db]
# Safe to re-run: an existing backend/.env is never overwritten.
set -euo pipefail

SEED_DEMO=0
SKIP_DB=0
for arg in "$@"; do
  case "$arg" in
    --seed-demo) SEED_DEMO=1 ;;
    --skip-db) SKIP_DB=1 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")/.."
step() { printf '\n==> %s\n' "$1"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "'$1' was not found. $2" >&2; exit 1; }; }

step "Checking prerequisites"
need uv "Install it from https://docs.astral.sh/uv/getting-started/installation/"
need node "Install Node.js 22.12+ (24 recommended) from https://nodejs.org/"
need npm "It ships with Node.js."
[ "$SKIP_DB" = 1 ] || need docker "Install Docker, or re-run with --skip-db and point SIMS_DATABASE_URL at your own PostgreSQL / Supabase."

step "Creating backend/.env"
if [ -f backend/.env ]; then
  echo "backend/.env already exists - leaving it untouched."
else
  if command -v openssl >/dev/null 2>&1; then
    SECRET="$(openssl rand -base64 48 | tr -d '=\n' | tr '+/' '-_')"
  else
    SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
  fi
  sed -e "s|^SIMS_SECRET_KEY=.*|SIMS_SECRET_KEY=${SECRET}|" \
      -e "s|^SIMS_COOKIE_SECURE=[^ #]*|SIMS_COOKIE_SECURE=false|" \
      backend/.env.example > backend/.env
  echo "Wrote backend/.env (random secret key, SIMS_COOKIE_SECURE=false for plain-http local use)."
fi

if [ "$SKIP_DB" = 0 ]; then
  step "Starting PostgreSQL (Docker, 127.0.0.1:54329)"
  docker compose up -d --wait
fi

step "Installing backend dependencies (uv)"
(
  cd backend
  uv sync
  step "Applying database migrations"
  uv run python -m app.cli migrate
  step "Loading permissions, roles and reference data"
  uv run python -m app.cli bootstrap
  if [ "$SEED_DEMO" = 1 ]; then
    step "Loading demo campus and accounts"
    uv run python -m app.cli seed-demo
  fi
)

step "Installing frontend dependencies (npm)"
(cd frontend && npm ci)

cat <<'EOF'

Setup complete.

Start the app (separate terminals):
  API : cd backend && uv run uvicorn app.main:app --reload     -> http://127.0.0.1:8000/api/docs
  Web : cd frontend && npm run dev                              -> http://localhost:5173
  Jobs: cd backend && uv run python -m app.cli worker           (optional background worker)

EOF
if [ "$SEED_DEMO" = 1 ]; then
  echo "Demo sign-ins: see docs/DEMO_DATA.md (usernames: demoadmin, registrar, hod, teacher, student ...)."
else
  echo "No users yet. Create an administrator:"
  echo '  export SIMS_BOOTSTRAP_ADMIN_PASSWORD="a-long-unique-password"'
  echo "  cd backend && uv run python -m app.cli create-admin --username admin --email you@example.org"
fi
