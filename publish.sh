#!/usr/bin/env bash
# Publish Peter 的每日雷达 → https://tangwin.github.io/daily/  (repo TangWin/daily, Pages = main:/docs)
#
#   ./publish.sh              validate all data/ files, rebuild docs/, link-check, commit changed files, push once
#   ./publish.sh --no-push    same, but stop after the local commit
#   ./publish.sh --dry-run    validate + build + link-check only (no git changes)
#   ./publish.sh -m "msg"     custom commit message
#
# Safe for several bots: everything runs under an exclusive flock (waits up to 15 min).
# Fails loudly (non-zero exit, message on stderr) on bad JSON / schema errors / broken links / push errors.
# Never force-pushes.
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$HERE"
MODE=push; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE=dry ;;
    --no-push) MODE=commit ;;
    -m) MSG="${2:?-m needs a message}"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "publish.sh: unknown argument $1" >&2; exit 2 ;;
  esac; shift
done
die() { echo "publish.sh: ERROR: $*" >&2; exit 1; }
export TZ=Asia/Shanghai
GH="$(command -v gh || echo /usr/local/bin/gh)"
GIT=(git -c user.name=TangWin -c user.email=35861394+TangWin@users.noreply.github.com
     -c credential.helper= -c "credential.helper=!$GH auth git-credential")

exec 9>"$HERE/.git/publish.lock"
flock -w 900 9 || die "another publish.sh is still running (lock .git/publish.lock held > 15 min)"
echo "[publish] $(date '+%F %T %Z') lock acquired (mode=$MODE)"

python3 scripts/validate.py || die "data validation failed — fix the files listed above; nothing was built or pushed"

if [ "$MODE" != dry ] && git remote get-url origin >/dev/null 2>&1; then
  "${GIT[@]}" fetch -q origin main || die "git fetch failed"
  if ! git merge-base --is-ancestor origin/main HEAD; then
    "${GIT[@]}" merge -q --ff-only origin/main || die "local main has diverged from origin/main; resolve manually (never force-push)"
  fi
fi

python3 build.py || die "build failed"
python3 scripts/linkcheck.py docs || die "link check failed"
[ "$MODE" = dry ] && { echo "[publish] dry run ok — docs/ rebuilt, nothing committed"; exit 0; }

git add -- data docs config
if git diff --cached --quiet; then echo "[publish] no changes — nothing to commit"; else
  CHANGED="$(git diff --cached --name-only -- data | sed -E 's#^data/([a-z]+)/([0-9-]+)\.json$#\1/\2#' | sort -u | paste -sd' ' -)"
  [ -n "$MSG" ] || MSG="Publish ${CHANGED:-site rebuild} ($(date '+%F %H:%M') CST)"
  "${GIT[@]}" commit -q -m "$MSG" || die "git commit failed"
  echo "[publish] committed $(git rev-parse --short HEAD): $MSG"
fi
[ "$MODE" = commit ] && { echo "[publish] --no-push: stopping before push"; exit 0; }
if [ -n "$(git rev-list origin/main..HEAD 2>/dev/null)" ] || ! git rev-parse -q --verify origin/main >/dev/null; then
  "${GIT[@]}" push -q origin HEAD:main || die "git push failed (not forcing). Run publish.sh again after fixing."
  echo "[publish] pushed $(git rev-parse --short HEAD) → https://github.com/TangWin/daily"
else
  echo "[publish] origin/main already up to date"
fi
echo "[publish] live in ~1 min: https://tangwin.github.io/daily/"
