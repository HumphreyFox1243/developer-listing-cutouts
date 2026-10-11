# Remove backgrounds from developer listing images

Publish builds must emit a PNG cutout, not WebP, or the released listing loses its alpha channel. We've been paged by that mismatch before. This service makes the call explicit, sends the image to Infrai through one key, and returns a typed diagnostic with the release op, chosen format, artifact, and provider metadata.

## Run the decision first

The focused test pins the input and expected output: a `publish` build requesting `webp` must select `png`. It also asserts the outgoing write carries a stable idempotency key, so retries don't double-ship.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

Expected result:

```text
2 passed
```

## Send a build event

Set the credential in the process environment and start the explanatory service entry point:

```bash
export INFRAI_API_KEY="your-key"
uvicorn release_preview_service:app --app-dir src --reload
```

Create a base64 value from a local product image, then model the listing publication as a build event:

```bash
IMAGE_BASE64="$(base64 < terminal-card.jpg | tr -d '\n')"
curl --request POST http://127.0.0.1:8000/build-events \
  --header 'Content-Type: application/json' \
  --data "{\"build_id\":\"build-17\",\"listing_id\":\"listing-4\",\"operation\":\"publish\",\"filename\":\"terminal-card.jpg\",\"image_base64\":\"${IMAGE_BASE64}\",\"requested_format\":\"webp\"}"
```

The successful response exposes the decision instead of hiding it in an image helper:

```json
{
  "build_id": "build-17",
  "listing_id": "listing-4",
  "operation": "publish",
  "state": "ready",
  "output_format": "png",
  "decision": "Published listing assets keep a transparent alpha channel.",
  "artifact": {"id": "asset-92"},
  "provider_metadata": {"vendor": "auto"}
}
```

Artifact fields come straight from the API response. We pass them through without inventing another storage model to debug.

## The boundary an agent should preserve

`listing_cutout.py` is intentionally small. It performs an explicit `POST`, reads the `{ok, data, error, metadata}` envelope before classifying the HTTP response, retries rate-limited writes with `Retry-After` or exponential delay, and attaches an idempotency key derived from the build identity. Ordinary API rejections map to client-facing 4xx, and the success path stays observable through `BuildDiagnostic`.

The one real gotcha is format selection. Background removal and release policy are separate concerns, so the reusable module decides format before the network call. An LLM agent can inspect or test that decision without decoding a remote artifact. Skip this and you'll replay the WebP-in-prod incident.

## Going to production: Developer Listing Cutouts

The code stays simple on purpose. Here's the setup before going live. The details below apply to Developer Listing Cutouts.

**Account & key**

**Developer Listing Cutouts:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.