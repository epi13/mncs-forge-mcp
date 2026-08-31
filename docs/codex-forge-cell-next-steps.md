# Codex implementation queue: Forge Cell

This queue is the implementation handoff for the larger Forge Cell work. The policy, test-bundle,
and execution-record schemas, reference validator, fail-closed assurance assessment, examples, and
architecture documentation are already established. They are specification and validation
foundations, not an execution sandbox.

Do not implement this entire queue in one branch. Each task should normally be one focused PR and
must preserve the invariants in [`docs/codex-next-steps.md`](codex-next-steps.md).

## Completed foundation

The repository now contains:

- three packaged JSON Schema Draft 2020-12 resources;
- `validate_forge_cell_document(...)`;
- `assess_execution_assurance(...)`;
- reference policy, bundle, and execution record fixtures;
- tests proving that test `PASS` does not promote missing isolation assurance; and
- ADR and threat-model documentation.

The following work remains.

## Progress note (this iteration)

- Cell Task 1 is partially complete: the fail-closed assurance assessment and
  Forge Cell document validation are exposed through the shared operation
  registry (`cell.documents.validate`, `cell.execution.assess`), and Forge now
  persists its own typed `execution_assurance` assessments over receipt
  bindings (ADR 0017). Full Cell Task 1 — policy, bundle, and execution-record
  documents stored as first-class transactional records with canonical
  identities and migration dispatch — remains open.
- Cell Task 2's runner foundation exists as the rootless `PodmanRunner`
  (ADR 0016); a native Linux namespace/landlock/seccomp launcher remains open.

---

## Cell Task 1 — Integrate typed Forge Cell records

**Priority:** P1 after core Task 2  
**Target:** `0.2.x`  
**Depends on:** central Codex Tasks 2, 4, and 7

### Objective

Move the reference documents into the versioned record and runner architecture without changing
their claim meanings.

### Required changes

- define frozen typed policy, bundle, execution-record, and assurance-assessment models;
- preserve the packaged schemas as compatibility snapshots;
- add canonical identity computation for each persisted form;
- add migration/version dispatch and reject unsupported future versions;
- store execution records transactionally with the ledger; and
- expose assurance status separately from the underlying workflow or verifier result.

### Acceptance criteria

- serialization round trips preserve canonical identities;
- old Forge state remains readable;
- malformed or unavailable Forge Cell evidence cannot become `PASS`;
- CLI and MCP output clearly separate `result` and `assurance_status`; and
- no runner is selected from caller-controlled executable, argv, environment, or working directory.

---

## Cell Task 2 — Implement the Linux `ForgeCellRunner`

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Cell Task 1 and central runner Task 7

### Objective

Implement a small Linux-specific launcher that constrains the candidate or provider and produces a
receipt describing only properties actually enforced.

### Required controls

- user, mount, PID, IPC, UTS, and network namespaces;
- read-only root filesystem;
- read-only candidate, test-bundle, and toolchain mounts;
- one or more explicitly declared writable output mounts;
- `pivot_root`, closed inherited descriptors, and `no_new_privs`;
- seccomp profile identity and enforcement;
- Landlock restrictions where supported;
- cgroup v2 CPU, memory, PID, and I/O bounds;
- disabled network by default;
- fixed argument arrays and allowlisted environment; and
- bounded stdout, stderr, time, and process-tree cleanup.

### Acceptance criteria

- capability inspection reports every supported, unavailable, and unenforced feature;
- a requested unavailable feature produces unmet assurance and `UNKNOWN` rather than a silent
  downgrade;
- mount targets and writable paths are normalized, non-overlapping, and symlink-safe;
- candidate processes cannot write tests, policy, runner, root filesystem, or candidate inputs;
- network and resource-limit tests observe the declared behavior; and
- non-Linux platforms report the adapter unavailable without pretending the tests passed.

### Out of scope

Do not claim resistance to hostile host root. Do not add TPM or confidential-VM logic in this PR.

---

## Cell Task 3 — Build immutable test bundles and integrity enforcement

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Cell Tasks 1 and 2

### Objective

Create and verify content-addressed test bundles whose manifest, harness, policy, files, and
expected outputs are bound to one identity.

### Required changes

- deterministic bundle construction with normalized paths and ordering;
- duplicate, traversal, absolute-path, special-file, symlink, and size-limit rejection;
- DSSE/Ed25519 signing and offline trust-policy verification through a declared adapter;
- bundle digest verification before launch and output-manifest verification after execution;
- optional `fs-verity` enablement and enforced-digest recording on supported filesystems; and
- explicit distinction between ordinary content hashing and kernel-enforced integrity.

### Acceptance criteria

- changing one byte changes the bundle identity and invalidates the signature;
- wrong policy, candidate, harness, or bundle combinations are rejected;
- signature expiration, revocation, unknown key, malformed envelope, and wrong payload type fail
  according to declared trust policy;
- absence of `fs-verity` cannot be reported as `verity-enforced`; and
- unsigned development bundles remain explicitly local and do not establish custody or
  independence.

---

## Cell Task 4 — Add challenge-bound execution requests and offline verification

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Cell Tasks 1 through 3

### Objective

Prevent replay and substitution by binding each run to a fresh verifier challenge and provide a
separate verifier for execution receipts.

### Required changes

- generate cryptographically random request IDs and nonces;
- bind nonce, policy, candidate, bundle, runner, root filesystem, executable, environment, and
  outputs into the execution record;
- sign the execution record using a backend-specific key interface;
- implement an offline verifier that checks schema, identities, signature/trust policy, challenge,
  requested/enforced/unmet assurance, expiration, and revocation; and
- record verification as a separate immutable result rather than editing the execution record.

### Acceptance criteria

- replaying an old `PASS` with a new nonce is rejected;
- swapping any material identity is rejected;
- a missing verifier challenge remains `UNKNOWN` when the policy requires freshness;
- local signing is classified as local control rather than independence; and
- verifier behavior is deterministic and network-free for a supplied trust snapshot.

---

## Cell Task 5 — Add the adversarial Forge Cell study

**Priority:** P1 release gate  
**Target:** `0.2.x`  
**Depends on:** Cell Tasks 2 through 4

### Objective

Attack the implementation as a case study and retain machine-readable evidence for every attempted
escape, mutation, replay, and substitution.

### Required corpus

- pre-launch and in-run test mutation;
- runner, policy, rootfs, executable, candidate, and environment substitution;
- symlink, mount, path traversal, inherited descriptor, device, and special-file escape;
- undeclared network access;
- fork bomb, memory, CPU, output, and storage exhaustion;
- child-process escape and cleanup failure;
- ledger, record, output, and manifest replacement or truncation;
- stale challenge replay;
- legitimate runner with wrong bundle or candidate; and
- host-root falsification attempts with the limitation of each assurance level recorded.

### Acceptance criteria

- every case has an expected status and stable failure code;
- unsupported attack instrumentation remains `UNKNOWN` rather than skipped `PASS`;
- the study distinguishes prevention, detection, rejection by an external verifier, and denial of
  service;
- the local study explicitly retains host root in its trusted computing base; and
- results can be reproduced without exposing protected holdout material.

---

## Cell Task 6 — Add TPM-backed measured execution

**Priority:** P2  
**Target:** `0.3.x`  
**Depends on:** Cell Tasks 4 and 5

### Objective

Allow an external verifier to accept fresh platform measurements and make silent local replacement
of the approved boot, kernel, launcher, or policy state detectable.

### Required changes

- define a TPM quote and event-log evidence adapter;
- bind the verifier nonce to the quote;
- define approved measurement-policy snapshots and deterministic evaluation;
- record boot, kernel, launcher, policy, and relevant integrity measurements;
- support key rotation, expiration, revocation, and recovery; and
- keep measured state distinct from organizational independence.

### Acceptance criteria

- stale or wrong-nonce quotes are rejected;
- unapproved measurements cannot produce `platform-attested`;
- a missing or unverifiable event log remains `UNKNOWN`;
- root can deny service but cannot create an accepted quote for a mismatched measured state under
  the declared model; and
- the verifier can operate offline with a supplied trust and measurement snapshot.

---

## Cell Task 7 — Add confidential-VM and protected-test release

**Priority:** P3  
**Target:** after TPM backend stability  
**Depends on:** Cell Tasks 4 through 6

### Objective

Run selected evaluations in an attested hardware-isolated guest and release protected test keys
only to an accepted measured environment.

### Required changes

- define one backend first, such as AMD SEV-SNP or Intel TDX;
- verify guest measurements and fresh challenge evidence externally;
- bind candidate, bundle, policy, runner, and output identities to the attestation;
- implement challenge-bound key release for encrypted holdout tests;
- ensure decrypted tests and keys are not returned in ordinary diagnostics or repair feedback; and
- document side-channel, firmware, availability, and provider trust assumptions.

### Acceptance criteria

- mismatched guest measurement or stale challenge prevents key release;
- the host cannot obtain plaintext holdout material through the normal protocol;
- final evaluation remains separated from same-epoch repair feedback;
- confidential execution is not described as independent custody unless a separate holder exists;
- unsupported hardware remains explicit `UNKNOWN`; and
- the backend can be disabled without changing local Forge behavior.

---

## Cell Task 8 — Add external evaluator and custody adapters

**Priority:** P3  
**Target:** `0.3.x`  
**Depends on:** stable challenge-bound records and central checkpoint Task 8

### Objective

Support evaluation by a separately administered machine or organization without treating a second
same-operator machine as independent.

### Required changes

- immutable job envelopes and encrypted or signed test-bundle delivery;
- authenticated evaluator identity and capability declaration;
- separately held signing keys and trust policy;
- receipt and ledger-head return with challenge binding;
- custody, witnessing, replication, and independence classifications; and
- explicit operator and organization metadata that code validates syntactically but cannot invent.

### Acceptance criteria

- unauthorized evaluator signatures are rejected;
- same-operator remote execution remains same-operator evidence;
- external custody requires a declared external holder and accepted trust policy;
- network interruption and duplicate delivery are idempotent and do not corrupt lineage; and
- unavailable external evidence remains `UNKNOWN` without blocking ordinary local development.

---

## Cell Task 9 — Integrate Forge Cell into CLI, MCP, and distributed workers

**Priority:** P2 after stable runner behavior  
**Target:** `0.3.x`  
**Depends on:** central Tasks 6, 7, and 11 plus the applicable Cell backend tasks

### Objective

Expose controlled runner selection and assurance inspection through the shared operation registry
without turning MCP into a privileged launcher or distributed scheduler.

### Required changes

- project configuration selects only declared runner profiles;
- CLI and MCP expose capability inspection, policy validation, execution request creation, receipt
  verification, and assurance explanation through the same handlers;
- evaluator-only operations stay out of the development MCP inventory;
- distributed workers advertise exact runner and attestation capabilities;
- scheduler matching treats unavailable requested assurance as a blocker or `UNKNOWN`; and
- results remain bound to worker, runner, environment, candidate, bundle, policy, and challenge.

### Acceptance criteria

- caller input cannot supply arbitrary privileged launcher arguments;
- development agents cannot obtain protected tests or final-evaluation diagnostics;
- capability drift invalidates worker registration or the active lease;
- CLI and MCP machine-readable outputs remain compatible; and
- no interface labels a result simply `sandboxed` without the explicit property set.

## Agent completion report

Every Cell PR must report:

- central and Cell task dependencies;
- enforced, unsupported, and intentionally excluded assurance properties;
- trusted computing base and host-root assumptions;
- public record, configuration, CLI, MCP, or Provider Protocol changes;
- exact tests and adversarial cases run;
- environment and hardware limitations; and
- all remaining `UNKNOWN` facts.
