from pathlib import Path
from fastapi import HTTPException

SENSITIVE_TOKENS = (
    "drug_discovery_priority_score", "priority_class", "database_candidate_tier",
    "internal", "triage", "candidate_tier", "candidate_model", "ranked_candidate",
)

def is_sensitive_name(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in SENSITIVE_TOKENS)

def reject_unsafe_identifier(value: str) -> None:
    if not value or ".." in value or "/" in value or "\\" in value or value.startswith("~"):
        raise HTTPException(status_code=400, detail="Unsafe identifier")

def safe_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="File is outside the approved public data root") from exc
    return resolved
