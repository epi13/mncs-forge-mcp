# Forge Cell reference artifacts

These files define a non-executing reference example for the proposed Forge Cell boundary:

- `policy.json` requests policy binding and process isolation;
- `test-bundle.json` identifies the test material and declares local operator custody; and
- `execution-record.json` records a successful test whose process-isolation request was not
  established.

The execution result is `PASS`, while `assess_execution_assurance(...)` returns `UNKNOWN`. This is
intentional: test behavior and evidence assurance are different claims.

The example does not launch a sandbox, verify a signature, establish protected custody, or produce
independent evidence.
