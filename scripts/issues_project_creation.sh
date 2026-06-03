#!/bin/bash

GITHUB_USER=""
REPO="$GITHUB_USER/Hs_codes_api"
PROJECT_NUM="4"
MYTMP="${TMPDIR:-/tmp}"

echo "========================================"
echo " HS Code Search "
echo "========================================"

gh repo view $REPO > /dev/null 2>&1 || { echo "Cannot access repo"; exit 1; }
echo "Repo accessible"

make_issue() {
  local TITLE="$1"
  local BODY="$2"
  local LABELS="$3"
  local MILESTONE_TITLE="$4"

  local BODYFILE="$MYTMP/body_$$.txt"
  printf '%s\n' "$BODY" > "$BODYFILE"

  local ARGS=(--repo "$REPO" --title "$TITLE" --body-file "$BODYFILE")
  [ -n "$LABELS" ]          && ARGS+=(-l "$LABELS")
  [ -n "$MILESTONE_TITLE" ] && ARGS+=(-m "$MILESTONE_TITLE")

  local OUT
  OUT=$(gh issue create "${ARGS[@]}" 2>&1)
  local EXIT=$?
  rm -f "$BODYFILE"

  if [ $EXIT -eq 0 ]; then
    local NUM
    NUM=$(echo "$OUT" | grep -o '/issues/[0-9]*' | grep -o '[0-9]*')
    echo "  ✓ #$NUM $TITLE"
  else
    echo "  ✗ FAILED: $TITLE"
    echo "    $OUT"
  fi
}

# =============================================================================
# LABELS
# =============================================================================
echo ""
echo "→ Creating labels..."
for label in "bug" "documentation" "duplicate" "enhancement" "good first issue" "help wanted" "invalid" "question" "wontfix"; do
  gh label delete "$label" --repo $REPO --yes 2>/dev/null || true
done
gh label create "backend"  --color "0075ca" --repo $REPO --force 2>/dev/null && echo "  ✓ backend"  || echo "  ~ backend"
gh label create "frontend" --color "e4e669" --repo $REPO --force 2>/dev/null && echo "  ✓ frontend" || echo "  ~ frontend"
gh label create "devops"   --color "d93f0b" --repo $REPO --force 2>/dev/null && echo "  ✓ devops"   || echo "  ~ devops"
gh label create "testing"  --color "0e8a16" --repo $REPO --force 2>/dev/null && echo "  ✓ testing"  || echo "  ~ testing"
gh label create "model"    --color "c5def5" --repo $REPO --force 2>/dev/null && echo "  ✓ model"    || echo "  ~ model"
gh label create "api"      --color "bfd4f2" --repo $REPO --force 2>/dev/null && echo "  ✓ api"      || echo "  ~ api"
gh label create "auth"     --color "f9d0c4" --repo $REPO --force 2>/dev/null && echo "  ✓ auth"     || echo "  ~ auth"
gh label create "search"   --color "1d76db" --repo $REPO --force 2>/dev/null && echo "  ✓ search"   || echo "  ~ search"
gh label create "docker"   --color "e99695" --repo $REPO --force 2>/dev/null && echo "  ✓ docker"   || echo "  ~ docker"
gh label create "ci"       --color "b60205" --repo $REPO --force 2>/dev/null && echo "  ✓ ci"       || echo "  ~ ci"
gh label create "cd"       --color "ee0701" --repo $REPO --force 2>/dev/null && echo "  ✓ cd"       || echo "  ~ cd"
gh label create "infra"    --color "5319e7" --repo $REPO --force 2>/dev/null && echo "  ✓ infra"    || echo "  ~ infra"
gh label create "database" --color "006b75" --repo $REPO --force 2>/dev/null && echo "  ✓ database" || echo "  ~ database"
gh label create "day-1"    --color "fbca04" --repo $REPO --force 2>/dev/null && echo "  ✓ day-1"    || echo "  ~ day-1"
gh label create "day-2"    --color "f9a825" --repo $REPO --force 2>/dev/null && echo "  ✓ day-2"    || echo "  ~ day-2"
gh label create "day-3"    --color "e65100" --repo $REPO --force 2>/dev/null && echo "  ✓ day-3"    || echo "  ~ day-3"
gh label create "backlog"  --color "cccccc" --repo $REPO --force 2>/dev/null && echo "  ✓ backlog"  || echo "  ~ backlog"

# =============================================================================
# MILESTONES
# =============================================================================
echo ""
echo "→ Creating milestones..."
if date -v+1d > /dev/null 2>&1; then
  DAY1=$(date -v+1d +%Y-%m-%dT00:00:00Z)
  DAY2=$(date -v+2d +%Y-%m-%dT00:00:00Z)
  DAY3=$(date -v+3d +%Y-%m-%dT00:00:00Z)
else
  DAY1=$(date -d '+1 day' +%Y-%m-%dT00:00:00Z)
  DAY2=$(date -d '+2 days' +%Y-%m-%dT00:00:00Z)
  DAY3=$(date -d '+3 days' +%Y-%m-%dT00:00:00Z)
fi
gh api repos/$REPO/milestones -f title="Backend"  -f description="Day 1" -f due_on="$DAY1" > /dev/null 2>&1 || true
gh api repos/$REPO/milestones -f title="CI/CD"    -f description="Day 2" -f due_on="$DAY2" > /dev/null 2>&1 || true
gh api repos/$REPO/milestones -f title="Frontend" -f description="Day 3" -f due_on="$DAY3" > /dev/null 2>&1 || true
echo "  ✓ Milestones ready (Backend / CI/CD / Frontend)"

# =============================================================================
# ISSUES — milestone passed as TITLE string
# =============================================================================
echo ""
echo "→ Day 1: Models..."

make_issue "[MIGRATION] Enable pg_trgm extension via migration" \
"Add a data migration to enable the pg_trgm PostgreSQL extension.
Must run before the HSCode model migration or indexes will fail.

Acceptance Criteria:
- Migration uses TrigramExtension() operation
- Migration ordered before HSCode model migration
- Works on a clean database
- README documents PostgreSQL as a requirement" \
"backend,database,day-1" "Backend"

make_issue "[MODEL] CustomUser model" \
"Extend AbstractUser with a minimal custom user model.

Acceptance Criteria:
- CustomUser extends AbstractUser
- Has role field: choices admin/user, default user
- Uses email as USERNAME_FIELD
- AUTH_USER_MODEL set in settings
- Registered in admin with UserAdmin" \
"backend,model,auth,day-1" "Backend"

make_issue "[MODEL] HSCode model with PostgreSQL trigram index" \
"Create the HSCode model with trigram GIN indexes for fast fuzzy search.

Acceptance Criteria:
- hs_code CharField unique max_length 20
- description TextField
- created_at auto DateTimeField
- GinIndex with gin_trgm_ops on both fields
- __str__ returns hs_code - description
- Registered in Django admin" \
"backend,model,day-1" "Backend"

echo ""
echo "→ Day 1: API..."

make_issue "[ADMIN] CSV upload endpoint for HS codes" \
"DRF endpoint that accepts a CSV file and bulk inserts HS codes.

Acceptance Criteria:
- POST /api/v1/hs-codes/upload/ accepts multipart CSV
- Parses two-column CSV (hs_code, description)
- Uses bulk_create with ignore_conflicts for idempotency
- Returns count of created vs skipped records
- Restricted to admin/staff only
- Returns 400 on malformed CSV
- Strips whitespace from codes and descriptions" \
"backend,api,day-1" "Backend"

make_issue "[API] Search endpoint with trigram similarity" \
"Core search endpoint using PostgreSQL trigram similarity.

Acceptance Criteria:
- GET /api/v1/hs-codes/?q=chicken returns relevant results
- Searches both hs_code and description fields
- Similarity threshold 0.1 tunable via env var
- Results ordered by similarity score descending
- Returns empty list not 404 when no results
- Returns 400 if q param is missing" \
"backend,api,search,day-1" "Backend"

make_issue "[API] Cursor pagination for search results" \
"Cursor-based pagination on the search endpoint.

Acceptance Criteria:
- CursorPagination applied to search viewset
- Default page size 20 max 100
- Ordered by hs_code for a stable cursor
- Response includes next and previous cursor URLs
- Page size configurable via page_size param" \
"backend,api,day-1" "Backend"

make_issue "[API] Exact code lookup endpoint" \
"Direct lookup by HS code.

Acceptance Criteria:
- GET /api/v1/hs-codes/{hs_code}/
- Returns 404 if code not found
- Response includes hs_code description and chapter (first 2 digits)
- Public endpoint no auth required" \
"backend,api,day-1" "Backend"

make_issue "[API] Chapter-level filtering" \
"Filter results by HS chapter.

Acceptance Criteria:
- GET /api/v1/hs-codes/?chapter=02 returns codes starting with 02
- GET /api/v1/hs-codes/chapters/ lists all available chapters
- Chapter filter combinable with q param
- Invalid chapter value returns 400" \
"backend,api,day-1" "Backend"

echo ""
echo "→ Day 1: Auth..."

make_issue "[AUTH] JWT authentication with SimpleJWT" \
"Stateless JWT auth for admin endpoints.

Acceptance Criteria:
- POST /api/v1/auth/token/ returns access and refresh tokens
- POST /api/v1/auth/token/refresh/ refreshes access token
- Access token lifetime 1 hour, refresh token lifetime 7 days
- Token payload includes role claim
- Invalid credentials return 401" \
"backend,auth,day-1" "Backend"

make_issue "[PERMISSION] Upload restricted to admin/staff only" \
"Acceptance Criteria:
- Custom IsStaffOrAdmin permission class
- 403 for authenticated non-admin users
- 401 for unauthenticated requests" \
"backend,auth,day-1" "Backend"

make_issue "[PERMISSION] Rate limiting on public search endpoint" \
"Acceptance Criteria:
- Anonymous users 60 requests per minute
- Authenticated users 300 requests per minute
- 429 with Retry-After header when exceeded
- Thresholds configurable via env vars" \
"backend,api,day-1" "Backend"

make_issue "[ENV] Settings management with django-environ" \
"Acceptance Criteria:
- django-environ installed and configured
- .env.example documents every variable
- .env in .gitignore
- Settings split into base development and production
- DEBUG defaults to False in production
- DATABASE_URL used for database config
- SECRET_KEY has no default in production" \
"backend,devops,day-1" "Backend"

echo ""
echo "→ Day 1: Tests..."

make_issue "[TEST] Model tests" \
"Acceptance Criteria:
- HSCode creation and __str__ output correct
- Duplicate hs_code raises IntegrityError
- bulk_create with ignore_conflicts handles duplicates silently
- GIN index exists on both fields
- CustomUser creation with email as username
- CustomUser role defaults to user" \
"testing,day-1" "Backend"

make_issue "[TEST] Search API tests" \
"Acceptance Criteria:
- Exact description match returns correct result
- Partial description returns results (fuzzy)
- No results returns empty list with 200
- Missing q param returns 400
- next cursor present when results exceed page_size
- Chapter filter returns only codes for that chapter
- Rate limit returns 429 after threshold" \
"testing,day-1" "Backend"

make_issue "[TEST] CSV upload tests" \
"Acceptance Criteria:
- Valid CSV creates records and returns correct count
- Duplicate rows skipped not errored
- Malformed CSV returns 400
- Non-admin authenticated user returns 403
- Unauthenticated request returns 401
- Non-ASCII characters in descriptions handled
- 1000+ row CSV completes without timeout" \
"testing,day-1" "Backend"

make_issue "[TEST] Auth endpoint tests" \
"Acceptance Criteria:
- Valid credentials return access and refresh tokens
- Invalid credentials return 401
- Valid refresh token returns new access token
- Expired refresh token returns 401
- Protected endpoint rejects missing and malformed token" \
"testing,day-1" "Backend"

echo ""
echo "→ Day 2: DevOps..."

make_issue "[DOCKER] docker-compose for local development" \
"Acceptance Criteria:
- Services: db postgres 15, web, redis
- pg_trgm enabled on first run
- Volume mounts for hot reload
- web depends_on db with healthcheck
- Makefile with make up make down make test" \
"devops,docker,day-2" "CI/CD"

make_issue "[DOCKER] Production Dockerfile" \
"Acceptance Criteria:
- Multi-stage build builder and runtime
- No dev dependencies in final image
- Non-root user appuser
- Gunicorn with configurable worker count
- Entrypoint runs migrations then starts gunicorn
- Health check at /api/v1/health/" \
"devops,docker,day-2" "CI/CD"

make_issue "[CI] GitHub Actions: lint and test on PR" \
"Acceptance Criteria:
- Triggers on pull_request to main and develop
- Runs ruff for linting
- Runs pytest with coverage
- Uses postgres service container with pg_trgm enabled
- Fails if coverage below 80%
- Completes under 3 minutes" \
"devops,ci,day-2" "CI/CD"

make_issue "[CD] Deploy to VPS on merge to main" \
"Acceptance Criteria:
- Triggers on push to main after CI passes
- SSHs to VPS and pulls latest Docker image
- Runs docker compose pull and docker compose up -d
- Runs migrations post-deploy
- Fails loudly if migrations fail
- Old container runs until new one is healthy
- Secrets needed: VPS_HOST VPS_USER VPS_SSH_KEY VPS_PORT" \
"devops,cd,day-2" "CI/CD"

make_issue "[INFRA] Nginx config for API proxy" \
"Acceptance Criteria:
- Proxies /api/ to gunicorn port 8000
- Sets X-Forwarded-For and X-Real-IP correctly
- Rate limit 60 requests per minute per IP on search endpoint
- Gzip for JSON responses
- SSL via Lets Encrypt
- Config passes nginx -t" \
"devops,infra,day-2" "CI/CD"

echo ""
echo "→ Day 3: Frontend..."

make_issue "[FE] Search UI with instant search" \
"Acceptance Criteria:
- Search input with 300ms debounce
- Results render as code and description pairs
- Loading indicator while fetching
- Empty state message when no results
- Error state if API unreachable
- Keyboard navigation through results
- Mobile responsive" \
"frontend,day-3" "Frontend"

make_issue "[FE] Chapter browser / category navigation" \
"Acceptance Criteria:
- Sidebar or dropdown listing all chapters
- Clicking chapter filters results
- Active chapter highlighted
- Combinable with text search
- Chapter list cached client-side" \
"frontend,day-3" "Frontend"

make_issue "[FE] Copy-to-clipboard on HS code click" \
"Acceptance Criteria:
- Clicking code copies it to clipboard
- Visual feedback with Copied tooltip or colour flash
- Works in all modern browsers
- Graceful fallback if Clipboard API unavailable" \
"frontend,day-3" "Frontend"

make_issue "[FE] API reference and docs page" \
"Acceptance Criteria:
- Documents all public endpoints with examples
- Auth token endpoint documented
- Copy button on all code examples
- Linked from main search UI" \
"frontend,day-3" "Frontend"

make_issue "[FE] Deploy to tools.digitaltouch.co.zw" \
"Acceptance Criteria:
- DNS subdomain configured and propagated
- Frontend served via Nginx
- SSL via Lets Encrypt
- API base URL from env var
- SPA 404 fallback to index.html
- Lighthouse score 90 or above on mobile" \
"frontend,devops,day-3" "Frontend"

echo ""
echo "→ Backlog..."

make_issue "[FEATURE] OpenAPI schema with drf-spectacular" \
"Acceptance Criteria:
- GET /api/schema/ returns OpenAPI 3.0 YAML
- GET /api/docs/ serves Swagger UI
- All endpoints documented with examples" \
"backend,backlog" ""

make_issue "[FEATURE] Search analytics and query logging" \
"Acceptance Criteria:
- Log query string result count and timestamp
- No PII stored
- Admin view of top queries
- CSV export from admin" \
"backend,backlog" ""

make_issue "[FEATURE] Bulk lookup endpoint" \
"Accept a list of HS codes and return descriptions for all.

Acceptance Criteria:
- POST /api/v1/hs-codes/bulk-lookup/
- Accepts JSON array up to 100 codes
- Returns found and not-found codes separately
- Requires authentication" \
"backend,backlog" ""

# =============================================================================
# LINK TO PROJECT
# =============================================================================
echo ""
echo "→ Linking issues to project #$PROJECT_NUM..."

gh issue list --repo $REPO --limit 100 --state open | \
  awk '{print $1}' | \
  while read n; do
    [ -z "$n" ] && continue
    echo "$n" | grep -qE '^[0-9]+$' || continue
    gh project item-add $PROJECT_NUM \
      --owner $GITHUB_USER \
      --url "https://github.com/$REPO/issues/$n" 2>/dev/null \
      && echo "  ✓ #$n linked" \
      || echo "  ~ #$n skipped"
  done

echo ""
echo "========================================"
echo " Done!"
echo " Issues : https://github.com/$REPO/issues"
echo " Project: https://github.com/users/$GITHUB_USER/projects/$PROJECT_NUM"
echo "========================================"
