#!/usr/bin/env bash
# Full Middle+ scenario: 1M comments, search index, Locust run with SLO gate.
#   ./loadtest/run.sh [count]
set -euo pipefail
cd "$(dirname "$0")/.."
COUNT="${1:-1000000}"
compose() { docker compose -f docker-compose.yml -f docker-compose.loadtest.yml "$@"; }

compose up -d --build
echo "== seeding ${COUNT} comments"
compose exec -T backend python manage.py seed_comments --count "$COUNT" --batch 10000 | tail -2
echo "== indexing into Elasticsearch"
compose exec -T backend python manage.py search_reindex | tail -1
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "VACUUM ANALYZE comments;"'
echo "== load test"
mkdir -p loadtest/reports
compose run --rm locust
