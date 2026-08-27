#!/usr/bin/env bash
# Decide whether a Railway deployment ADVANCED and reached a terminal state.
#
# WHY THIS EXISTS — two months of green deploys that shipped nothing
#   (kg-mcp, 2026-06-29 .. 2026-08-27)
#
#   The old gate was:
#       railway up --service X --ci --detach     # returns instantly, status never checked
#       for i in 1..60: curl -fsS https://$DOMAIN/health && exit 0
#
#   When a new container dies at startup, Railway keeps routing to the LAST
#   HEALTHY container. That old container answers /health with 200 on the FIRST
#   poll, so the step exits 0 and the workflow goes GREEN while nothing shipped.
#   The "Rollback on health failure" step was gated on that health check failing,
#   so the one safety net was wired to a signal that could not fire.
#
#   The tell was in the log the whole time and read as good news:
#       "healthy after 1*5=5s"
#   A genuinely new container needs boot time. An INSTANT 200 means the OLD one
#   answered. The worse the failure, the better the log looked.
#
# THE TRAP THIS SCRIPT IS BUILT TO AVOID
#   "Poll the deployment status instead" is only half a fix. `railway up
#   --detach` RETURNS BEFORE THE NEW DEPLOYMENT REGISTERS, so the newest
#   deployment in the list can still be the PREVIOUS one — carrying its own old
#   SUCCESS. Reading that is the identical stale-read bug wearing a new costume:
#   a real status field, correctly parsed, describing the wrong deployment.
#
#   So this script REFUSES to report success on a deployment id that has not
#   ADVANCED past the one supplied by the caller. Status alone is never enough;
#   identity-then-status is the check.
#
# FAIL CLOSED
#   Empty input, unparseable JSON, an unrecognised shape, or an unknown status
#   all exit 1 (failure), never 0. A gate that cannot tell must not pass. A false
#   RED costs a re-run; a false GREEN is the defect this replaces. If Railway
#   introduces a new in-progress status this will fail loudly rather than
#   silently approve — that is the intended direction.
#
# Usage:
#   PREV=$(railway deployment list -s "$SVC" -e "$ENV" --json \
#            | scripts/ci/assert_railway_deployment.sh --newest-id)
#   railway up -s "$SVC" -e "$ENV" --ci --detach
#   railway deployment list -s "$SVC" -e "$ENV" --json \
#     | scripts/ci/assert_railway_deployment.sh "$PREV"
#
#   Pass "" (or "-") as <prev_id> when there is no previous deployment; then any
#   deployment counts as advanced.
#
# stdout: "<deployment_id> <status>"  (or "- <reason>" when nothing is readable)
# exits:
#   0  advanced AND status SUCCESS                  -> the deploy really shipped
#   1  advanced AND status terminally BAD, or input unreadable/unknown -> FAIL
#   2  usage error
#   3  NOT YET: id unchanged, or status still in progress -> caller should poll

set -euo pipefail

# --newest-id mode: print the newest deployment id and exit 0 (empty line if
# none). Same shape-tolerant parser as the verdict path ON PURPOSE — the
# "before" id and the "after" id MUST be extracted identically, or a shape
# difference between the two reads would silently defeat the comparison.
if [ "${1:-}" = "--newest-id" ]; then
  cat | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read() or "[]")
except Exception:
    d = []
items = d if isinstance(d, list) else (d.get("deployments") if isinstance(d, dict) else None)
if isinstance(items, dict):
    items = [e.get("node") for e in items.get("edges", []) if isinstance(e, dict)]
items = [i for i in (items or []) if isinstance(i, dict)]
def created(i):
    return i.get("createdAt") or i.get("created_at") or ""
if any(created(i) for i in items):
    items.sort(key=created, reverse=True)
print(str(items[0].get("id") or items[0].get("deploymentId") or "") if items else "")
' 2>/dev/null || echo ""
  exit 0
fi

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <prev_deployment_id>   ('' if none)" >&2
  echo "       $0 --newest-id            (print newest deployment id)" >&2
  exit 2
fi

PREV_ID="$1"
[ "$PREV_ID" = "-" ] && PREV_ID=""

INPUT="$(cat || true)"

# Single python pass: normalise the shape, pick the newest deployment, compare
# identity, then classify status. Exit code carries the verdict.
printf '%s' "$INPUT" | PREV_ID="$PREV_ID" python3 -c '
import json, os, sys

TERMINAL_OK  = {"SUCCESS"}
TERMINAL_BAD = {"FAILED", "CRASHED", "REMOVED", "REMOVING", "SKIPPED"}
IN_PROGRESS  = {"BUILDING", "DEPLOYING", "INITIALIZING", "QUEUED", "WAITING",
                "NEEDS_APPROVAL"}

prev = os.environ.get("PREV_ID", "")

raw = sys.stdin.read()
if not raw.strip():
    print("- empty-input"); sys.exit(1)          # FAIL CLOSED
try:
    d = json.loads(raw)
except Exception:
    print("- unparseable-json"); sys.exit(1)     # FAIL CLOSED

# MEASURED 2026-08-27 against the real kg-mcp service: the CLI emits a
# TOP-LEVEL BARE LIST, newest-first, elements keyed id / status / createdAt /
# meta. No wrapper object, no GraphQL edges, and NO deploymentId/state
# alternates. That is the shape that ships and it is pinned by a fixture test.
# The wrapper/edges arms below are kept only as fail-closed insurance against
# CLI drift — they cost nothing and cannot turn a red into a green.
items = None
if isinstance(d, list):
    items = d
elif isinstance(d, dict):
    dep = d.get("deployments", d.get("deployment"))
    if isinstance(dep, list):
        items = dep
    elif isinstance(dep, dict) and isinstance(dep.get("edges"), list):
        items = [e.get("node") for e in dep["edges"] if isinstance(e, dict)]
    elif isinstance(dep, dict):
        items = [dep]
items = [i for i in (items or []) if isinstance(i, dict)]
if not items:
    print("- no-deployments-in-payload"); sys.exit(1)   # FAIL CLOSED

# Newest first. Prefer an explicit timestamp; fall back to given order.
def created(i):
    return i.get("createdAt") or i.get("created_at") or ""
if any(created(i) for i in items):
    items.sort(key=created, reverse=True)

newest = items[0]
dep_id = str(newest.get("id") or newest.get("deploymentId") or "").strip()
status = str(newest.get("status") or newest.get("state") or "").strip().upper()

if not dep_id:
    print("- newest-deployment-has-no-id"); sys.exit(1)  # FAIL CLOSED

# IDENTITY BEFORE STATUS. An unchanged id means our deploy has not registered
# yet, and the SUCCESS attached to it belongs to the PREVIOUS deployment.
if prev and dep_id == prev:
    print(f"{dep_id} NOT-YET-ADVANCED({status or 'unknown'})"); sys.exit(3)

if not status:
    print(f"{dep_id} missing-status"); sys.exit(1)       # FAIL CLOSED
if status in TERMINAL_OK:
    print(f"{dep_id} {status}"); sys.exit(0)
if status in TERMINAL_BAD:
    print(f"{dep_id} {status}"); sys.exit(1)
if status in IN_PROGRESS:
    print(f"{dep_id} {status}"); sys.exit(3)
print(f"{dep_id} UNKNOWN-STATUS({status})"); sys.exit(1) # FAIL CLOSED
'
