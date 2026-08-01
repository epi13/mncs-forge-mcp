# Provider Protocol integration

Forge uses MNCS Provider Protocol 0.1 rather than defining another analyzer protocol. A provider
command must be declared both in `[[providers]]` and in its workflow. Forge sends one bounded JSON
Lines request and accepts exactly one response line. It preserves protocol version, provider
identity, method, status, compact witnesses, limitations, unsupported constructs, duration,
bounded stderr diagnostics, and output identity.

Capabilities and health are protocol concepts. Forge does not automatically execute them during
ordinary inspection. Timeouts terminate the provider process group where practical. Provider
stderr never enters protocol stdout framing. Public MNCS `provider inspect`, `provider run`, and
`provider verify-result` commands remain available for independent verification.

`providers probe` sends a capabilities request only after executable containment, availability,
and optional pinned-identity checks. The response must be one recognized capabilities object with
provider name/id, identity/version, analyses, statuses, cancellation, health-check support, and
well-formed extensions. Exit zero with text, malformed JSON, the wrong response type, timeout,
output overflow, or identity drift remains UNKNOWN.

Capability blockers are satisfied only by a current successful probe whose returned analyses
include the required capability and do not mark it unsupported. Declared capability without a
current probe is not PASS. See the [provider transition](provider-transition.md) for the optional
legacy Joern adapter profile.
