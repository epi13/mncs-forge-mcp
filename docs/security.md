# Security model and residual risks

The implementation-mapped review for the current stable-local target is in the
[stable-local Forge threat model](local-threat-model.md). This page remains the concise
operational summary; the detailed model distinguishes controls, evidence, trust assumptions, and
residual risks.

Forge tests and enforces path normalization/containment, symlink escape rejection, protected-path
write rejection, evaluator immutability, argument-array commands, no-shell execution, environment
allowlisting, timeout, stdout/stderr caps, process-group termination on POSIX, file locking, stale
identity rejection, frozen identity drift, ledger tamper detection, strict Provider Protocol
stdout framing, explicit unsupported/`UNKNOWN`, bounded diagnostics, and basic secret redaction.

Provider discovery also checks relative executable containment, symlink escape, executable
permission, optional executable SHA-256 identity, declared provider identity/version, strict
capabilities fields, staleness after executable drift, and allowlisted probe environments.
Unavailable optional providers are informational UNKNOWN; required providers or capabilities are
blockers/UNKNOWN.

Forge is not, by default, a filesystem, container, process, or network sandbox. A malicious
executable already authorized in configuration may use its ambient operating-system permissions
under the default `local-process` runner. Provider inputs are copied to a reduced temporary
workspace, but this is not an OS access-control boundary. Process-tree cleanup is best-effort
outside POSIX process groups.

Projects that declare `[runner] kind = "podman-rootless"` execute inside a rootless container with
network isolation (`--network=none`), a read-only root filesystem and workspace mount, declared
writable mounts only, dropped capabilities, and optional resource bounds (ADR 0016). That adapter
records exactly the properties its flags and confirmed runtime facts enforce; it does not claim
resistance to a hostile host kernel or host root, which remain trusted. Killing the `podman run`
client is followed by best-effort container cleanup; a residual container after a hard kill is a
known limitation. On SELinux hosts podman may relabel declared writable directories.

Configuration and the executable environment remain trusted inputs. Hash-linked state detects
rewriting; it does not provide external timestamping, protected custody, signatures, witnessing,
or independent governance. Secret redaction is defensive and cannot guarantee removal of every
possible secret representation. Ordinary operation requires no network.

Micro-verifier callers cannot supply argv, executables, shell fragments, environment, or working
directories. Changed paths are restricted to candidate/generated scopes and checked for absolute
paths, traversal, containment, file type, protected overlap, and symlink escape. Source regions,
JSON parameter keys/depth/size, request/batch duration, stdout/stderr, witnesses, and result
records are bounded. Commands and environment values are omitted from verifier discovery.
Evaluator runs require freeze/drift checks; status-only disclosure removes repair-enabling detail.

A configured provider is still trusted code. Under the default runner it has ambient host
permissions; under the rootless Podman runner its ambient authority is bounded by the container
property set recorded in the receipt binding, and the container stack remains trusted code.

## Forge Cell specification boundary

Forge Cell adds versioned schemas and offline validation for a future stronger execution boundary.
The current reference implementation can validate a declared policy, test-bundle manifest, and
execution record and can assess whether every requested assurance property was accounted for. It
does not currently enforce namespaces, mounts, seccomp, Landlock, cgroups, network isolation,
`fs-verity`, TPM measurements, confidential execution, or external custody.

Forge Cell intentionally separates a test result from execution assurance. A test may report
`PASS` while assurance remains `UNKNOWN` because process isolation, integrity enforcement,
attestation, or custody was requested but not established. Identity or challenge contradictions
are failures. See [Forge Cell execution assurance](forge-cell.md).

The proposed assurance properties are:

- `policy-bound`;
- `process-isolated`;
- `verity-enforced`;
- `platform-attested`;
- `confidential-attested`; and
- `external-custody`.

A local process or container boundary can constrain a candidate but still trusts the host kernel
and administrator. Host root can generally deny service and may defeat local-only controls. A claim
that root cannot silently forge an accepted result requires fresh external or hardware-backed
evidence, such as an accepted TPM quote, confidential-VM attestation, or separately administered
evaluator. Those backends remain future work and must document their own trusted computing base.

Report vulnerabilities according to [SECURITY.md](../SECURITY.md).
