# MNCS Forge usage

Inspect, begin an epoch, register candidates, run declared checks, compare, select, freeze,
then use a separately configured evaluator-mode process. Keep MNCS and MNCDS results
separate and preserve `UNKNOWN`.

List configured providers before selecting analysis. Probe only explicitly, and treat
unavailable or unsupported required capabilities as blockers/UNKNOWN. Forge orchestrates
providers; it is not a graph analyzer. Joern is optional and is not configured by default.

List or deterministically match declared micro-verifiers without execution. Run only an
explicit verifier ID or bounded batch, retain `UNKNOWN`, inspect witnesses and limitations,
and treat evaluator status-only results as non-repair feedback.
