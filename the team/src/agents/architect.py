"""Architect agent.

Translates a validated PRD into the concrete engineering blueprint: the
project folder schema, the entity-relationship model, and the REST API
contract the developer agent will implement.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import (
    APIContractContent,
    AgentRole,
    ArtifactKind,
    ArtifactPayload,
    Endpoint,
    Entity,
    EntityRelation,
    ERDContent,
    ERDField,
    FolderEntry,
    FolderSchemaContent,
)
from .base import AgentContext, BaseAgent
from .specs import (
    ENTITIES,
    FEATURE_ENTITIES,
    FEATURE_RESOURCES,
    SAMPLE_PAYLOADS,
    pluralize,
    singular,
    slugify,
)


class ArchitectAgent(BaseAgent):
    """Designs the folder schema, ERD, and API contract from a PRD."""

    role = AgentRole.ARCHITECT
    display_name = "Architect"

    async def _execute(self, context: AgentContext, inputs: Dict[str, Any]) -> List[ArtifactPayload]:
        prd = inputs["prd"]
        reporter, sprint = context.reporter, context.sprint

        feature_keys = [f["key"] for f in prd.get("features", [])] or ["core_api"]
        project_name = prd.get("project_name", "Generated Product")
        root = slugify(project_name)
        resources = self._select_resources(feature_keys)

        await reporter.log(sprint, self.role.value, "info", f"Designing architecture for {len(resources)} REST resources")

        folder_schema = FolderSchemaContent(
            root=root,
            tree=self._build_tree(root, resources),
            structure=self._build_structure(root, resources),
        )

        erd = ERDContent(
            overview=f"Entity-relationship model for {project_name} covering {len(feature_keys)} feature areas.",
            assumptions=[
                "Every entity stores its primary key in an auto-incremented integer id.",
                "All feature entities belong to exactly one user (many-to-one).",
                "Persistence is in-memory in the generated reference implementation.",
            ],
            entities=self._build_entities(feature_keys),
        )

        api = APIContractContent(
            base_path="/api/v1",
            auth="Bearer token (mock in the generated scaffold)",
            endpoints=self._build_endpoints(resources),
        )

        await reporter.log(sprint, self.role.value, "info", "Architecture complete: schema, ERD, and API contract ready")

        return [
            ArtifactPayload(
                kind=ArtifactKind.FOLDER_SCHEMA,
                title="Project Folder Schema",
                content=folder_schema.model_dump(mode="json"),
            ),
            ArtifactPayload(
                kind=ArtifactKind.ERD,
                title=f"Entity-Relationship Model — {project_name}",
                content=erd.model_dump(mode="json"),
            ),
            ArtifactPayload(
                kind=ArtifactKind.API_CONTRACT,
                title=f"REST API Contract — {project_name}",
                content=api.model_dump(mode="json"),
            ),
        ]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_resources(feature_keys: List[str]) -> List[str]:
        resources: List[str] = []
        for key in feature_keys:
            for resource in FEATURE_RESOURCES.get(key, []):
                if resource not in resources:
                    resources.append(resource)
        return resources

    @staticmethod
    def _build_entities(feature_keys: List[str]) -> List[Entity]:
        entities: List[Entity] = []
        seen: set = set()

        def add(entity_name: str) -> None:
            if entity_name in seen:
                return
            seen.add(entity_name)
            spec = ENTITIES[entity_name]
            fields = []
            for field in spec.fields:
                constraints: List[str] = []
                if field.name == "id":
                    constraints = ["primary_key", "auto_increment"]
                else:
                    if field.unique:
                        constraints.append("unique")
                    constraints.append("not_null" if field.required else "nullable")
                    if field.factory:
                        constraints.append("auto_timestamp")
                fields.append(ERDField(name=field.name, type=field.type, constraints=constraints))
            relations = []
            if entity_name != "User":
                relations.append(EntityRelation(type="many-to-one", target="User"))
            entities.append(
                Entity(
                    name=entity_name,
                    table=pluralize(entity_name),
                    description=spec.description,
                    fields=fields,
                    relations=relations,
                )
            )

        add("User")
        for key in feature_keys:
            for entity_name in FEATURE_ENTITIES.get(key, []):
                add(entity_name)
        return entities

    @staticmethod
    def _build_tree(root: str, resources: List[str]) -> str:
        lines = [
            f"{root}/",
            "├── src/",
            "│   ├── __init__.py",
            "│   ├── models.py",
            "│   ├── main.py",
            "│   └── routes/",
            "│       ├── __init__.py",
        ]
        for index, resource in enumerate(resources):
            marker = "└──" if index == len(resources) - 1 else "├──"
            lines.append(f"│       {marker} {resource}.py")
        lines.append("├── tests/")
        for index, resource in enumerate(resources):
            marker = "└──" if index == len(resources) - 1 else "├──"
            lines.append(f"│   {marker} test_{resource}.py")
        lines.append("├── conftest.py")
        lines.append("├── requirements.txt")
        lines.append("└── README.md")
        return "\n".join(lines)

    @staticmethod
    def _build_structure(root: str, resources: List[str]) -> List[FolderEntry]:
        structure: List[FolderEntry] = [
            FolderEntry(path=f"{root}/src", type="dir", purpose="Application source package"),
            FolderEntry(path=f"{root}/src/models.py", type="file", purpose="Pydantic data models derived from the ERD"),
            FolderEntry(path=f"{root}/src/main.py", type="file", purpose="FastAPI application entrypoint"),
            FolderEntry(path=f"{root}/src/routes", type="dir", purpose="REST route modules, one per resource"),
        ]
        for resource in resources:
            structure.append(
                FolderEntry(path=f"{root}/src/routes/{resource}.py", type="file", purpose=f"CRUD endpoints for {resource}")
            )
        structure.append(FolderEntry(path=f"{root}/tests", type="dir", purpose="Automated pytest suite"))
        for resource in resources:
            structure.append(
                FolderEntry(path=f"{root}/tests/test_{resource}.py", type="file", purpose=f"API tests for {resource}")
            )
        structure.append(FolderEntry(path=f"{root}/requirements.txt", type="file", purpose="Python dependencies"))
        structure.append(FolderEntry(path=f"{root}/README.md", type="file", purpose="Project documentation"))
        return structure

    @staticmethod
    def _build_endpoints(resources: List[str]) -> List[Endpoint]:
        endpoints: List[Endpoint] = []
        for resource in resources:
            name = singular(resource)
            endpoints.extend(
                [
                    Endpoint(method="GET", path=f"/api/v1/{resource}", summary=f"List all {resource}", responses=["200 OK"]),
                    Endpoint(
                        method="POST",
                        path=f"/api/v1/{resource}",
                        summary=f"Create a {name}",
                        request_body=SAMPLE_PAYLOADS.get(resource, {}),
                        responses=["201 Created", "422 Validation Error"],
                    ),
                    Endpoint(method="GET", path=f"/api/v1/{resource}/{{id}}", summary=f"Fetch a single {name}", responses=["200 OK", "404 Not Found"]),
                    Endpoint(method="DELETE", path=f"/api/v1/{resource}/{{id}}", summary=f"Delete a {name}", responses=["204 No Content", "404 Not Found"]),
                ]
            )
        endpoints.append(Endpoint(method="GET", path="/health", summary="Liveness probe", responses=["200 OK"]))
        return endpoints
