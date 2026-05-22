"""Thin REST wrapper around the Engram (Lumetra) API.

Six endpoints are exposed, mirroring the standard Engram surface:

    store_memory(content, bucket)
    query(query, bucket)
    list_memories(bucket, limit=...)
    list_buckets()
    delete_memory(memory_id, bucket)
    clear_memories(bucket)

The wrapper has no MetaGPT dependency and is reused by
`EngramMemory` and the Engram Actions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


DEFAULT_BASE_URL = "https://api.lumetra.io"


class EngramClient:
    """Synchronous REST client for the Engram API.

    All methods raise `requests.HTTPError` on non-2xx responses.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        key = api_key or os.environ.get("ENGRAM_API_KEY")
        if not key:
            raise RuntimeError(
                "ENGRAM_API_KEY not set. Pass api_key=... or "
                "export ENGRAM_API_KEY=eng_live_..."
            )
        self.api_key = key
        self.base_url = (
            base_url
            or os.environ.get("ENGRAM_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # internals                                                          #
    # ------------------------------------------------------------------ #

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    # operations                                                         #
    # ------------------------------------------------------------------ #

    def store_memory(self, content: str, bucket: str) -> Dict[str, Any]:
        r = requests.post(
            f"{self.base_url}/v1/buckets/{bucket}/memories",
            headers=self._headers(),
            json={"content": content},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def query(
        self,
        query: str,
        bucket: Optional[str] = None,
        buckets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"query": query}
        if buckets:
            body["buckets"] = buckets
        elif bucket:
            body["buckets"] = [bucket]
        r = requests.post(
            f"{self.base_url}/v1/query",
            headers=self._headers(),
            json=body,
            timeout=120.0,
        )
        r.raise_for_status()
        return r.json()

    def list_memories(self, bucket: str, limit: int = 100) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/v1/buckets/{bucket}/memories",
            headers=self._headers(),
            params={"limit": limit},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def list_buckets(self) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/v1/buckets",
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def delete_memory(self, memory_id: str, bucket: str) -> None:
        r = requests.delete(
            f"{self.base_url}/v1/buckets/{bucket}/memories/{memory_id}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()

    def clear_memories(self, bucket: str) -> None:
        r = requests.delete(
            f"{self.base_url}/v1/buckets/{bucket}/memories",
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()


def extract_final_answer(answer: str) -> str:
    """Engram `/v1/query` returns a reasoning trace followed by
    ``FINAL ANSWER:``. Surface just the final answer to callers.
    """
    if not answer:
        return ""
    if "FINAL ANSWER:" in answer:
        return answer.split("FINAL ANSWER:", 1)[1].strip()
    return answer.strip()
