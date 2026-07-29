from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mncs_forge.config import ForgeConfig, load_config


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for directory in (
        "candidate",
        "generated",
        "contract",
        "reference",
        "evaluator",
        "evidence",
        "protected",
        "output",
    ):
        (tmp_path / directory).mkdir()
    (tmp_path / "candidate/main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "contract/contract.md").write_text("Return VALUE.\n", encoding="utf-8")
    (tmp_path / "reference/reference.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "evaluator/policy.json").write_text(
        '{"required":["pass-check"]}\n', encoding="utf-8"
    )
    (tmp_path / "evidence/result.json").write_text('{"status":"UNKNOWN"}\n', encoding="utf-8")
    (tmp_path / "protected/holdout.txt").write_text("sealed\n", encoding="utf-8")
    fixture = Path(__file__).parent / "fixtures/fake_provider.py"
    python = sys.executable
    providers = [
        ("provider-pass", "PASS"),
        ("provider-fail", "FAIL"),
        ("provider-unknown", "UNKNOWN"),
        ("provider-malformed", "MALFORMED"),
        ("provider-oversize", "OVERSIZE"),
    ]
    provider_tables = "\n".join(
        (
            "[[providers]]\n"
            f"id = {json.dumps(name)}\n"
            f"command = {json.dumps([python, str(fixture), mode])}\n"
        )
        for name, mode in providers
    )
    provider_workflows = "\n".join(
        (
            "[[workflows]]\n"
            f"name = {json.dumps(name)}\n"
            'category = "bounded_structural_analysis"\n'
            'mode = "development"\n'
            f"command = {json.dumps([python, str(fixture), mode])}\n"
            "provider_protocol = true\n"
            f"provider_id = {json.dumps(name)}\n"
        )
        for name, mode in providers
    )
    config = f"""
version = 1
environment_allowlist = ["PATH", "LANG", "LC_ALL"]

[project]
name = "fixture"
identity = "fixture-v1"
root = "."

[paths]
candidates = ["candidate"]
generated = ["generated"]
contracts = ["contract"]
references = ["reference"]
evaluators = ["evaluator"]
acceptance_policies = ["evaluator/policy.json"]
development_evidence = ["evidence"]
protected = ["protected"]
outputs = ["output"]

[limits]
timeout_seconds = 0.5
output_bytes = 4096

[commands]
mncs = [{json.dumps(python)}]
mncds = [{json.dumps(python)}]

[authority.development]
may_write_candidates = true
may_write_generated = true
may_run_providers = true

[authority.evaluator]
candidate_read_only = true
authority_read_only = true
require_frozen_identities = true
withhold_repair_feedback = true

[policies]
selection = "evaluator/policy.json"
useful_benefit_objective = "contract/contract.md"

{provider_tables}
{provider_workflows}

[[workflows]]
name = "pass-check"
category = "inspection"
mode = "development"
command = {json.dumps([python, "-c", "import json; print(json.dumps({'status':'PASS'}))"])}
provider_protocol = false

[[workflows]]
name = "fail-check"
category = "build"
mode = "development"
command = {json.dumps([python, "-c", "import sys; sys.exit(7)"])}
provider_protocol = false

[[workflows]]
name = "timeout-check"
category = "inspection"
mode = "development"
command = {json.dumps([python, "-c", "import time; time.sleep(5)"])}
provider_protocol = false

[[workflows]]
name = "output-check"
category = "inspection"
mode = "development"
command = {json.dumps([python, "-c", "print('x' * 100000)"])}
provider_protocol = false

[[workflows]]
name = "injection-check"
category = "inspection"
mode = "development"
command = {
        json.dumps(
            [
                python,
                "-c",
                "import json; print(json.dumps({'status':'PASS'}))",
                ";touch",
                "PWNED",
            ]
        )
    }
provider_protocol = false

[[workflows]]
name = "evaluator-pass"
category = "inspection"
mode = "evaluator"
command = {json.dumps([python, "-c", "import json; print(json.dumps({'status':'PASS'}))"])}
provider_protocol = false
disclosure = "status-only"
"""
    (tmp_path / "mncs-forge.toml").write_text(config, encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(project: Path) -> ForgeConfig:
    return load_config(project / "mncs-forge.toml")
