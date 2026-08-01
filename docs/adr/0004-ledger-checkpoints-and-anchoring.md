# ADR 0004: Ledger checkpoints and external anchoring

- **Status:** Proposed
- **Target:** `0.2.x`

## Context

The local Forge ledger is append-only and hash linked. It detects truncation, reordering, and
modification when the retained ledger is verified, but an operator with sufficient local access
can replace the ledger and all related records together. The current design intentionally does not
claim external timestamping, protected custody, witnessing, or organizational independence.

Forge needs a way to bind a local history to externally retained evidence without making stronger
claims than the receipt and holder relationship support.

## Decision

Forge will support periodic checkpoint records containing at least:

- project identity;
- ledger range and head identity;
- checkpoint format and hash algorithm;
- material Forge and environment identities;
- creation time as an informational field; and
- checkpoint identity.

Checkpoint heads may receive detached signatures, publication receipts, or witness receipts.
Receipts must be verifiable offline and retained as separate immutable records. Forge will classify
properties independently rather than treating them as one boolean trust state:

- local chain valid;
- checkpoint created;
- externally anchored;
- witnessed;
- protected custody; and
- independently held.

A self-signature or another machine controlled by the same operator does not establish
organizational independence. A receipt can support only the property and scope explicitly declared
by its format and holder.

## Consequences

Positive consequences:

- replacement of locally retained history can be detected against an externally held checkpoint;
- multiple witnesses can retain separate receipts;
- offline operation remains possible; and
- custody and independence claims remain explicit rather than inferred.

Costs and risks:

- key handling, revocation, expiration, and holder identity require careful policy;
- external availability does not by itself establish independence; and
- receipt verification failure must not erase valid local history, though it may leave stronger
  claims `UNKNOWN` or `FAIL` according to policy.

## Required evidence before acceptance

- a retained receipt detects a substituted local ledger head;
- malformed, mismatched, expired, or revoked receipts fail according to an explicit policy;
- multiple receipts are preserved rather than overwritten;
- self-controlled anchoring remains classified as self-controlled; and
- ordinary local Forge use does not require a network service or signing key.
