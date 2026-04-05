from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUTHORS_PATH = ROOT / "data" / "authors.json"


@dataclass(frozen=True, slots=True)
class AuthorProfile:
    author_id: str
    name: str
    slug: str
    role_slug: str
    role: str
    team: str
    short_bio: str
    long_bio: str
    linkedin_url: str
    x_url: str
    image_path: str
    known_bad_roles: tuple[str, ...] = ()


def load_author_registry(
    path: Path | None = None,
) -> tuple[str, dict[str, AuthorProfile]]:
    registry_path = path or AUTHORS_PATH
    payload = json.loads(registry_path.read_text())
    default_author_id = payload["default_author_id"]
    authors: dict[str, AuthorProfile] = {}
    slugs: set[str] = set()

    for record in payload.get("authors", []):
        author = AuthorProfile(
            author_id=record["author_id"],
            name=record["name"],
            slug=record["slug"],
            role_slug=record["role_slug"],
            role=record["role"],
            team=record["team"],
            short_bio=record["short_bio"],
            long_bio=record["long_bio"],
            linkedin_url=record["linkedin_url"],
            x_url=record["x_url"],
            image_path=record["image_path"],
            known_bad_roles=tuple(record.get("known_bad_roles", [])),
        )
        if author.author_id in authors:
            raise ValueError(f"duplicate author_id in registry: {author.author_id}")
        if author.slug in slugs:
            raise ValueError(f"duplicate author slug in registry: {author.slug}")
        authors[author.author_id] = author
        slugs.add(author.slug)

    if default_author_id not in authors:
        raise ValueError(f"default author_id not found in registry: {default_author_id}")
    return default_author_id, authors


def primary_author_profile(path: Path | None = None) -> AuthorProfile:
    default_author_id, authors = load_author_registry(path)
    return authors[default_author_id]
