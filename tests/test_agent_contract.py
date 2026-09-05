"""Pin the Forge agent contract to the ecosystem authority table."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "AGENTS.md"


def contract_text() -> str:
    assert CONTRACT.is_file(), "AGENTS.md (agent execution contract) is missing"
    return CONTRACT.read_text(encoding="utf-8")


def test_contract_claims_assurance_role_and_routes_language():
    text = contract_text()
    assert "assurance semantics" in text
    assert "mncs-language" in text
    assert "development-pressure" in text
    assert "tests/test_agent_contract.py" in text


def test_contract_keeps_unknown_distinct():
    text = contract_text()
    assert "`UNKNOWN`" in text
