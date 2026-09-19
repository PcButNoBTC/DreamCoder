"""Live GitHub synchronization for DreamCoder's IDE.

The browser never receives the GitHub token. The backend uses a token from the
environment and mirrors successful IDE saves to the configured repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class GitHubSync:
    repo: str
    branch: str
    token: str
    enabled: bool = True
    timeout: float = 20.0

    @classmethod
    def from_env(cls) -> "GitHubSync":
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
        repo = os.getenv("DREAMCODER_GITHUB_REPO", "").strip()
        branch = os.getenv("DREAMCODER_GITHUB_BRANCH", "main").strip() or "main"
        enabled = os.getenv("DREAMCODER_GITHUB_AUTOSYNC", "true").lower() not in {"0", "false", "no", "off"}
        return cls(repo=repo, branch=branch, token=token, enabled=enabled)

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.repo and self.token and "/" in self.repo)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "repo": self.repo or None,
            "branch": self.branch,
            "auth": bool(self.token),
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def sync_file(self, path: str, content: str, message: str | None = None) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "skipped": True, "reason": "GitHub autosync is not configured"}

        path = path.replace("\\", "/").lstrip("/")
        if not path or path.startswith(".git/") or ".." in path.split("/"):
            return {"ok": False, "skipped": True, "reason": "Invalid repository path"}

        url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        commit_message = message or f"DreamCoder live sync: {path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            get = await client.get(url, params={"ref": self.branch}, headers=self._headers())
            sha = None
            if get.status_code == 200:
                sha = get.json().get("sha")
            elif get.status_code != 404:
                return {"ok": False, "status_code": get.status_code, "error": get.text[:1000]}

            import base64
            body: dict[str, Any] = {
                "message": commit_message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            }
            if sha:
                body["sha"] = sha

            put = await client.put(url, headers=self._headers(), json=body)
            if put.status_code not in (200, 201):
                return {"ok": False, "status_code": put.status_code, "error": put.text[:1200]}

            data = put.json()
            return {
                "ok": True,
                "path": path,
                "branch": self.branch,
                "commit_sha": (data.get("commit") or {}).get("sha"),
                "commit_url": (data.get("commit") or {}).get("html_url"),
                "created": not bool(sha),
            }


    async def delete_file(self, path: str, message: str | None = None) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "skipped": True, "reason": "GitHub autosync is not configured"}
        path = path.replace("\\", "/").lstrip("/")
        if not path or path.startswith(".git/") or ".." in path.split("/"):
            return {"ok": False, "skipped": True, "reason": "Invalid repository path"}
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            get = await client.get(url, params={"ref": self.branch}, headers=self._headers())
            if get.status_code == 404:
                return {"ok": True, "skipped": True, "reason": "Already absent"}
            if get.status_code != 200:
                return {"ok": False, "status_code": get.status_code, "error": get.text[:1000]}
            sha = get.json().get("sha")
            result = await client.request("DELETE", url, headers=self._headers(), json={
                "message": message or f"DreamCoder live delete: {path}",
                "sha": sha,
                "branch": self.branch,
            })
            if result.status_code != 200:
                return {"ok": False, "status_code": result.status_code, "error": result.text[:1200]}
            data = result.json()
            return {"ok": True, "path": path, "branch": self.branch, "commit_sha": (data.get("commit") or {}).get("sha")}

    async def sync_files(self, files: list[dict[str, str]], message: str = "DreamCoder live sync") -> dict[str, Any]:
        results = []
        for item in files:
            results.append(await self.sync_file(item["path"], item["content"], message=f"{message}: {item['path']}"))
        return {"ok": all(r.get("ok") or r.get("skipped") for r in results), "results": results}


github_sync = GitHubSync.from_env()
