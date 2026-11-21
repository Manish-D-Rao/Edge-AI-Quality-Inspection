# Phase 03 — Inspection Service and API

## Status

The local upload-to-result API vertical slice is implemented. It currently
uses the original OpenCV reference-difference baseline (`threshold=25`,
`min_area=80`). This is the working MVP default, not a detector proven best on
verified real PCB data. Candidates are image differences, not confirmed defects.

The API is stateless: it does not keep an inspection history or raw uploaded
images. Each successful request writes a unique result JSON and generated
annotated, difference, and mask images below `outputs/inspections/<uuid>/`.
These artifacts remain until manually removed. SQLite/history and automated
retention are deferred.

## Start the backend

Run from the `backend/` directory:

```bash
./venv/bin/uvicorn main:app --reload
```

The health endpoint is `GET http://127.0.0.1:8000/api/health`. Interactive API
documentation is available at `http://127.0.0.1:8000/docs`.

## Inspect an image pair

Send multipart fields named `reference` and `test`. JPEG and PNG are supported,
with a maximum of 10 MiB per file. Filenames are ignored and are never used as
filesystem paths. The optional `threshold` is 0–255 and `min_area` must be at
least 1.

```bash
curl -X POST http://127.0.0.1:8000/api/inspect \
  -F "reference=@../datasets/synthetic/reference.jpg" \
  -F "test=@../datasets/synthetic/test.jpg" \
  -F "threshold=25" \
  -F "min_area=80"
```

The JSON response includes a unique inspection ID, detector/config IDs,
candidate boxes, measured processing time, artifact URLs, and an explicit
warning that candidates are not confirmed defects. Open the returned
`annotated`, `difference`, or `mask` URL to view the generated artifact.

## Error behavior

- `422`: empty, unsupported, or undecodable image; invalid parameter.
- `413`: either upload exceeds 10 MiB.
- `404`: unknown inspection ID or artifact name.
- `500`: detector failed; the response is generic and does not expose a stack
  trace or filesystem path.

## Next

Phase 04 can now connect its upload form to `POST /api/inspect`, render the
response candidates, and display the returned artifacts. Real detector
selection remains blocked until Phases 01–02 have a verified paired dataset,
reconciled annotations, valid splits, and a user-approved false-candidate
budget. Do not treat synthetic unit tests as PCB accuracy results.
