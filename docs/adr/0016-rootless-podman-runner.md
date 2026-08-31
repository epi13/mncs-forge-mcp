# ADR 0016: Rootless Podman as the first sandbox-capable runner

## Status

Accepted (implemented in this iteration).

## Context

Task 7A extracted the `Runner` port and `LocalProcessRunner`; Task 7B-2 persisted
identity-bound execution-receipt bindings. The remaining Task 7 work was a
sandbox-capable adapter so Forge could produce executions whose isolation
properties are materially stronger than an ambient local process, without
claiming properties that are not enforced.

Rootless Podman is widely available on Linux developer hosts, requires no
daemon running as root, and can enforce network isolation (`--network=none`),
a read-only root filesystem (`--read-only`), capability dropping
(`--cap-drop=all`), declared mounts, and optional cgroup-based resource bounds.

## Decision

1. Add `PodmanRunner` implementing the existing `Runner` port. It wraps each
   declared argv in a fixed, Forge-constructed `podman run` argument array.
   Caller input still cannot choose the executable, launcher flags, working
   directory, or environment; only declared allowlisted environment keys are
   forwarded into the container.
2. Availability probes fail closed. A missing binary, an unsupported client
   version, an unconfirmed-rootless runtime (`podman info` must report
   `host.security.rootless == true`), a missing image, and non-POSIX hosts all
   raise `RUNNER_UNAVAILABLE`. The runner is never silently downgraded to the
   local-process runner.
3. Image identity is resolved through `podman image inspect` digests. A tag
   alone is not treated as an immutable identity; when no digest can be
   resolved, `image_identity` stays unset and containerization is reported as
   not established even though the process ran in a container.
4. Declared writable paths are mounted read-write with a private SELinux label
   (`rw,Z`) nested under the read-only workspace mount. Configuration keeps
   runner writable paths disjoint from protected authority scopes.
5. Selection is additive configuration: an optional `[runner]` section with
   default kind `local-process` preserves historical behavior for every
   existing project.
6. The trusted computing base is stated explicitly: host kernel, the rootless
   container stack (podman/crun), host root, and image contents. The adapter
   does not claim resistance to hostile host root.

## Consequences

- Forge has at least one sandbox-capable execution path whose recorded
  capabilities derive from flags it actually passes plus confirmed runtime
  facts.
- Receipt bindings produced under this runner can establish
  `network_isolation`, `filesystem_isolation`, and `containerization`
  (digest-resolved) while everything else remains `UNKNOWN`.
- Timeout enforcement remains wrapper-side; killing the `podman run` client is
  followed by best-effort container cleanup, and residual containers after a
  hard kill remain a documented limitation.
