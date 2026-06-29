---
title: "Manifest Regeneration Policy"
version: 1.0.0
doc_version: 1.0.0
status: active
last_updated: 2026-06-29
---

# Manifest Regeneration Policy

## Problem Statement

`docs/MANIFEST.yaml` stores a SHA-256 hash for every tracked file. The integrity
check tool (`lumina.systools.manifest_integrity check`) computes hashes by
**normalizing CRLF → LF before hashing** so that Windows and Linux checkouts
produce identical values. Any hash computed by a different method (e.g.,
`certutil`, Python `hashlib` without normalization, `sha256sum`) will produce a
different value and **will fail the integrity test** in CI.

This has been a recurring failure mode in automated agent sessions: the agent
adds a file, tries to compute the hash manually, inserts a wrong or placeholder
SHA, and breaks `test_manifest_check_passes`.

---

## Mandatory Rules

### Rule 1 — Never compute SHA-256 hashes manually

Do **not** use any of the following to generate a SHA for a MANIFEST entry:

```powershell
# WRONG — certutil does not normalize line endings
certutil -hashfile <file> SHA256

# WRONG — raw hashlib without CRLF normalization
python -c "import hashlib; print(hashlib.sha256(open(...,'rb').read()).hexdigest())"

# WRONG — placeholder
sha256: 0000000000000000000000000000000000000000000000000000000000000000
```

### Rule 2 — Always use `sha256: pending` for new entries

When adding a new file to `docs/MANIFEST.yaml`, set the hash field to the
literal string `pending`:

```yaml
- path: docs/roadmap/slices/13-tier-1-architect.md
  type: doc
  section: 0
  doc_version: 1.0.0
  status: planned
  last_updated: 2026-06-29
  sha256: pending
```

### Rule 3 — Run the regen script immediately after adding the entry

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manifest-regenerate.ps1
```

The script reads every tracked entry, normalizes CRLF → LF, and writes the
correct hash in-place. This is the **only** sanctioned way to populate or
update SHA-256 values.

### Rule 4 — Run the integrity check before committing

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\integrity-check.ps1
```

The check must exit with `[PASS]` before `git add docs/MANIFEST.yaml`.

### Rule 5 — New docs require manifest entries

Any new `.md` file added under `docs/` or `model-packs/*/docs/` **must** have a
corresponding entry in `docs/MANIFEST.yaml`. The CI test
`TestManifestCoverage.test_all_docs_tracked` will fail otherwise.

---

## Correct Workflow (new doc)

```text
1. Create the .md file
2. Append entry with sha256: pending to docs/MANIFEST.yaml
3. powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manifest-regenerate.ps1
4. powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\integrity-check.ps1
5. git add docs/MANIFEST.yaml <new-file>
6. git commit
```

---

## Why This Fails in Automated Sessions

Coding agents and LLMs operating in a Windows environment default to computing
hashes from raw bytes. Git checks out files with CRLF line endings on Windows,
producing a different SHA than the LF-only bytes that Git stores and that
`manifest_integrity.py` always normalizes to. The only safe path is to delegate
hash computation entirely to the regen script, which applies the normalization
consistently.

---

## Related

- `scripts/manifest-regenerate.ps1` — canonical regen tool
- `scripts/integrity-check.ps1` — integrity verification
- `src/lumina/systools/manifest_integrity.py` — integrity check implementation
- `tests/test_system_log_integrity.py::TestManifestIntegrity` — CI gate
- `tests/test_schema_versioning.py::TestManifestCoverage` — coverage gate
