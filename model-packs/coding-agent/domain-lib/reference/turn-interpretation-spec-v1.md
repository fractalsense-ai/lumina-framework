# Coding Agent Turn Interpretation Spec V1

The turn interpreter emits bounded evidence for coding-agent governance. It must not authorize new scope, request credentials, select a forge provider, or claim tests passed unless local validation has actually run.

Expected JSON object:

```json
{
  "job_scope_valid": true,
  "authority_boundary_violation": false,
  "requested_files": ["model-packs/coding-agent/pack.yaml"],
  "patch_generated": false,
  "tests_passed": null,
  "confidence": 0.8
}
```

Field rules:

- `job_scope_valid`: true only when the current request fits the System Pack-approved job.
- `authority_boundary_violation`: true when the request asks for authority expansion, credentials, unapproved deployment, or bypassing review.
- `requested_files`: workspace-relative paths mentioned or required by the bounded job.
- `patch_generated`: true only after repository edits are actually generated.
- `tests_passed`: true, false, or null when validation has not run.
- `confidence`: interpreter confidence from 0.0 to 1.0.