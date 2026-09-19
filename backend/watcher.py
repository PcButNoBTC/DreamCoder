"""File watcher – keeps the project index fresh when files change on disk.

Uses the `watchdog` library when available; otherwise falls back to a simple
polling loop so the feature always works.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Callable, Optional, Set

# Optional watchdog
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


SUPPORTED_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".json", ".toml", ".yaml", ".yml"}


def _lang_for(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
        ".json": "json",
    }.get(ext, "text")


class IndexWatcher:
    """Watch a root directory and re-index changed source files."""

    def __init__(self, root: str, on_change: Callable[[str, str, str], None]):
        self.root = Path(root).resolve()
        self.on_change = on_change
        self._observer = None
        self._polling = False
        self._stop = False
        self._seen: dict[str, float] = {}
        self._pending: dict[str, tuple[str,str]] = {}
        self._lock = threading.Lock()
        self._debounce_seconds = float(os.getenv("DREAMCODER_WATCH_DEBOUNCE", "0.35"))

    def start(self) -> dict:
        if not self.root.exists():
            return {"status": "missing", "root": str(self.root)}

        # Initial full scan
        self._scan_all()

        if HAS_WATCHDOG:
            handler = _Handler(self)
            self._observer = Observer()
            self._observer.schedule(handler, str(self.root), recursive=True)
            self._observer.start()
            return {"status": "watching", "backend": "watchdog", "root": str(self.root)}
        else:
            self._polling = True
            self._stop = False
            # Caller should schedule _poll_loop on the event loop
            return {"status": "watching", "backend": "polling", "root": str(self.root)}

    def stop(self) -> None:
        self._stop = True
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def _scan_all(self) -> int:
        count = 0
        for path in self.root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
                if any(part.startswith(".") or part in ("node_modules", "__pycache__", "venv", ".git") for part in path.parts):
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    rel = str(path.relative_to(self.root)).replace("\\", "/")
                    self._emit(rel, content, _lang_for(rel))
                    self._seen[str(path)] = path.stat().st_mtime
                    count += 1
                except Exception:
                    pass
        return count

    async def poll_loop(self, interval: float = 2.0) -> None:
        """Async polling fallback when watchdog is not installed."""
        while not self._stop:
            await asyncio.sleep(interval)
            if not self._polling:
                continue
            for path in self.root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                if any(part.startswith(".") or part in ("node_modules", "__pycache__", "venv", ".git") for part in path.parts):
                    continue
                try:
                    mtime = path.stat().st_mtime
                    key = str(path)
                    if self._seen.get(key) == mtime:
                        continue
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    rel = str(path.relative_to(self.root)).replace("\\", "/")
                    self.on_change(rel, content, _lang_for(rel))
                    self._seen[key] = mtime
                except Exception:
                    pass


if HAS_WATCHDOG:

    class _Handler(FileSystemEventHandler):
        def __init__(self, watcher: IndexWatcher):
            self.w = watcher

        def on_modified(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() not in SUPPORTED_EXTS:
                return
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                rel = str(path.relative_to(self.w.root)).replace("\\", "/")
                self.w._emit(rel, content, _lang_for(rel))
            except Exception:
                pass

        def on_created(self, event):
            self.on_modified(event)

        def on_deleted(self, event):
            if event.is_directory:
                return
            try:
                path = Path(event.src_path)
                rel = str(path.relative_to(self.w.root)).replace("\\", "/")
                # Caller handles delete via a special empty content or separate hook
                self.w._emit(rel, "", "deleted")
            except Exception:
                pass
else:
    _Handler = None  # type: ignore
