"""Shared domain specifications used across the agent team.

Keeping the feature vocabulary, entity definitions, and resource names in one
place guarantees that the PM, architect, developer, and QA agents all reason
about the same model of the product being built.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

_COMPILED = Tuple[re.Pattern, str]


@dataclass(frozen=True)
class FieldSpec:
    """Specification of a single entity field (column)."""

    name: str
    type: str = "string"  # integer | string | boolean | float
    required: bool = False
    default: object = None
    factory: bool = False  # auto-populated timestamp
    unique: bool = False
    description: str = ""


@dataclass(frozen=True)
class EntitySpec:
    """Specification of a single ERD entity (database table)."""

    name: str
    description: str
    fields: List[FieldSpec]


@dataclass(frozen=True)
class FeatureSpec:
    """Specification of a product feature the PM agent can detect."""

    key: str
    name: str
    description: str
    story: str = ""


# ---------------------------------------------------------------------------
# Feature detection
# ---------------------------------------------------------------------------

# Ordered (regex, feature_key) pairs.  The PM agent scans the user's idea
# against these; the first match per key wins and "core_api" is always added.
FEATURE_KEYWORDS: List[_COMPILED] = [
    (
        re.compile(
            r"auth|login|log ?in|register|sign ?up|sign ?in|session|user account|user management",
            re.IGNORECASE,
        ),
        "authentication",
    ),
    (
        re.compile(r"profile|avatar|bio|account settings", re.IGNORECASE),
        "user_profiles",
    ),
    (
        re.compile(r"pay|payment|checkout|billing|invoice|stripe|subscription", re.IGNORECASE),
        "payments",
    ),
    (
        re.compile(r"notif|email|alert|push message|digest", re.IGNORECASE),
        "notifications",
    ),
    (
        re.compile(r"report|dashboard|analytics|metric|chart|kpi", re.IGNORECASE),
        "reporting",
    ),
    (
        re.compile(r"api key|public api|third.party|webhook|integration", re.IGNORECASE),
        "public_api",
    ),
    (
        re.compile(r"task|todo|issue|kanban|project|sprint|board|ticket", re.IGNORECASE),
        "task_management",
    ),
]

FEATURES: Dict[str, FeatureSpec] = {
    "core_api": FeatureSpec(
        key="core_api",
        name="Core API Foundation",
        description="Project scaffolding, health endpoint, shared data models, and REST conventions.",
    ),
    "authentication": FeatureSpec(
        key="authentication",
        name="User Authentication",
        description="Registration, login, session issuance, and access control for end users.",
    ),
    "user_profiles": FeatureSpec(
        key="user_profiles",
        name="User Profiles",
        description="Profile records tied to user accounts with public/private visibility flags.",
    ),
    "payments": FeatureSpec(
        key="payments",
        name="Payments & Billing",
        description="Payment records, amount capture, currency handling, and billing status tracking.",
    ),
    "notifications": FeatureSpec(
        key="notifications",
        name="Notifications",
        description="Outbound notification records with channel, subject, body, and delivery state.",
    ),
    "reporting": FeatureSpec(
        key="reporting",
        name="Reporting & Analytics",
        description="Metric capture and report generation over the data the product collects.",
    ),
    "public_api": FeatureSpec(
        key="public_api",
        name="Public API & Keys",
        description="Managed API keys and integration endpoints for third-party consumers.",
    ),
    "task_management": FeatureSpec(
        key="task_management",
        name="Task Management",
        description="Issue and task records with priority, status, and assignment metadata.",
    ),
}


def match_features(idea: str) -> List[str]:
    """Return the ordered feature keys detected in a user idea.

    ``core_api`` is always present; every feature keyword that matches the
    idea is appended afterwards, deduplicated and in canonical order.
    """
    matched: List[str] = ["core_api"]
    for pattern, key in FEATURE_KEYWORDS:
        if key not in matched and pattern.search(idea):
            matched.append(key)
    return matched


# ---------------------------------------------------------------------------
# Entity definitions
# ---------------------------------------------------------------------------

ENTITIES: Dict[str, EntitySpec] = {
    "User": EntitySpec(
        name="User",
        description="An account that can interact with the system.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("email", "string", required=True, description="Email address", unique=True),
            FieldSpec("display_name", "string", default="anonymous", description="Display name"),
            FieldSpec("is_active", "boolean", default=True, description="Account active flag"),
            FieldSpec("created_at", "string", factory=True, description="Creation timestamp"),
        ],
    ),
    "Item": EntitySpec(
        name="Item",
        description="A generic record managed by the core API foundation.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("name", "string", required=True, description="Item name"),
            FieldSpec("description", "string", default="", description="Free-form description"),
            FieldSpec("created_at", "string", factory=True, description="Creation timestamp"),
        ],
    ),
    "Session": EntitySpec(
        name="Session",
        description="An authenticated session issued after login.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Owning user"),
            FieldSpec("token", "string", required=True, description="Session token"),
            FieldSpec("expires_at", "string", default="", description="Expiration timestamp"),
        ],
    ),
    "Profile": EntitySpec(
        name="Profile",
        description="Extended profile information for a user account.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Owning user"),
            FieldSpec("bio", "string", default="", description="Short biography"),
            FieldSpec("avatar_url", "string", default="", description="Avatar image URL"),
            FieldSpec("is_public", "boolean", default=True, description="Profile visibility flag"),
        ],
    ),
    "Payment": EntitySpec(
        name="Payment",
        description="A financial transaction captured by the billing system.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Paying user"),
            FieldSpec("amount", "float", required=True, description="Monetary amount"),
            FieldSpec("currency", "string", default="USD", description="ISO currency code"),
            FieldSpec("status", "string", default="pending", description="Billing status"),
        ],
    ),
    "Notification": EntitySpec(
        name="Notification",
        description="An outbound notification queued for delivery.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Recipient user"),
            FieldSpec("channel", "string", default="email", description="Delivery channel"),
            FieldSpec("subject", "string", default="", description="Notification subject"),
            FieldSpec("body", "string", default="", description="Notification body"),
            FieldSpec("sent", "boolean", default=False, description="Delivery state flag"),
        ],
    ),
    "Report": EntitySpec(
        name="Report",
        description="A generated analytics report over collected metrics.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Owning user"),
            FieldSpec("metric", "string", default="", description="Reported metric"),
            FieldSpec("value", "float", default=0.0, description="Metric value"),
            FieldSpec("generated_at", "string", factory=True, description="Generation timestamp"),
        ],
    ),
    "ApiKey": EntitySpec(
        name="ApiKey",
        description="A managed credential for third-party API consumers.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Owning user"),
            FieldSpec("name", "string", default="", description="Human-readable key name"),
            FieldSpec("key_hash", "string", default="", description="Hashed key material"),
            FieldSpec("enabled", "boolean", default=True, description="Key enabled flag"),
        ],
    ),
    "Task": EntitySpec(
        name="Task",
        description="An issue or task tracked by the task management feature.",
        fields=[
            FieldSpec("id", "integer", required=True, description="Primary key", unique=True),
            FieldSpec("user_id", "integer", required=True, description="Owning user"),
            FieldSpec("title", "string", required=True, description="Task title"),
            FieldSpec("description", "string", default="", description="Free-form description"),
            FieldSpec("status", "string", default="open", description="Workflow status"),
            FieldSpec("priority", "integer", default=1, description="Priority rank (1 = highest)"),
            FieldSpec("due_date", "string", default="", description="Due date"),
        ],
    ),
}

# Which entities belong to which feature.
FEATURE_ENTITIES: Dict[str, List[str]] = {
    "core_api": ["Item"],
    "authentication": ["User", "Session"],
    "user_profiles": ["Profile"],
    "payments": ["Payment"],
    "notifications": ["Notification"],
    "reporting": ["Report"],
    "public_api": ["ApiKey"],
    "task_management": ["Task"],
}

# Which REST resources belong to which feature.
FEATURE_RESOURCES: Dict[str, List[str]] = {
    "core_api": ["items"],
    "authentication": ["users", "sessions"],
    "user_profiles": ["profiles"],
    "payments": ["payments"],
    "notifications": ["notifications"],
    "reporting": ["reports"],
    "public_api": ["api_keys"],
    "task_management": ["tasks"],
}


def camel_to_snake(name: str) -> str:
    """Convert a CamelCase entity name to snake_case (``ApiKey`` -> ``api_key``)."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def pluralize(name: str) -> str:
    """Naive pluralizer good enough for our controlled entity vocabulary."""
    return camel_to_snake(name) + "s"


def singular(resource: str) -> str:
    """Strip a trailing 's' to recover a singular resource name."""
    if resource.endswith("ies"):
        return resource[:-3] + "y"
    if resource.endswith("s"):
        return resource[:-1]
    return resource


def slugify(name: str) -> str:
    """Turn an arbitrary project name into a filesystem-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


# Resource name -> entity model name (e.g. "users" -> "User").
RESOURCE_TO_MODEL: Dict[str, str] = {}
for _feature_entities in FEATURE_ENTITIES.values():
    for _entity_name in _feature_entities:
        RESOURCE_TO_MODEL[pluralize(_entity_name)] = _entity_name

# Sample payloads (only required fields) used by the architect's API contract
# and the developer agent's generated test suites.
SAMPLE_PAYLOADS: Dict[str, Dict[str, object]] = {
    "users": {"email": "ada@example.com"},
    "items": {"name": "Example item"},
    "sessions": {"user_id": 1, "token": "demo-token"},
    "profiles": {"user_id": 1},
    "payments": {"user_id": 1, "amount": 19.99},
    "notifications": {"user_id": 1, "subject": "Hello"},
    "reports": {"user_id": 1, "metric": "signups"},
    "api_keys": {"user_id": 1, "name": "ci-key"},
    "tasks": {"user_id": 1, "title": "Write tests"},
}
