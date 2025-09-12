from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from cnc.database.models import PentestEngagement


def _deep_merge(base: Any, delta: Any) -> Any:
    """Deep-merge delta into base according to simplified rules.
    - Objects: recursive merge
    - Arrays of scalars: union by value
    - Arrays of objects: union by identity key if present (id, url, (url, method)), else dedupe by value
    - Scalars: overwrite
    """
    if isinstance(base, dict) and isinstance(delta, dict):
        result: Dict[str, Any] = dict(base)
        for k, v in delta.items():
            if k in result:
                result[k] = _deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    if isinstance(base, list) and isinstance(delta, list):
        # Detect scalars vs objects
        if all(not isinstance(x, dict) for x in base + delta):
            # union while preserving order
            seen = set()
            merged: List[Any] = []
            for item in base + delta:
                if item not in seen:
                    seen.add(item)
                    merged.append(item)
            return merged

        # Treat as list of objects
        def make_key(obj: Any) -> Any:
            if not isinstance(obj, dict):
                return ("__scalar__", obj)
            if "id" in obj:
                return ("id", obj["id"])
            if "url" in obj and "method" in obj:
                return ("urlmethod", obj["url"], obj["method"])
            if "url" in obj:
                return ("url", obj["url"])  # best-effort
            # fallback to tuple of sorted items for stability
            return ("dict", tuple(sorted(obj.items())))

        merged_map: Dict[Any, Any] = {}
        # seed with base
        for item in base:
            merged_map[make_key(item)] = item
        # apply delta
        for item in delta:
            key = make_key(item)
            if key in merged_map and isinstance(merged_map[key], dict) and isinstance(item, dict):
                merged_map[key] = _deep_merge(merged_map[key], item)
            else:
                merged_map[key] = item
        return list(merged_map.values())

    # Default: overwrite
    return delta


async def merge_page_data(db: AsyncSession, engagement_id, delta: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge the given delta into the engagement's page_data and persist.
    Returns the updated page_data list.
    """
    result = await db.execute(select(PentestEngagement).where(PentestEngagement.id == engagement_id).with_for_update())
    engagement: Optional[PentestEngagement] = result.scalars().first()
    if not engagement:
        raise ValueError("Engagement not found")

    current = engagement.page_data or []
    updated = _deep_merge(current, delta)

    engagement.page_data = updated  # type: ignore
    db.add(engagement)
    await db.commit()
    await db.refresh(engagement)
    return engagement.page_data or []


