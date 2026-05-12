from __future__ import annotations

from .models import RetentionProfile

ONE_TIB_BYTES = 1024 * 1024 * 1024 * 1024


def resolve_retention_profile(
    profile_name: str,
    configured_capacity_bytes: int,
    installed_capacity_bytes: int,
    min_free_reserve_bytes: int = 0,
    lock_default_ttl_seconds: int = 0,
    max_supported_bytes: int = ONE_TIB_BYTES,
    overwrite_policy: str = "oldest-unlocked-first",
) -> RetentionProfile:
    max_supported = max(0, max_supported_bytes) or ONE_TIB_BYTES
    installed = max(0, installed_capacity_bytes)
    configured = max(0, configured_capacity_bytes)
    requested_capacity = configured if configured > 0 else installed
    effective_capacity = min(requested_capacity, installed, max_supported)
    reserve = min(max(0, min_free_reserve_bytes), effective_capacity)
    return RetentionProfile(
        name=profile_name,
        max_supported_bytes=max_supported,
        capacity_limit_bytes=effective_capacity,
        min_free_reserve_bytes=reserve,
        lock_default_ttl_seconds=max(0, lock_default_ttl_seconds),
        overwrite_policy=overwrite_policy or "oldest-unlocked-first",
    )
