# Manifest Regeneration Rules — Coding Agent Reference

version: 1.0.0

**Load this file whenever you add, rename, or delete any tracked file in the repo.**

---

## The one rule: never compute SHA-256 yourself

The `docs/MANIFEST.yaml` integrity check normalizes CRLF → LF before hashing.
Raw OS-level tools (`certutil`, plain `hashlib`) do **not** do this and will
produce a mismatched hash that breaks CI.

## Mandatory steps when adding a new doc or YAML to the repo

```text
1.  Create the file.
2.  Add an entry to docs/MANIFEST.yaml with:
        sha256: pending
3.  Run the regen script (the ONLY way to set hashes):
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manifest-regenerate.ps1
4.  Verify:
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\integrity-check.ps1
5.  Stage and commit:
        git add docs/MANIFEST.yaml <your-new-file>
```

## Mandatory steps when editing an existing tracked file

The regen script updates ALL hashes, so the same three commands apply:

```text
1.  Edit the file.
2.  Run regen:
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manifest-regenerate.ps1
3.  Verify:
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\integrity-check.ps1
4.  Stage and commit docs/MANIFEST.yaml together with the edited file.
```

## What you must NEVER do

| Action | Why it breaks |
|--------|---------------|
| `certutil -hashfile <f> SHA256` | Hashes raw CRLF bytes — wrong value on Windows |
| `hashlib.sha256(open(f,'rb').read()).hexdigest()` | Same — no CRLF normalization |
| Hard-code any hex string as sha256 | Will mismatch when regen script runs |
| Use placeholder `000...` SHA | Fails `TestManifestIntegrity` immediately |
| Skip manifest entry for a new doc | Fails `TestManifestCoverage` immediately |

## CI tests that enforce this

- `tests/test_system_log_integrity.py::TestManifestIntegrity::test_manifest_check_passes`
- `tests/test_schema_versioning.py::TestManifestCoverage::test_all_docs_tracked`

---

See also: `docs/5-standards/manifest-regen-policy.md`
