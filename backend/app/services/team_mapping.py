import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def load_team_mapping(path: str = "team_mapping.json") -> dict[str, dict]:
    mapping_path = Path(path)
    if not mapping_path.exists():
        return {}
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def leader_for_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    mapping = load_team_mapping()
    key = domain.lower().replace("/", "_").replace(" ", "_")
    team = mapping.get(key) or mapping.get(domain.lower())
    return team.get("leader") if team else None
