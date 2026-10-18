#!/usr/bin/env bash
#
# Bring the EaglerVault preview back after a sandbox recycle.
#
# A recycle may leave a sparse checkout with the launcher present and game
# payloads intentionally omitted. This restores missing site files when needed,
# audits the catalogue without reading payloads, and can run the UI smoke suite.
#
#   ./tools/resume.sh              repair whatever is missing, then serve
#   ./tools/resume.sh --check      verify only, change nothing
#   ./tools/resume.sh --test       repair, serve, then run the smoke suite
#   ./tools/resume.sh --force      allow a reset even with uncommitted work
#
set -euo pipefail

PORT="${PORT:-8080}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTENV="${TESTENV:-/tmp/testenv}"

CHECK=0; RUN_TEST=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --test)  RUN_TEST=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

cd "$REPO_ROOT"

B="\033[1m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; D="\033[2m"; N="\033[0m"
step() { printf "\n${B}%s${N}\n" "$1"; }
ok()   { printf "  ${G}ok${N}   %s\n" "$1"; }
skip() { printf "  ${D}--${N}   %s\n" "$1"; }
bad()  { printf "  ${R}!!${N}   %s\n" "$1"; }

port_open() { (exec 3<>/dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; }

# ---------------------------------------------------------------- branch ---
step "branch"
BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [ -z "$BRANCH" ]; then
  BAD=1; bad "not on a branch (detached HEAD) -- refusing to guess"; exit 1
fi
ok "$BRANCH"

# A recycle leaves the working tree at the base commit, which has neither
# index.html nor tools/ -- so their presence is a reliable "already restored".
needs_restore=0
for f in index.html tools/embed_catalog.py; do
  [ -f "$f" ] || needs_restore=1
done

# ---------------------------------------------------------------- safety ---
step "working tree"
# Only tracked edits block a reset. Untracked files are how a new script like
# this one survives a recycle, so they must not get in the way.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  if [ "$FORCE" -eq 1 ]; then
    printf "  ${Y}!!${N}   uncommitted edits present, --force given, they will be lost\n"
  else
    bad "you have uncommitted changes"
    echo "        commit them, or re-run with --force to discard"
    exit 1
  fi
else
  ok "clean"
fi

# --------------------------------------------------------------- restore ---
step "files"
if [ "$needs_restore" -eq 0 ]; then
  skip "already restored, nothing to fetch"
else
  if [ "$CHECK" -eq 1 ]; then
    bad "site files are missing (run without --check to restore)"; exit 1
  fi
  echo "  fetching $BRANCH ..."
  git fetch origin "$BRANCH" 2>&1 | sed 's/^/        /'
  git reset --hard FETCH_HEAD >/dev/null
  ok "restored to $(git rev-parse --short HEAD)"
fi

# the remote-tracking ref is lost on every recycle
if ! git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
  git branch --set-upstream-to="origin/$BRANCH" >/dev/null 2>&1 || true
fi
UPSTREAM="$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo '(none)')"
if [ "$UPSTREAM" = "(none)" ]; then bad "no upstream configured"; else ok "upstream -> $UPSTREAM"; fi

# ------------------------------------------------------------------- jsdom --
step "jsdom"
if [ -d "$TESTENV/node_modules/jsdom" ]; then
  skip "present in $TESTENV"
elif [ "$CHECK" -eq 1 ]; then
  bad "jsdom missing (run without --check to install)"; exit 1
else
  mkdir -p "$TESTENV"
  ( cd "$TESTENV" && npm init -y >/dev/null 2>&1 && npm install --silent jsdom >/dev/null 2>&1 )
  ok "installed $(node -e "process.stdout.write(require('$TESTENV/node_modules/jsdom/package.json').version)")"
fi

# ------------------------------------------------------------------ server --
step "server"
if port_open; then
  skip "already listening on $PORT"
else
  if [ "$CHECK" -eq 1 ]; then
    bad "nothing serving on $PORT (run without --check to start it)"; exit 1
  fi
  setsid nohup python3 -m http.server "$PORT" --bind 0.0.0.0 \
    >/tmp/eaglervault-server.log 2>&1 < /dev/null &
  disown 2>/dev/null || true
  for _ in $(seq 1 40); do port_open && break; sleep 0.25; done
  if port_open; then ok "listening on 0.0.0.0:$PORT"; else
    bad "server did not come up; see /tmp/eaglervault-server.log"; exit 1
  fi
fi

# ----------------------------------------------------------------- verify --
step "verify"
fail=0
for route in / /index.html; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$PORT$route" || echo 000)"
  if [ "$code" = "200" ]; then ok "$route -> 200"; else bad "$route -> $code"; fail=1; fi
done

# Validate the embedded data against Git's index without opening game blobs.
if python3 tools/verify_catalog.py; then
  ok "catalogue matches tracked builds"
else
  bad "catalogue audit failed"; fail=1
fi

# A full checkout also gets a lightweight HEAD check. Unmaterialized sparse
# payloads are intentionally skipped; only a launched build transfers bytes.
if ! python3 - "$PORT" <<'PY'
import json, os, re, sys, urllib.parse, urllib.request
port = sys.argv[1]
html = open('index.html', encoding='utf-8').read()
m = re.search(r'<script id="vault" type="application/json">(.*?)</script>', html, re.S)
if not m:
    print('  \033[31m!!\033[0m   index.html has no embedded catalogue')
    sys.exit(1)
data = json.loads(m.group(1))
missing, broken, checked = 0, [], 0
for build in data['versions']:
    if not os.path.isfile(build['file']):
        missing += 1
        continue
    checked += 1
    url = 'http://localhost:%s/%s' % (port, urllib.parse.quote(build['file']))
    try:
        code = urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=15).status
    except Exception as error:
        code = getattr(error, 'code', 'ERR')
    if code != 200:
        broken.append((build['file'], code))
if broken:
    print('  \033[31m!!\033[0m   %d/%d materialized builds unreachable' % (len(broken), checked))
    for filename, code in broken[:5]:
        print('        %s -> %s' % (filename, code))
    sys.exit(1)
print('  \033[32mok\033[0m   %d materialized builds reachable; %d sparse payloads omitted'
      % (checked, missing))
PY
then
  fail=1
fi

# ------------------------------------------------------------------- test --
if [ "$RUN_TEST" -eq 1 ]; then
  step "smoke test"
  NODE_PATH="$TESTENV/node_modules" node tools/smoke-test.js 2>&1 | tail -3
fi

printf "\n"
if [ "$fail" -eq 0 ]; then
  printf "${G}ready${N}  http://localhost:$PORT/\n"
else
  printf "${R}verify failed${N}\n"; exit 1
fi
