# Transactional local storage

Forge persists each ledger-backed typed record through `LocalRecordStore`. Lifecycle authority
remains in `ForgeStateMachine`: authorization happens first, the typed record is constructed next,
and only a successful storage commit becomes projected history. Storage success does not prove that
a transition was authorized.

## Transaction boundary

All cooperating writers use `.mncs-forge/ledger.lock` as the transaction lock. Under that
exclusive lock the store
validates the immutable group, ledger kind, typed record, schema version, identity, destination,
and duplicate state. It then binds a transaction to the exact expected ledger sequence and
`previous_hash`; recovery never rebases a prepared transaction onto a different head.

The inspectable transaction directory contains only bounded canonical record bytes, a staged
replacement ledger, and a journal with storage metadata and SHA-256 digests. Transaction IDs,
staging paths, and index offsets never enter evidence records or their identity projections.

```text
authorize transition
  -> construct typed record
  -> acquire ledger.lock transaction boundary
  -> stage record and complete next ledger image
  -> persist PREPARED journal
  -> publish immutable record
  -> verify expected ledger predecessor
  -> publish ledger
  -> persist COMMITTED journal
  -> rebuild derived index and remove journal
```

The complete ledger is staged and replaced on the same filesystem. This preserves all prior raw
bytes, including legacy lines, and avoids exposing a truncated appended line after interruption.
Identical duplicate commits are idempotent. The same identity with competing bytes, an unexpected
ledger head, or an incomplete pre-existing representation fails with a specific storage conflict.

## Recovery

Forge opens storage and recovers journals before ordinary state reads. Recovery is deterministic
and idempotent:

- staging without a durable journal is abandoned before either public object could have changed;
- a valid `PREPARED` journal with the old ledger completes the recorded transaction;
- a transaction whose exact new ledger and record are already public is recognized and completed;
- a `COMMITTED` journal is checked, indexed, and cleaned up; and
- malformed journals, substituted stages, conflicting records, wrong predecessors, and states
  matching neither the old nor new digest fail closed without deleting contradictory material.

Recovery therefore converges to either no record/no entry with the previous head, or one valid
record/one linked entry with the new head. It does not accept record-only, ledger-only, duplicate,
or rebased results.

Low-level ledger reads that encounter an unresolved transaction fail with `RECOVERY_REQUIRED`;
they do not project a lifecycle state around pending storage work.

Storage recovery is separate from verifier execution recovery. A completely committed verifier
action may outlive the process that was running its provider. Per-action OS locks distinguish a
live cooperating executor from a stranded action. After restart, a stranded action receives
exactly one terminal `UNKNOWN` bound to the original action. The recovery result records
operational uncertainty and cannot manufacture PASS or FAIL provider evidence.

## Verification and derived index

Ledger verification first checks the raw historical JSONL sequence, links, and hashes. Only then
does it normalize typed payloads and verify each ledger-backed immutable companion: canonical
path, expected type, parseability, identity, and payload equality. Current records must also retain
their canonical serialized bytes. Historical `0.1` bytes are never rewritten and are migrated only
after their raw chain is valid.

`.mncs-forge/ledger-index.json` records the current ledger digest, head, entry count, sequences by
kind, and identity-to-sequence locations. It is local acceleration/recovery metadata, not evidence
and not an external checkpoint. Every open validates it when present against authoritative ledger
bytes; stale or malformed index data is discarded and rebuilt. An in-process cache similarly reuses parsed
history only while the SHA-256 digest of the complete ledger bytes remains unchanged.

## Filesystem and authority limits

Forge writes and syncs staged contents before rename and syncs containing directories where Python
and the operating system support directory handles. Linux and macOS expose the strongest tested
file-plus-directory durability behavior. Windows uses closed handles, `os.replace`, file flushes,
and the same logical journal recovery, but Python may not expose equivalent directory `fsync` on
every filesystem. The logical old-or-new recovery invariant is cross-platform; identical physical
power-loss guarantees are not claimed where the platform primitive is unavailable.

This protocol establishes local consistency on an operator-controlled filesystem. It is not
tamper-proof storage and does not establish external anchoring, independent custody, witnessing,
certification, governance approval, or promotion.
