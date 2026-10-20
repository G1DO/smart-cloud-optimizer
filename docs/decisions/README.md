# Decisions

No standalone Architecture Decision Records (ADRs) have been adopted yet —
that is the N/A status being recorded here, not a missing folder.

Reason: cross-cutting choices on `main` are currently documented inline where
they are implemented and explained:

- Optimizer approach (LP for compute right-sizing, rules for the rest),
  headroom, and clear-then-replace semantics —
  [engines/optimizer.md](../architecture/engines/optimizer.md) (`Design rationale`, `Usage`).
- Trust boundary (client-supplied `user_id` is filtering, not authorization)
  and connection identity/verification —
  [architecture README](../architecture/README.md) (`Trust boundary`,
  `Connection identity and verification`).
- SQLite access rules (storage facade preferred, some routes use direct SQL;
  transaction ownership) — [Storage API](../api/storage.md).
- Local runtime exposure, persistence, and recovery —
  [operations](../operations/local-runtime.md).

Rule going forward: any new cross-cutting or hard-to-reverse decision must add
a dated note under this folder (`docs/decisions/YYYY-MM-DD-<topic>.md`) in the
same change as the code/docs it affects, and link it from the affected
architecture page.
