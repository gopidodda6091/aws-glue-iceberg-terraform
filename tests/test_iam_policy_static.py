"""Static guard-rails on the Terraform IAM module: no wildcard actions."""

from __future__ import annotations

import re
from pathlib import Path

IAM_MAIN = Path(__file__).resolve().parents[1] / "terraform" / "modules" / "iam" / "main.tf"
ACTIONS = re.compile(r"actions\s*=\s*\[([^\]]*)\]")


def _actions() -> list[str]:
    text = IAM_MAIN.read_text(encoding="utf-8")
    found: list[str] = []
    for block in ACTIONS.findall(text):
        found += re.findall(r'"([^"]+)"', block)
    return found


def test_iam_module_declares_actions() -> None:
    assert len(_actions()) >= 10


def test_no_wildcard_actions_in_job_role() -> None:
    offenders = [a for a in _actions() if "*" in a]
    assert offenders == []


def test_only_metrics_statement_uses_star_resource() -> None:
    text = IAM_MAIN.read_text(encoding="utf-8")
    star_resources = re.findall(r'resources\s*=\s*\["\*"\]', text)
    assert len(star_resources) == 1
    assert '"cloudwatch:namespace"' in text
