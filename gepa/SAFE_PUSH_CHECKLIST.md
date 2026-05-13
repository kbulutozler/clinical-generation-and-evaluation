# GEPA public-safe push checklist

Use this before pushing `gepa/` changes when Anvil details should stay private.

## 1) Keep these out of pushes

- `gepa/docs/ANVIL_QUICKSTART.md`
- `gepa/docs/RUNBOOK.md`
- `gepa/docs/gepa_paper.md` (if it contains infra/internal notes)
- `gepa/servers/pids/`
- `gepa/**/__pycache__/`
- `gepa/**/*.py[cod]`

These are ignored in `.gitignore`.

## 2) If any of those files were already tracked, untrack once

Run:

```bash
git rm -r --cached gepa/docs/ANVIL_QUICKSTART.md gepa/docs/RUNBOOK.md gepa/docs/gepa_paper.md gepa/servers/pids gepa/__pycache__ || true
```

Then commit the removal from index (local files remain on disk).

## 3) Sanity-check what will be pushed

```bash
git status --short
git diff --name-only --cached
git ls-files 'gepa/*'
```

Verify no Anvil-specific docs or runtime artifacts are in staged files.

## 4) Optional: create sanitized docs for sharing

If docs are needed remotely, create `*-public.md` versions with:
- no usernames
- no hostnames
- no account/project/allocation IDs
- no absolute cluster paths
- no private queue/QoS details
