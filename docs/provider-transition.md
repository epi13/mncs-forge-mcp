# Forge and provider transition

Forge is the project-facing orchestration and evidence-control layer, not a graph
analyzer. Joern was demoted from mandatory policy so projects select evidence by declared
capability, method, scope, identity, and limitation instead of by one tool brand.

Historical Joern snapshots, study outputs, frozen baselines, case-study evidence, RFC
history, fixtures, and compatibility records remain unchanged. The transition does not
delete Joern programs, caches, repositories, or evidence.

Joern can still be used through an explicitly configured Provider Protocol 0.1 adapter.
The Joern CLI itself is not a Provider Protocol adapter. Copy and complete the disabled
fragment in `examples/providers/joern-legacy.toml.example`, pin identities when policy
requires them, validate the project configuration, and explicitly probe the adapter.
Another provider may declare equivalent, narrower, broader, or different capabilities
and constructs; Forge reports those differences without treating providers as
interchangeable.

Forge does not replace structural facts with source reading, grep, or line counts. An
unavailable optional provider is an informational UNKNOWN. A required provider or
capability that is unavailable, stale, unprobed, malformed, timed out, or unsupported is
a blocker/UNKNOWN. A zero exit without a recognized structured response is not PASS.

For comparative graph-sensitive evidence, run the same provider, method, scope, and
relevant bounds before and after the change. The rollback path is to restore an explicit
optional profile or a verified project-owned MCP registration and revert the policy
commit; frozen evidence is never rewritten as part of rollback.

The transition audit classified mandatory `AGENTS.md`/`CONTRIBUTING.md` language as
replaceable policy, the host pipx `joern-agent-bridge` registration as unrelated and
untouched, and all other Joern references as historical evidence, optional compatibility,
or preserved documentation.
