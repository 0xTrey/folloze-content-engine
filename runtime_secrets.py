from __future__ import annotations

import os
import subprocess

DEFAULT_KEYCHAIN_SERVICES = {
    "BRAVE_API_KEY": ("brave-search-api",),
    "PERPLEXITY_API_KEY": ("perplexity-api",),
    "GEMINI_API_KEY": ("gemini-api", "gemini-api-key"),
    "SMTP_PASSWORD": ("smtp-password", "gmail-app-password", "gmail-smtp"),
    "VERCEL_TOKEN": ("vercel-token", "vercel-cli-token"),
}


def read_keychain(service: str) -> str | None:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    value = result.stdout.strip()
    return value or None


def get_secret(env_name: str, *services: str) -> str | None:
    value = os.getenv(env_name)
    if value:
        return value

    candidate_services = services or DEFAULT_KEYCHAIN_SERVICES.get(env_name, ())
    for service in candidate_services:
        value = read_keychain(service)
        if value:
            return value
    return None
