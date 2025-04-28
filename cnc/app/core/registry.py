from typing import Dict, Type

from app.services.attack import AttackWorker
from app.services.enrichment import RequestEnrichmentWorker

_WORKERS: Dict[str, Type[AttackWorker]] = {}
_ENRICHERS: Dict[str, Type[RequestEnrichmentWorker]] = {}


def register_enricher(cls: Type[RequestEnrichmentWorker]):
    _ENRICHERS[cls.name] = cls
    return cls


def register_attacker(cls: Type[AttackWorker]):
    _WORKERS[cls.name] = cls
    return cls


def sanity_check():
    """
    Ensure every enricher has ≥1 consumer
    This is a key safety check to prevent orphaned enrichment output.
    """
    produced = set(_ENRICHERS)
    consumed = {e for w in _WORKERS.values() for e in w.consumes}
    missing = produced - consumed
    if missing:
        raise RuntimeError(
            "No AttackWorker consumes output of: " + ", ".join(sorted(missing))
        )