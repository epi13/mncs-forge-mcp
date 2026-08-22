"""Identity-bearing Forge evaluations for Concept Reconstruction Experiments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import ForgeError

CONCEPT_EVALUATION_SCHEMA = "mncs-forge.concept-evaluation.v0.1"


def _text(value: object, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ForgeError("CONCEPT_EVALUATION_INVALID", f"{field} must be bounded text")
    return value.strip()


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_concept_evaluation(
    *,
    concept_experiment_id: str,
    candidate_identity: str,
    language_profile: str,
    compiler_identity: str,
    backend_identity: str,
    execution_identities: Iterable[str],
    verifier_identity: str,
    verifier_version: str,
    obligation: str,
    evidence_identities: Iterable[str],
    status: str,
    unresolved_obligations: Iterable[str] = (),
    generator_identity: str | None = None,
    evaluator_policy_identity: str | None = None,
) -> dict[str, Any]:
    """Build a bounded Forge-native result without candidate self-certification."""

    if status not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ForgeError("CONCEPT_EVALUATION_STATUS", "status must preserve PASS, FAIL, or UNKNOWN")
    verifier_identity = _text(verifier_identity, "verifier_identity")
    if generator_identity is not None and verifier_identity == generator_identity:
        raise ForgeError(
            "CONCEPT_EVALUATION_SELF_CERTIFICATION",
            "candidate generator and evaluator identities must be distinct",
        )
    material: dict[str, Any] = {
        "schema_version": CONCEPT_EVALUATION_SCHEMA,
        "producer": "mncs-forge",
        "concept_experiment_id": _text(concept_experiment_id, "concept_experiment_id", 256),
        "candidate_identity": _text(candidate_identity, "candidate_identity"),
        "language_profile": _text(language_profile, "language_profile"),
        "compiler_identity": _text(compiler_identity, "compiler_identity"),
        "backend_identity": _text(backend_identity, "backend_identity"),
        "execution_identities": sorted(
            {_text(item, "execution_identities[]") for item in execution_identities}
        ),
        "verifier_identity": verifier_identity,
        "verifier_version": _text(verifier_version, "verifier_version", 256),
        "obligation": _text(obligation, "obligation"),
        "evidence_identities": sorted(
            {_text(item, "evidence_identities[]") for item in evidence_identities}
        ),
        "status": status,
        "unresolved_obligations": sorted(
            {_text(item, "unresolved_obligations[]") for item in unresolved_obligations}
        ),
        "generator_identity": generator_identity,
        "evaluator_policy_identity": evaluator_policy_identity,
        "generator_certified": False,
        "interpretation": "bounded_forge_evaluation_not_mncs_conformance",
        "claim_boundary": (
            "Forge evaluator scope only; candidate generation, Language semantics, Fabric "
            "execution, scientific interpretation, and MNCS conformance remain separate"
        ),
    }
    content_digest = _digest(material)
    return {
        **material,
        "stable_id": f"mncs-forge://evaluation/{content_digest[7:]}",
        "content_digest": content_digest,
    }
