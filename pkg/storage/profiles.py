from __future__ import annotations

from .models import RetentionProfile

ONE_TIB_BYTES = 1024 * 1024 * 1024 * 1024


def resolve_retention_profile(
    profile_name: str,
    configured_capacity_bytes: int,
    installed_capacity_bytes: int,
    min_free_reserve_bytes: int = 0,
    lock_default_ttl_seconds: int = 0,
) -> RetentionProfile:
    max_supported = ONE_TIB_BYTES
    installed = max(0, installed_capacity_bytes)
    configured = max(0, configured_capacity_bytes)
    effective_capacity = min(configured, installed, max_supported)
    return RetentionProfile(
        name=profile_name,
        max_supported_bytes=max_supported,
        capacity_limit_bytes=effective_capacity,
        min_free_reserve_bytes=max(0, min_free_reserve_bytes),
        lock_default_ttl_seconds=max(0, lock_default_ttl_seconds),
        overwrite_policy="oldest-unlocked-first",
    )
