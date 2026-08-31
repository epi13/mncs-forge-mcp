# ADR 0009: Recoverable local record and ledger commits

- **Status:** Accepted; implemented in Task 4
- **Target:** `0.1.0a3`

## Context

Forge previously wrote an immutable typed record with `O_EXCL` and then independently appended its
ledger entry under a different lock. Process loss could leave record-only state, and concurrent
writers had no boundary encompassing both storage objects. Lifecycle authorization could be valid
while its attempted persistence remained incomplete.

## Decision

Introduce a narrow typed `RecordStore` protocol and a local implementation. One exclusive state
lock serializes preparation, expected-head calculation, record publication, and ledger publication.
A durable on-disk journal binds staged bytes to the exact expected sequence and previous hash and
distinguishes `PREPARED` from `COMMITTED`. Startup resolves transactions before state-machine
projection and fails closed when durable evidence is contradictory.

The ledger plus its immutable companions remain authoritative. A rebuildable local index and
in-process digest cache accelerate reads but cannot establish or replace evidence. Raw historical
ledger bytes are verified before typed migration and are never rewritten by startup recovery.

A durable verifier action without a terminal result is execution recovery, not an incomplete
storage transaction. Forge records one terminal `UNKNOWN` after establishing that no cooperating
executor holds the action lock; it never reconstructs a provider semantic result.

## Consequences

Positive consequences:

- authorized writes have one recoverable record-plus-ledger commit boundary;
- cooperating threads and processes cannot allocate the same next sequence;
- tested interruption points converge to a complete old or complete new state;
- immutable-file deletion or replacement is detected during ledger verification; and
- storage machinery does not enter domain identities or state-machine policy.

Costs and limits:

- local writers serialize, and staging a complete replacement ledger is linear in ledger size;
- directory synchronization is best effort where Python/platform support is weaker, notably some
  Windows filesystems, while logical journal recovery remains available;
- the local index is not an external checkpoint or anchor; and
- hostile host/root mutation, independent custody, witnessing, and certification remain outside
  this local consistency guarantee.

Task 5 may inject the protocol into smaller application services. Remote stores, databases,
external checkpoints, signatures, and replication are intentionally deferred.
