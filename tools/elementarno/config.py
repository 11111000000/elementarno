"""Configuration: profiles, packs, modes, providers."""

import json
from pathlib import Path

DEFAULT_CONFIG = Path("config/profiles.json")

BASE_PROFILE = {
    "id": "default",
    "title": "Базовая",
    "packs": ["core", "absence"],
    "mode": "detective",
    "persona": "plain",
    "min_findings": 1,
    "allow_interpretation": False,
    "capabilities": [],
}


def load_config(path=None):
    path = Path(path) if path else DEFAULT_CONFIG
    if not path.exists():
        return {"providers": {}, "mcp_servers": {}, "profiles": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def get_profile(config, profile_id=None):
    profiles = config.get("profiles", {})
    if profile_id is None:
        profile_id = config.get("default_profile", "default")
    profile = profiles.get(profile_id)
    if profile is None:
        if profile_id != "default":
            raise KeyError(f"unknown profile: {profile_id}")
        profile = dict(BASE_PROFILE)
    merged = dict(BASE_PROFILE)
    merged.update(profile)
    merged["id"] = profile_id
    return merged


def list_profiles(config):
    return sorted((config.get("profiles") or {}).keys())
