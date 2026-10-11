import json

import httpx

from listing_cutout import BackgroundRemovalClient, ReleaseOperation, plan_cutout


def test_publish_build_chooses_png_for_transparent_listing_artifact() -> None:
    plan = plan_cutout(ReleaseOperation.PUBLISH, requested_format="webp")

    assert plan.output_format == "png"
    assert "transparent" in plan.reason


def test_request_boundary_sends_decision_and_idempotency_key() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert request.method == "POST"
        assert request.headers["Idempotency-Key"] == "build-17:listing-4:publish"
        assert request.headers["Content-Type"] == "application/json"
        assert body == {
            "image": {"base64": "aW1hZ2UtYnl0ZXM="},
            "format": "png",
        }
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "ok": True,
                    "data": {"id": "asset-92"},
                    "error": None,
                    "metadata": {"vendor": "auto"},
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )

    client = BackgroundRemovalClient(
        "test-key",
        transport=httpx.MockTransport(respond),
        sleep=lambda _: None,
    )
    data, metadata = client.remove(
        b"image-bytes",
        filename="terminal-card.jpg",
        output_format="png",
        idempotency_key="build-17:listing-4:publish",
    )

    assert data == {"id": "asset-92"}
    assert metadata == {"vendor": "auto"}
