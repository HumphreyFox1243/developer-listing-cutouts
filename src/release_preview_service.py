from __future__ import annotations

import base64
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from listing_cutout import (
    BackgroundRemovalClient,
    BuildState,
    InfraiError,
    ReleaseOperation,
    plan_cutout,
)


class ListingBuildEvent(BaseModel):
    build_id: str = Field(min_length=1)
    listing_id: str = Field(min_length=1)
    operation: ReleaseOperation
    filename: str = Field(min_length=1)
    image_base64: str = Field(min_length=1)
    requested_format: str = Field(default="webp", pattern="^(png|webp)$")


class BuildDiagnostic(BaseModel):
    build_id: str
    listing_id: str
    operation: ReleaseOperation
    state: BuildState
    output_format: str
    decision: str
    artifact: dict[str, Any]
    provider_metadata: dict[str, Any]


app = FastAPI(title="Developer listing cutout service")


@app.post("/build-events", response_model=BuildDiagnostic)
def handle_build_event(event: ListingBuildEvent) -> BuildDiagnostic:
    plan = plan_cutout(event.operation, event.requested_format)
    try:
        image = base64.b64decode(event.image_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="image_base64 must be valid base64") from exc

    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")

    client = BackgroundRemovalClient(api_key)
    try:
        artifact, metadata = client.remove(
            image,
            filename=event.filename,
            output_format=plan.output_format,
            idempotency_key=f"{event.build_id}:{event.listing_id}:{event.operation.value}",
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return BuildDiagnostic(
        build_id=event.build_id,
        listing_id=event.listing_id,
        operation=event.operation,
        state=BuildState.READY,
        output_format=plan.output_format,
        decision=plan.reason,
        artifact=artifact,
        provider_metadata=metadata,
    )
