from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mncs_forge.adapters import LocalCommandExecutor
from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError
from mncs_forge.execution import parse_provider_capabilities, parse_provider_response
from mncs_forge.ports import ExecutionResult


def _line(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode() + b"\n"


def _valid_analysis() -> dict[str, Any]:
    return {
        "protocol_version": "0.1",
        "type": "analysis_response",
        "request_id": "request-1",
        "provider": {"id": "provider", "identity": "provider-v1", "version": "1"},
        "status": "UNKNOWN",
        "summary": "bounded response",
        "extensions": {},
    }


def _valid_capabilities() -> dict[str, Any]:
    return {
        "protocol_version": "0.1",
        "type": "capabilities",
        "provider": {"id": "provider", "identity": "provider-v1", "version": "1"},
        "analyses": ["bounded-structural"],
        "statuses": ["PASS", "FAIL", "UNKNOWN"],
        "cancellation": False,
        "health_checks": True,
        "extensions": {
            "supported_constructs": ["direct-calls"],
            "unsupported_constructs": ["dynamic-dispatch"],
            "limitations": ["bounded fixture"],
        },
    }


@pytest.mark.parametrize(
    ("stdout", "code"),
    [
        pytest.param(b"", "PROVIDER_FRAMING", id="empty"),
        pytest.param(b"\n", "PROVIDER_FRAMING", id="blank-line"),
        pytest.param(
            _line({"protocol_version": "0.1"}) + _line({"protocol_version": "0.1"}),
            "PROVIDER_FRAMING",
            id="two-json-lines",
        ),
        pytest.param(
            _line({"protocol_version": "0.1"}) + b"\n",
            "PROVIDER_FRAMING",
            id="trailing-blank-line",
        ),
        pytest.param(b"\xff\n", "PROVIDER_FRAMING", id="invalid-utf8"),
        pytest.param(b"{" + b"x" * 65536, "PROVIDER_MALFORMED", id="oversized-malformed-json"),
        pytest.param(_line([]), "PROVIDER_MALFORMED", id="non-object-json"),
    ],
)
def test_provider_framing_corpus_fails_closed(stdout: bytes, code: str) -> None:
    with pytest.raises(ForgeError) as issue:
        parse_provider_response(stdout)
    assert issue.value.code == code


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("protocol_version", None, id="missing-protocol-version"),
        pytest.param("protocol_version", "0.2", id="unsupported-protocol-version"),
        pytest.param("type", None, id="missing-type"),
        pytest.param("type", 3, id="numeric-type"),
        pytest.param("provider", None, id="missing-provider"),
        pytest.param("provider", [], id="list-provider"),
        pytest.param("extensions", None, id="null-extensions"),
        pytest.param("extensions", [], id="list-extensions"),
        pytest.param("status", "pass", id="lowercase-status"),
        pytest.param("status", 1, id="numeric-status"),
        pytest.param("status", {}, id="object-status"),
        pytest.param("status", [], id="list-status"),
    ],
)
def test_provider_metadata_and_status_mutations_never_become_analysis_pass(
    field: str, value: object
) -> None:
    response = _valid_analysis()
    response[field] = value
    expected = "PROVIDER_UNSUPPORTED" if field == "protocol_version" else "PROVIDER_MALFORMED"
    with pytest.raises(ForgeError) as issue:
        parse_provider_response(_line(response))
    assert issue.value.code == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param(
            "analyses", ["bounded-structural", "bounded-structural"], id="duplicate-analysis"
        ),
        pytest.param("analyses", [""], id="empty-analysis"),
        pytest.param("analyses", [None], id="null-analysis"),
        pytest.param("statuses", [], id="empty-statuses"),
        pytest.param("statuses", ["pass"], id="lowercase-status-declaration"),
        pytest.param("statuses", ["PASS", 1], id="numeric-status-declaration"),
        pytest.param("cancellation", None, id="null-cancellation"),
        pytest.param("cancellation", "false", id="string-cancellation"),
        pytest.param("health_checks", None, id="null-health-checks"),
        pytest.param("health_checks", {}, id="object-health-checks"),
        pytest.param("extensions", {"supported_constructs": [""]}, id="empty-supported-construct"),
        pytest.param(
            "extensions", {"unsupported_constructs": [None]}, id="null-unsupported-construct"
        ),
        pytest.param("extensions", {"limitations": "not-an-array"}, id="string-limitations"),
    ],
)
def test_capability_mutation_corpus_remains_malformed(field: str, value: object) -> None:
    response = _valid_capabilities()
    response[field] = value
    with pytest.raises(ForgeError) as issue:
        parse_provider_capabilities(_line(response))
    assert issue.value.code == "PROVIDER_MALFORMED"


_json_scalars = st.one_of(
    st.none(), st.booleans(), st.integers(min_value=-1000, max_value=1000), st.text(max_size=20)
)
_json_values = st.recursive(
    _json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=4), st.dictionaries(st.text(max_size=12), children, max_size=4)
    ),
    max_leaves=12,
)


@given(value=_json_values)
@settings(max_examples=60, deadline=None, derandomize=True, database=None)
def test_arbitrary_bounded_json_cannot_create_an_invalid_provider_success(value: object) -> None:
    try:
        response = parse_provider_response(_line(value))
    except ForgeError:
        return
    assert response["protocol_version"] == "0.1"
    assert response["type"] in {
        "analysis_response",
        "capabilities",
        "health_response",
        "error",
        "cancelled",
    }
    assert isinstance(response["provider"], dict)
    assert isinstance(response["extensions"], dict)
    if response["type"] == "analysis_response":
        assert response["status"] in {"PASS", "FAIL", "UNKNOWN"}


def test_probe_identity_completeness_is_unknown_not_pass(
    config: ForgeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed = _valid_capabilities()
    malformed["provider"] = {"id": "provider"}

    def execute(
        _self: LocalCommandExecutor,
        command: object,
        **kwargs: object,
    ) -> ExecutionResult:
        del kwargs
        return ExecutionResult(
            argv=[str(item) for item in command] if isinstance(command, list) else [],
            returncode=0,
            stdout=_line(malformed),
            stderr=b"",
            duration_seconds=0.001,
        )

    monkeypatch.setattr(LocalCommandExecutor, "execute", execute)
    result = Forge(config).provider_probe("provider-pass")

    assert result["status"] == "UNKNOWN"
    assert result["error_code"] == "PROVIDER_MALFORMED"
