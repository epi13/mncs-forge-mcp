# Security model and residual risks

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

Forge is not a filesystem, container, process, or network sandbox. A malicious executable already
authorized in configuration may use its ambient operating-system permissions. Provider inputs are
copied to a reduced temporary workspace, but this is not an OS access-control boundary. Use a
container or host sandbox when adversarial providers are in scope. Process-tree cleanup is
best-effort outside POSIX process groups.

Configuration and the executable environment remain trusted inputs. Hash-linked state detects
rewriting; it does not provide external timestamping, protected custody, signatures, witnessing,
or independent governance. Secret redaction is defensive and cannot guarantee removal of every
possible secret representation. Ordinary operation requires no network.

Report vulnerabilities according to [SECURITY.md](../SECURITY.md).
