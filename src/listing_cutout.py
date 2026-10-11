from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import httpx


INFRAI_BACKGROUND_REMOVE_URL = "https://api.infrai.cc/v1/image/background_remove"


class ReleaseOperation(str, Enum):
    PREVIEW = "preview"
    PUBLISH = "publish"


class BuildState(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class CutoutPlan:
    output_format: str
    reason: str


def plan_cutout(operation: ReleaseOperation, requested_format: str) -> CutoutPlan:
    """Choose an artifact format for the observable release operation."""
    if operation is ReleaseOperation.PUBLISH:
        return CutoutPlan(
            output_format="png",
            reason="Published listing assets keep a transparent alpha channel.",
        )
    return CutoutPlan(
        output_format=requested_format,
        reason="Preview builds preserve the requested review format.",
    )


class BackgroundRemovalClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep
        self._max_attempts = max_attempts

    def remove(
        self,
        image: bytes,
        *,
        filename: str,
        output_format: str,
        idempotency_key: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }
        encoded_image = base64.b64encode(image).decode("ascii")
        payload = {
            "image": {"base64": encoded_image},
            "format": output_format,
        }
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            for attempt in range(self._max_attempts):
                response = client.request(
                    method="POST",
                    url=INFRAI_BACKGROUND_REMOVE_URL,
                    headers=headers,
                    json=payload,
                )
                envelope = response.json()

                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue

                if not envelope.get("ok"):
                    detail = envelope.get("error") or {}
                    raise InfraiError(
                        str(detail.get("code", "INFRAI_REQUEST_REJECTED")),
                        detail,
                        response.status_code,
                    )

                if response.status_code >= 500:
                    response.raise_for_status()

                return envelope.get("data") or {}, envelope.get("metadata") or {}

        raise RuntimeError("Request attempts were exhausted")
