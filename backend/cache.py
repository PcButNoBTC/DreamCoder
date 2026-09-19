"""Simple in-memory LRU cache for identical suggestion requests."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import asdict
from typing import Any, Optional

from models.base import CodeContext, InferenceResult


class SuggestionCache:
    def __init__(self, max_size: int = 128, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._store: OrderedDict[str, tuple[float, InferenceResult]] = OrderedDict()

    def _key(self, model_name: str, context: CodeContext) -> str:
        payload = {
            "model": model_name,
            "code": context.code,
            "language": context.language,
            "selection": context.selection,
            "filename": context.filename,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, model_name: str, context: CodeContext) -> Optional[InferenceResult]:
        key = self._key(model_name, context)
        if key not in self._store:
            return None
        ts, result = self._store[key]
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        # Move to end (LRU)
        self._store.move_to_end(key)
        # Mark as cached
        cached = InferenceResult(
            suggestions=result.suggestions,
            latency_ms=result.latency_ms,
            model=result.model,
            cached=True,
            architecture_insights=result.architecture_insights,
            health=result.health,
        )
        return cached

    def put(self, model_name: str, context: CodeContext, result: InferenceResult) -> None:
        key = self._key(model_name, context)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.time(), result)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl,
        }
