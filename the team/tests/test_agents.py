"""Unit tests for the four specialized agents.

These tests exercise each agent in isolation: PM produces a validated PRD,
user stories, and task queue; the architect derives schema/ERD/API contract;
the developer generates runnable code (proven by running the generated
project's own pytest suite); and QA correctly passes clean code while
flagging deliberately broken and insecure code.
"""

import asyncio
import pathlib
import subprocess
import sys

from src.agents.architect import ArchitectAgent
from src.agents.base import AgentContext, Reporter
from src.agents.developer import DeveloperAgent
from src.agents.product_manager import ProductManagerAgent
from src.agents.qa_auditor import QAAuditorAgent
from src.models import (
    AgentRole,
    ArtifactKind,
    Severity,
    Sprint,
    WorkflowMode,
)

IDEA = "Build a task management app with user authentication and notifications"


def _run(coro):
    return asyncio.run(coro)


def _context():
    """A self-contained sprint + reporter context for isolated agent runs."""
    sprint = Sprint(idea=IDEA, mode=WorkflowMode.SEQUENTIAL)
    return AgentContext(sprint=sprint, workflow_mode=sprint.mode, reporter=Reporter())


def _pm_payloads(idea=IDEA):
    ctx = _context()
    return _run(ProductManagerAgent().run(ctx, {"idea": idea}))


def _prd_content(idea=IDEA):
    payloads = _pm_payloads(idea)
    return [p for p in payloads if p.kind is ArtifactKind.PRD][0].content


def _architect_payloads(idea=IDEA):
    ctx = _context()
    return _run(ArchitectAgent().run(ctx, {"prd": _prd_content(idea)}))


def _developer_payloads(task=None):
    ctx = _context()
    prd = _prd_content()
    schema = {p.kind.value: p.content for p in _architect_payloads()}
    inputs = {"prd": prd, "schema": schema}
    if task:
        inputs["task"] = task
    return _run(DeveloperAgent().run(ctx, inputs))


def _code_content(task=None):
    payloads = _developer_payloads(task)
    return [p for p in payloads if p.kind is ArtifactKind.SOURCE_CODE][0].content


# ---------------------------------------------------------------------------
# Product Manager
# ---------------------------------------------------------------------------


def test_pm_produces_prd_stories_and_task_queue():
    payloads = _pm_payloads()
    kinds = {p.kind for p in payloads}
    assert kinds == {
        ArtifactKind.PRD,
        ArtifactKind.USER_STORIES,
        ArtifactKind.TASK_QUEUE,
    }


def test_pm_prd_has_structured_content():
    prd = _prd_content()
    assert prd["project_name"]
    assert len(prd["goals"]) >= 3
    assert len(prd["features"]) >= 3
    keys = [f["key"] for f in prd["features"]]
    assert "core_api" in keys
    assert "task_management" in keys
    assert "authentication" in keys


def test_pm_detects_features_from_idea_keywords():
    prd = _prd_content("Build a payments platform with billing and reporting")
    keys = [f["key"] for f in prd["features"]]
    assert "payments" in keys
    assert "reporting" in keys
    assert "core_api" in keys


def test_pm_task_queue_is_role_assigned_and_acceptance_criteria_checked():
    payloads = _pm_payloads()
    queue = [p for p in payloads if p.kind is ArtifactKind.TASK_QUEUE][0].content
    tasks = queue["tasks"]
    assert len(tasks) >= 5
    roles = {t["role"] for t in tasks}
    assert roles == {AgentRole.ARCHITECT.value, AgentRole.DEVELOPER.value, AgentRole.QA_AUDITOR.value}
    for task in tasks:
        assert task["id"]
        assert task["title"]
        assert len(task["acceptance_criteria"]) >= 1
    dev_tasks = [t for t in tasks if t["role"] == AgentRole.DEVELOPER.value]
    assert all(t["feature_key"] for t in dev_tasks)


def test_pm_user_stories_follow_standard_shape():
    payloads = _pm_payloads()
    stories = [p for p in payloads if p.kind is ArtifactKind.USER_STORIES][0].content["stories"]
    assert len(stories) >= 1
    for story in stories:
        assert story["as_a"]
        assert story["i_want"]
        assert story["so_that"]


# ---------------------------------------------------------------------------
# Architect
# ---------------------------------------------------------------------------


def test_architect_produces_schema_erd_and_api_contract():
    payloads = _architect_payloads()
    kinds = {p.kind for p in payloads}
    assert kinds == {ArtifactKind.FOLDER_SCHEMA, ArtifactKind.ERD, ArtifactKind.API_CONTRACT}


def test_architect_folder_schema_covers_generated_files():
    schema = [p for p in _architect_payloads() if p.kind is ArtifactKind.FOLDER_SCHEMA][0].content
    tree = schema["tree"]
    assert "models.py" in tree
    assert "main.py" in tree
    assert "routes/" in tree
    assert "tests/" in tree
    assert "conftest.py" in tree
    paths = {entry["path"] for entry in schema["structure"]}
    assert any("src/routes" in path for path in paths)
    assert any("requirements.txt" in path for path in paths)


def test_architect_erd_has_entities_fields_and_relations():
    erd = [p for p in _architect_payloads() if p.kind is ArtifactKind.ERD][0].content
    entities = erd["entities"]
    names = {e["name"] for e in entities}
    assert "User" in names
    assert "Task" in names
    assert "Notification" in names
    for entity in entities:
        assert entity["table"]
        assert len(entity["fields"]) >= 2
        for field in entity["fields"]:
            assert field["name"]
            assert field["type"] in {"integer", "string", "boolean", "float"}
        if entity["name"] != "User":
            assert any(r["target"] == "User" for r in entity["relations"])


def test_architect_api_contract_documents_crud_endpoints():
    api = [p for p in _architect_payloads() if p.kind is ArtifactKind.API_CONTRACT][0].content
    methods = {(e["method"], e["path"]) for e in api["endpoints"]}
    assert ("GET", "/health") in methods
    assert ("POST", "/api/v1/tasks") in methods
    assert ("GET", "/api/v1/tasks/{id}") in methods
    assert ("DELETE", "/api/v1/tasks/{id}") in methods
    assert api["base_path"] == "/api/v1"


# ---------------------------------------------------------------------------
# Developer
# ---------------------------------------------------------------------------


def test_developer_generates_runnable_project_files():
    code = _code_content()
    files = code["files"]
    assert any(key.endswith("src/main.py") for key in files)
    assert any(key.endswith("src/models.py") for key in files)
    assert any("src/routes/" in key and key.endswith(".py") for key in files)
    assert any("tests/" in key and key.endswith(".py") for key in files)
    assert any(key.endswith("requirements.txt") for key in files)
    assert code["feature_keys"]


def test_generated_code_parses_without_syntax_errors():
    code = _code_content()
    for path, content in code["files"].items():
        if path.endswith(".py"):
            compile(content, path, "exec")  # raises SyntaxError if broken


def test_developer_honors_itemized_task_feature():
    code = _code_content(task={"id": "T-DEV-01", "title": "Implement Payments", "feature_key": "payments"})
    files = code["files"]
    assert code["feature_keys"] == ["payments"]
    assert any(key.endswith("src/routes/payments.py") for key in files)
    assert any(key.endswith("tests/test_payments.py") for key in files)


def test_generated_project_passes_its_own_test_suite(tmp_path):
    """Write the generated project to disk and run pytest inside it."""
    code = _code_content()
    root = tmp_path / "generated"
    for relpath, content in code["files"].items():
        out = root / relpath
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"Generated tests failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# QA Auditor
# ---------------------------------------------------------------------------


def test_qa_passes_clean_generated_code():
    ctx = _context()
    payloads = _run(QAAuditorAgent().run(ctx, {"code": _code_content()}))
    report = [p for p in payloads if p.kind is ArtifactKind.AUDIT_REPORT][0].content
    assert report["passed"] is True
    assert report["score"] == 100
    assert report["findings"] == []
    assert "syntax" in " ".join(report["checks_run"])


def test_qa_flags_syntax_errors_as_critical():
    ctx = _context()
    code = {
        "project_name": "Broken",
        "files": {
            "broken/src/main.py": "def broken(  # unterminated signature\n",
        },
    }
    payloads = _run(QAAuditorAgent().run(ctx, {"code": code}))
    report = [p for p in payloads if p.kind is ArtifactKind.AUDIT_REPORT][0].content
    assert report["passed"] is False
    syntax_findings = [f for f in report["findings"] if f["category"] == "syntax"]
    assert syntax_findings
    assert syntax_findings[0]["severity"] == Severity.CRITICAL.value
    # one critical finding drops the score from 100 to 60, which still fails
    # on the blocking-findings rule; anything at or below 60 is a fail
    assert report["score"] <= 60


def test_qa_flags_security_and_edge_case_vulnerabilities():
    ctx = _context()
    bad_code = """import os
import subprocess
import pickle

password = "hunter2supersecret"


def unsafe(data):
    result = eval(data)
    os.system("rm -rf /")
    subprocess.run(data, shell=True)
    pickle.loads(data)
    try:
        rate = 100 / 0
    except:
        pass


def mutable_default(items=[]):
    return items
"""
    code = {"project_name": "Insecure", "files": {"bad/src/unsafe.py": bad_code}}
    payloads = _run(QAAuditorAgent().run(ctx, {"code": code}))
    report = [p for p in payloads if p.kind is ArtifactKind.AUDIT_REPORT][0].content
    assert report["passed"] is False

    high_security = [
        f
        for f in report["findings"]
        if f["severity"] == Severity.HIGH.value and f["category"] == "security"
    ]
    assert any("eval" in f["message"] for f in high_security)
    assert any("shell" in f["message"].lower() for f in high_security)
    assert any("Hardcoded credential" in f["message"] for f in report["findings"])

    edge = [f for f in report["findings"] if f["category"] == "edge_cases"]
    assert any("zero" in f["message"] for f in edge)
    assert any("Bare except" in f["message"] for f in edge)

    mutable = [f for f in report["findings"] if f["category"] == "correctness"]
    assert any("Mutable default" in f["message"] for f in mutable)
