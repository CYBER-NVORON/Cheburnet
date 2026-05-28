from __future__ import annotations

import json
from pathlib import Path

from cheburnet.app.core.paths import app_data_dir
from cheburnet.app.models.profile import Profile


class ProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "profiles.json"
        self.profiles: list[Profile] = []
        self.load()

    def load(self) -> list[Profile]:
        if not self.path.exists():
            self.save()
            return self.profiles
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        items = data.get("profiles", data) if isinstance(data, dict) else data
        self.profiles = [Profile.from_dict(item) for item in items if isinstance(item, dict)]
        return self.profiles

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"profiles": [profile.to_dict() for profile in self.profiles]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def all(self) -> list[Profile]:
        return list(self.profiles)

    def get(self, profile_id: str | None) -> Profile | None:
        if not profile_id:
            return None
        return next((profile for profile in self.profiles if profile.id == profile_id), None)

    def upsert(self, profile: Profile) -> Profile:
        self.profiles = [item for item in self.profiles if item.id != profile.id]
        self.profiles.append(profile)
        self.save()
        return profile

    def upsert_many(self, profiles: list[Profile]) -> None:
        existing = {profile.id: profile for profile in self.profiles}
        for profile in profiles:
            existing[profile.id] = profile
        self.profiles = list(existing.values())
        self.save()

    def delete(self, profile_id: str) -> bool:
        before = len(self.profiles)
        self.profiles = [profile for profile in self.profiles if profile.id != profile_id]
        changed = len(self.profiles) != before
        if changed:
            self.save()
        return changed

    def select(self, profile_id: str) -> Profile | None:
        return self.get(profile_id)
