"""Developer agent.

Converts the architecture blueprint (folder schema, ERD, API contract) into
complete, runnable Python files: Pydantic models, FastAPI routers, a main
application, generated pytest suites, and project meta files.

Every generated module is produced as a plain string, so the QA auditor can
parse and statically analyze it, and the test suite can run the generated
project end-to-end.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import (
    AgentRole,
    ArtifactKind,
    ArtifactPayload,
    CodeContent,
)
from .base import AgentContext, BaseAgent
from .specs import (
    ENTITIES,
    FEATURE_ENTITIES,
    FEATURE_RESOURCES,
    RESOURCE_TO_MODEL,
    SAMPLE_PAYLOADS,
    slugify,
)

_REQUIRED_DEPS = """fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
httpx>=0.27.0
pytest>=8.0.0
"""

_INIT = '"""Auto-generated package module."""\n'
_CONFTEST = '# Root conftest: puts the project root on sys.path so tests can import src.\n'

_TYPE_MAP = {"integer": "int", "string": "str", "boolean": "bool", "float": "float"}


class DeveloperAgent(BaseAgent):
    """Generates runnable source code from the PRD + architecture inputs."""

    role = AgentRole.DEVELOPER
    display_name = "Developer"

    async def _execute(self, context: AgentContext, inputs: Dict[str, Any]) -> List[ArtifactPayload]:
        prd = inputs["prd"]
        task = inputs.get("task")
        reporter, sprint = context.reporter, context.sprint

        project_name = prd.get("project_name", "Generated Project")

        if task:
            feature_keys = [task.get("feature_key")] if task.get("feature_key") else ["core_api"]
        else:
            feature_keys = [f["key"] for f in prd.get("features", [])] or ["core_api"]

        entities = self._select_entities(feature_keys)
        resources = self._select_resources(feature_keys)
        files = self._build_files(project_name, entities, resources)

        await reporter.log(
            sprint,
            self.role.value,
            "info",
            f"Generated {len(files)} files for feature(s): {', '.join(feature_keys)}",
        )

        content = CodeContent(
            project_name=project_name,
            files=files,
            feature_keys=feature_keys,
            summary=(
                f"Runnable scaffold for {project_name}: {len(files)} files, "
                f"{len(resources)} REST resource module(s), generated pytest suites."
            ),
        )

        return [
            ArtifactPayload(
                kind=ArtifactKind.SOURCE_CODE,
                title=f"Source Code — {project_name}",
                content=content.model_dump(mode="json"),
            )
        ]

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_entities(feature_keys: List[str]) -> List[Any]:
        names: List[str] = []
        for key in feature_keys:
            for entity_name in FEATURE_ENTITIES.get(key, []):
                if entity_name not in names:
                    names.append(entity_name)
        if "User" not in names:
            names.insert(0, "User")
        return [ENTITIES[name] for name in names]

    @staticmethod
    def _select_resources(feature_keys: List[str]) -> List[str]:
        resources: List[str] = []
        for key in feature_keys:
            for resource in FEATURE_RESOURCES.get(key, []):
                if resource not in resources:
                    resources.append(resource)
        return resources

    # ------------------------------------------------------------------
    # file generation
    # ------------------------------------------------------------------

    def _build_files(self, project_name: str, entities: List[Any], resources: List[str]) -> Dict[str, str]:
        root = slugify(project_name)
        files: Dict[str, str] = {
            f"{root}/requirements.txt": _REQUIRED_DEPS,
            f"{root}/conftest.py": _CONFTEST,
            f"{root}/src/__init__.py": _INIT,
            f"{root}/src/routes/__init__.py": _INIT,
            f"{root}/src/models.py": self._models_module(project_name, entities),
            f"{root}/src/main.py": self._main_module(project_name, resources),
            f"{root}/README.md": self._readme(project_name, resources),
        }
        for resource in resources:
            model_name = RESOURCE_TO_MODEL[resource]
            files[f"{root}/src/routes/{resource}.py"] = self._route_module(resource, model_name)
            sample = SAMPLE_PAYLOADS.get(resource, {})
            files[f"{root}/tests/test_{resource}.py"] = self._test_module(resource, model_name, sample)
        return files

    # ------------------------------------------------------------------
    # module templates
    # ------------------------------------------------------------------

    @staticmethod
    def _models_module(project_name: str, entities: List[Any]) -> str:
        lines = [
            f'"""Auto-generated Pydantic data models for {project_name}."""',
            "",
            "from datetime import datetime, timezone",
            "from typing import Optional",
            "",
            "from pydantic import BaseModel, Field",
        ]
        for entity in entities:
            lines.append("")
            lines.append(f"class {entity.name}(BaseModel):")
            lines.append(f'    """{entity.description}"""')
            lines.append("")
            for field in entity.fields:
                lines.append(DeveloperAgent._field_annotation(field))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _field_annotation(field: Any) -> str:
        if field.name == "id":
            return '    id: Optional[int] = Field(default=None, description="Primary key.")'
        description = field.description or f"{field.name.replace('_', ' ')}."
        py_type = _TYPE_MAP[field.type]
        if field.factory:
            return (
                f"    {field.name}: str = Field("
                f'default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="{description}")'
            )
        if field.required:
            return f'    {field.name}: {py_type} = Field(..., description="{description}")'
        return f'    {field.name}: {py_type} = Field(default={field.default!r}, description="{description}")'

    @staticmethod
    def _route_module(resource: str, model_name: str) -> str:
        id_param = f"{model_name.lower()}_id"
        return f'''"""REST endpoints for {resource}."""

from typing import List

from fastapi import APIRouter, HTTPException, status

from src.models import {model_name}

router = APIRouter(prefix="/{resource}", tags=["{resource}"])

_store: dict = {{}}
_next_id = 1


@router.get("", response_model=List[{model_name}])
def list_{resource}() -> List[{model_name}]:
    """Return every {resource} record."""
    return list(_store.values())


@router.post("", response_model={model_name}, status_code=status.HTTP_201_CREATED)
def create_{resource}(item: {model_name}) -> {model_name}:
    """Create a new {resource} record."""
    global _next_id
    item.id = _next_id
    _store[item.id] = item
    _next_id += 1
    return item


@router.get("/{{{id_param}}}", response_model={model_name})
def get_{resource}({id_param}: int) -> {model_name}:
    """Fetch a single {resource} record by identifier."""
    try:
        return _store[{id_param}]
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{resource} not found")


@router.delete("/{{{id_param}}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_{resource}({id_param}: int) -> None:
    """Delete a {resource} record by identifier."""
    try:
        del _store[{id_param}]
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{resource} not found")
'''

    @staticmethod
    def _main_module(project_name: str, resources: List[str]) -> str:
        imports = ", ".join(resources)
        lines = [
            f'"""Auto-generated FastAPI application for {project_name}."""',
            "",
            "from fastapi import FastAPI",
            "",
            f"from src.routes import {imports}",
            "",
            f'app = FastAPI(title="{project_name}", version="0.1.0", description="Application scaffolded by the multi-agent development system.")',
            "",
        ]
        for resource in resources:
            lines.append(f'app.include_router({resource}.router, prefix="/api/v1")')
        lines.extend(
            [
                "",
                "",
                '@app.get("/health")',
                "def health() -> dict:",
                '    """Liveness probe for the service."""',
                '    return {"status": "ok"}',
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _test_module(resource: str, model_name: str, sample_payload: Dict[str, object]) -> str:
        return f'''"""Automated tests for the {resource} API."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {{"status": "ok"}}


def test_create_and_fetch_{resource}() -> None:
    created = client.post("/api/v1/{resource}", json={sample_payload!r})
    assert created.status_code == 201
    record = created.json()
    assert isinstance(record["id"], int)
    fetched = client.get(f"/api/v1/{resource}/{{record['id']}}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == record["id"]


def test_delete_{resource}() -> None:
    created = client.post("/api/v1/{resource}", json={sample_payload!r})
    assert created.status_code == 201
    record = created.json()
    deleted = client.delete(f"/api/v1/{resource}/{{record['id']}}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/{resource}/{{record['id']}}")
    assert missing.status_code == 404
'''

    @staticmethod
    def _readme(project_name: str, resources: List[str]) -> str:
        lines = [
            f"# {project_name}",
            "",
            "Auto-generated by the Freebuff multi-agent development system.",
            "",
            "## Run",
            "",
            "    pip install -r requirements.txt",
            "    uvicorn src.main:app --reload",
            "",
            "## Endpoints",
            "",
            "- `GET /health`",
        ]
        for resource in resources:
            lines.append(f"- `GET/POST /api/v1/{resource}`")
            lines.append(f"- `GET/DELETE /api/v1/{resource}/{{id}}`")
        lines.append("")
        return "\n".join(lines)
