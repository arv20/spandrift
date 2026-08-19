"""QA Auditor agent.

Audits generated code for syntax errors, missing edge cases, and security
vulnerabilities using pure static analysis (no execution): every ``.py``
file is parsed with ``ast``, then scanned for dangerous constructs,
hardcoded credentials, unguarded operations, and common correctness traps.
The result is a scored, severity-tagged audit report.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List

from ..models import (
    AgentRole,
    ArtifactKind,
    ArtifactPayload,
    AuditReportContent,
    Finding,
    Severity,
)
from .base import AgentContext, BaseAgent

_SEVERITY_POINTS = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 20,
    Severity.MEDIUM: 10,
    Severity.LOW: 5,
}

_BLOCKING_SEVERITIES = (Severity.CRITICAL, Severity.HIGH)

# Roughly matches hardcoded credentials like `password = "hunter2"` or
# `API_KEY = "abc123..."` inside source files.
_SECRET_RE = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)"
    r"\s*[:=]\s*['\"][^'\"]{6,}"
)


class QAAuditorAgent(BaseAgent):
    """Static code auditor producing a scored, severity-tagged report."""

    role = AgentRole.QA_AUDITOR
    display_name = "QA Auditor"

    async def _execute(self, context: AgentContext, inputs: Dict[str, Any]) -> List[ArtifactPayload]:
        code = inputs["code"]
        files = code.get("files", {})
        reporter, sprint = context.reporter, context.sprint

        findings: List[Finding] = []
        checks_run: List[str] = []

        await reporter.log(sprint, self.role.value, "info", f"Auditing {len(files)} generated file(s)")

        self._audit_syntax(files, findings, checks_run)
        self._audit_security(files, findings, checks_run)
        self._audit_edge_cases(files, findings, checks_run)
        self._audit_secrets(files, findings, checks_run)
        self._audit_style(files, findings, checks_run)

        score = max(0, 100 - sum(_SEVERITY_POINTS[f.severity] for f in findings))
        blocking = [f for f in findings if f.severity in _BLOCKING_SEVERITIES]
        passed = score >= 60 and not blocking

        if blocking:
            await reporter.log(
                sprint,
                self.role.value,
                "warning",
                f"Audit failed: {len(blocking)} blocking finding(s), score {score}",
            )
        else:
            await reporter.log(sprint, self.role.value, "info", f"Audit passed with score {score}")

        report = AuditReportContent(
            summary=(
                f"Audited {len(files)} file(s): {len(findings)} finding(s), "
                f"{len([f for f in findings if f.severity in _BLOCKING_SEVERITIES])} blocking. "
                f"{'PASS' if passed else 'FAIL'}."
            ),
            score=score,
            passed=passed,
            files_audited=sorted(files),
            findings=findings,
            checks_run=checks_run,
        )

        return [
            ArtifactPayload(
                kind=ArtifactKind.AUDIT_REPORT,
                title=f"QA Audit Report — {code.get('project_name', 'project')}",
                content=report.model_dump(mode="json"),
            )
        ]

    # ------------------------------------------------------------------
    # checks
    # ------------------------------------------------------------------

    @staticmethod
    def _py_files(files: Dict[str, str]) -> List[str]:
        return [path for path in files if path.endswith(".py")]

    @staticmethod
    def _audit_syntax(files: Dict[str, str], findings: List[Finding], checks_run: List[str]) -> None:
        checked = False
        for path in QAAuditorAgent._py_files(files):
            checked = True
            try:
                ast.parse(files[path])
            except SyntaxError as exc:
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category="syntax",
                        file=path,
                        line=exc.lineno,
                        message=f"Syntax error: {exc.msg}",
                        recommendation="Fix the reported syntax error before running the code.",
                    )
                )
        if checked:
            checks_run.append("syntax: ast.parse every .py file")

    @staticmethod
    def _audit_security(files: Dict[str, str], findings: List[Finding], checks_run: List[str]) -> None:
        for path in QAAuditorAgent._py_files(files):
            try:
                tree = ast.parse(files[path])
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                        findings.append(
                            Finding(
                                severity=Severity.HIGH,
                                category="security",
                                file=path,
                                line=node.lineno,
                                message=f"Use of {func.id}() permits arbitrary code execution.",
                                recommendation="Remove eval/exec and use a safe parser such as json.loads.",
                            )
                        )
                    elif isinstance(func, ast.Attribute):
                        if (
                            func.attr == "system"
                            and isinstance(func.value, ast.Name)
                            and func.value.id == "os"
                        ):
                            findings.append(
                                Finding(
                                    severity=Severity.HIGH,
                                    category="security",
                                    file=path,
                                    line=node.lineno,
                                    message="os.system() runs commands through the shell.",
                                    recommendation="Use subprocess with an argument list and shell=False.",
                                )
                            )
                        elif (
                            func.attr == "loads"
                            and isinstance(func.value, ast.Name)
                            and func.value.id == "pickle"
                        ):
                            findings.append(
                                Finding(
                                    severity=Severity.HIGH,
                                    category="security",
                                    file=path,
                                    line=node.lineno,
                                    message="pickle.loads() can execute arbitrary objects.",
                                    recommendation="Prefer a safe serialization format such as JSON.",
                                )
                            )
                        elif (
                            func.attr in ("Popen", "run", "call", "check_output")
                            and isinstance(func.value, ast.Attribute)
                            and isinstance(func.value.value, ast.Name)
                            and func.value.value.id == "subprocess"
                        ):
                            shell = any(
                                kw.arg == "shell"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                                for kw in node.keywords
                            )
                            if shell:
                                findings.append(
                                    Finding(
                                        severity=Severity.HIGH,
                                        category="security",
                                        file=path,
                                        line=node.lineno,
                                        message="subprocess invoked with shell=True.",
                                        recommendation="Pass an argument list and shell=False.",
                                    )
                                )
                        elif func.attr == "execute" and any(
                            isinstance(arg, ast.JoinedStr) for arg in node.args
                        ):
                            findings.append(
                                Finding(
                                    severity=Severity.MEDIUM,
                                    category="security",
                                    file=path,
                                    line=node.lineno,
                                    message="SQL query assembled with f-string interpolation.",
                                    recommendation="Use parameterized queries instead of string interpolation.",
                                )
                            )
                    if (
                        isinstance(func, ast.Name)
                        and func.id == "input"
                        and "test" not in path
                    ):
                        findings.append(
                            Finding(
                                severity=Severity.MEDIUM,
                                category="security",
                                file=path,
                                line=node.lineno,
                                message="input() reads unvalidated user data at runtime.",
                                recommendation="Validate and sanitize all user-supplied input.",
                            )
                        )
                elif isinstance(node, ast.FunctionDef) and node.args.defaults:
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            findings.append(
                                Finding(
                                    severity=Severity.MEDIUM,
                                    category="correctness",
                                    file=path,
                                    line=node.lineno,
                                    message=f"Mutable default argument in {node.name}() is shared across calls.",
                                    recommendation="Use default=None and create a fresh container inside the function.",
                                )
                            )
        checks_run.append("security: eval/exec, os.system, shell=True, pickle, input, SQL interpolation, mutable defaults")

    @staticmethod
    def _audit_edge_cases(files: Dict[str, str], findings: List[Finding], checks_run: List[str]) -> None:
        for path in QAAuditorAgent._py_files(files):
            try:
                tree = ast.parse(files[path])
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.BinOp)
                    and isinstance(node.op, (ast.Div, ast.FloorDiv))
                    and isinstance(node.right, ast.Constant)
                    and isinstance(node.right.value, (int, float))
                    and node.right.value == 0
                ):
                    findings.append(
                        Finding(
                            severity=Severity.HIGH,
                            category="edge_cases",
                            file=path,
                            line=node.lineno,
                            message="Division by a literal zero raises ZeroDivisionError at runtime.",
                            recommendation="Guard the denominator before dividing.",
                        )
                    )
                elif isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings.append(
                        Finding(
                            severity=Severity.MEDIUM,
                            category="edge_cases",
                            file=path,
                            line=node.lineno,
                            message="Bare except: catches every exception, including KeyboardInterrupt.",
                            recommendation="Catch specific exception types.",
                        )
                    )
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        findings.append(
                            Finding(
                                severity=Severity.LOW,
                                category="edge_cases",
                                file=path,
                                line=node.lineno,
                                message="Exception handler silently swallows errors (pass only).",
                                recommendation="Log or re-raise the exception.",
                            )
                        )
        checks_run.append("edge cases: zero division, bare except, silent exception handling")

    @staticmethod
    def _audit_secrets(files: Dict[str, str], findings: List[Finding], checks_run: List[str]) -> None:
        checked = False
        for path, content in files.items():
            if not (path.endswith(".py") or path.endswith(".env")):
                continue
            checked = True
            for lineno, line in enumerate(content.splitlines(), start=1):
                if _SECRET_RE.search(line):
                    findings.append(
                        Finding(
                            severity=Severity.HIGH,
                            category="security",
                            file=path,
                            line=lineno,
                            message="Hardcoded credential detected in source.",
                            recommendation="Load secrets from environment variables or a secrets manager.",
                        )
                    )
        if checked:
            checks_run.append("secrets: scan for hardcoded credentials")

    @staticmethod
    def _audit_style(files: Dict[str, str], findings: List[Finding], checks_run: List[str]) -> None:
        checked = False
        for path in QAAuditorAgent._py_files(files):
            checked = True
            if len(files[path].splitlines()) > 500:
                findings.append(
                    Finding(
                        severity=Severity.LOW,
                        category="style",
                        file=path,
                        line=None,
                        message="File exceeds 500 lines; consider splitting it into smaller modules.",
                        recommendation="Refactor oversized modules for maintainability.",
                    )
                )
        if checked:
            checks_run.append("style: module size")
