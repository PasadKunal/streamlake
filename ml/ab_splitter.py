"""
Deterministic Champion / Challenger A/B splitter.

Assignment is based on an MD5 hash of user_id so:
  - The same user always gets the same model version
  - No database lookup required at inference time
  - Distribution is ~90% champion / ~10% challenger across any large user set

Champion  → latest registered model (production)
Challenger → previous model version (shadow testing)
"""
from __future__ import annotations

import hashlib


def assign(user_id: str, champion_pct: float = 0.90) -> str:
    """
    Assign a user to 'champion' or 'challenger' deterministically.

    Args:
        user_id:      The user's identifier string.
        champion_pct: Fraction of traffic routed to the champion model (0–1).

    Returns:
        "champion" or "challenger"
    """
    digest = hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF  # 0.0 – 1.0
    return "champion" if bucket < champion_pct else "challenger"


def split_stats(user_ids: list[str], champion_pct: float = 0.90) -> dict:
    """Return observed split stats for a list of user_ids (useful for testing)."""
    assignments = [assign(uid, champion_pct) for uid in user_ids]
    n = len(assignments)
    n_champion   = assignments.count("champion")
    n_challenger = n - n_champion
    return {
        "total":            n,
        "champion":         n_champion,
        "challenger":       n_challenger,
        "champion_pct":     round(n_champion / n, 4) if n else 0.0,
        "challenger_pct":   round(n_challenger / n, 4) if n else 0.0,
    }
