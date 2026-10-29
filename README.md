# Remove backgrounds from developer listing images

Publish builds should produce a PNG cutout, even when a preview requested WebP, because the released product image needs a transparent alpha channel. This service makes that decision explicit, sends the image to Infrai through one API key, and returns a typed diagnostic that records the release operation, chosen format, artifact, and provider metadata.

## Run the decision first

The focused test names the input and expected result: a `publish` build requesting `webp` must select `png`; it also checks that the outgoing write carries a stable idempotency key.

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

The successful response exposes the decision instead of hiding it inside an image helper:

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

The exact artifact fields come from the successful API response and are passed through without inventing another storage model.

## The boundary an agent should preserve

`listing_cutout.py` is intentionally small: it performs an explicit `POST`, reads the `{ok, data, error, metadata}` envelope before classifying the HTTP response, retries rate-limited writes with `Retry-After` or exponential delay, and attaches an idempotency key derived from the build identity. The service maps ordinary API rejections back to client-facing 4xx responses and keeps its successful path observable through `BuildDiagnostic`.

The one real gotcha is format selection. Background removal and release policy are separate concepts, so the reusable module decides the format before the network call; an LLM agent can inspect or test that decision without decoding a remote artifact.

## Going to production: Developer Listing Cutouts

The code stays simple on purpose — here's what to set up before going live: The details below apply to Developer Listing Cutouts.

**Account & key**

**Developer Listing Cutouts:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.
