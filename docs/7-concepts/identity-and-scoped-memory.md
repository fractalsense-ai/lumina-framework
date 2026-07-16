---
version: 1.0.0
last_updated: 2026-07-15
---

# Identity and Scoped Memory

Slice 26 defines how Lumina keeps institutional memory partitioned by organization and
site while retaining pseudonymous actor and device provenance. The contract is provider
neutral and local-first: a deployment can persist records in files or SQLite without
requiring a connector or hosted service.

## Scope Contract

Every new institutional-memory contract carries:

- `organization_id`: the tenant or organization boundary.
- `site_id`: the operational site within that organization.
- `actor_id`: the pseudonymous actor associated with the record.
- `device_id`: an optional pseudonymous workstation or device identifier.

Organization and site are hard boundaries. A record without either identifier is not
eligible for normal scoped writes. Actor and device are provenance and optional narrowing
filters; they do not replace organization/site isolation.

## Propagation Path

Scope enters the runtime from authenticated claims or an already-populated profile. Session
construction hydrates the profile before the domain context is built. The resulting context
is passed to record writers, persistence queries, and retrieval adapters.

The normal path is:

1. Authentication identifies the pseudonymous actor and any organization/site claims.
2. Profile loading preserves existing values and fills only values supplied by trusted
   authenticated context.
3. Session and orchestrator construction carry the scope into system-log writers.
4. Filesystem and SQLite queries apply organization/site filters before returning records.
5. Vector retrieval excludes ineligible chunks before similarity scoring and top-k selection.
6. Escalation and commitment records retain organization/site and optional device provenance.

Missing scope remains unset. Literal template placeholders are not valid scope identifiers.
This fail-closed rule prevents anonymous or partially configured sessions from writing under
a shared synthetic tenant.

## Memory Record Families

The standards directory defines four provider-neutral v1 envelopes:

- institutional memory records for durable observations, patterns, procedures, and outcomes;
- decision precedent records for scoped decisions and their outcomes;
- thread summary records for concise continuity without raw transcript persistence;
- business-system event mirror records for external events linked by stable identifiers.

These records require organization, site, and actor identity. Device identity and external
references are optional except where an event mirror must identify its source event.

## External References

An external reference contains only generic identity fields:

- `connector_instance_id`;
- `external_record_type`;
- `external_record_id`.

Provider-specific details belong under the namespaced `provider_data` object. Credentials,
passwords, access tokens, API keys, and other secrets are not canonical fields. Connector
registration and provider-specific behavior remain outside Slice 26.

## Privacy and Continuity

Actor and device values are pseudonymous identifiers, not raw personal data. Thread summaries
and institutional memory artifacts must not embed raw chat transcripts. A summary may retain
structured facts needed for deterministic continuity, while the source transcript remains
outside these contracts.

Hash-linked System Log records continue to provide append-only provenance for commitment and
escalation paths. The addition of scope fields changes the record contract but does not alter
canonical hash-chain behavior.

## Boundary with Slice 27

Slice 26 provides the identity contracts and foundational hard filtering needed for safe
retrieval. Slice 27 remains responsible for the broader institutional vector-memory layer,
including indexing policy, corpus lifecycle, and richer memory retrieval behavior. Slice 26
does not implement connector routing, provider adapters, semantic thread routing, or business
workflow behavior.
