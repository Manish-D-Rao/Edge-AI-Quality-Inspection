# Edge Vision-Language PCB Inspection — MVP Implementation Plan

## Purpose and success target

This plan turns the current OpenCV prototype into a small, reproducible
upload-to-results MVP. It is intentionally divided into short tasks that can
be assigned one at a time to coding agents with limited context.

The requested **70% target means defect-instance recall**:

```text
recall = matched ground-truth defect instances / all ground-truth defect instances
```

It does **not** mean overall accuracy, and it is not guaranteed by this plan.
The target may be reported as met only after evaluating against a held-out,
human-labeled real PCB set. Report precision, false-positive burden, dataset
split, matching rule, and latency beside recall. The current two-edit synthetic
demo and unlabeled real image pair cannot validate this target.

The first user-visible MVP is:

1. User uploads reference and test PCB images.
2. The system proposes localized suspicious regions using an evaluated
   localization method (the existing difference baseline remains available).
3. The UI displays the annotated image, candidate details, and latency, with a
   clear warning that a proposal is not a confirmed defect.
4. An optional VLM may explain a selected crop; inspection must still work
   when that model is unavailable.

Live camera and MQTT are explicitly outside the first MVP unless the team
later makes them a must-have.

## Current state — verified work only

### Phase 00 — setup and project scaffold

- **DONE:** Git repository and agreed top-level folders exist.
- **DONE:** Local Linux backend virtual environment exists and has been used
  for project tests and OpenCV experiments.
- **DONE:** React/Vite frontend scaffold exists.
- **PARTIAL:** A FastAPI app exists with `GET /api/health`.
- **NOT VERIFIED:** Clean setup on the second teammate's machine; Node/Python/
  Git/RAM comparison on both machines; webcam access; Ollama/VLM resource
  feasibility; decision on which machine should run the VLM.

### Phase 01 — image acquisition and baseline experiments

- **DONE:** OpenCV baseline loads image pairs, resizes the test to reference
  dimensions when needed, preprocesses grayscale images, computes thresholded
  differences, filters contours, and writes annotated/difference/mask images
  plus JSON.
- **DONE:** Synthetic image generator and known line/circle test edits exist.
- **DONE:** Real-pair images were copied without changing original bytes;
  synthetic data has a separate folder. Inventory and provenance uncertainty
  are documented.
- **DONE:** Baseline, alignment, alignment evaluation, support/border artifact,
  localization-noise, candidate-merging, and preprocessing experiments have
  separate scripts/reports and unit tests.
- **PARTIAL:** The synthetic pair verifies only two synthetic edits; it is not
  real PCB accuracy evidence.
- **NOT DONE:** Human-verified defect labels for the real pair or a real
  held-out test set. No measured real defect recall/precision exists.
- **NOT DONE:** Selection of an improved detector; the exploratory alignment,
  merge, and preprocessing settings are not proven improvements and are not
  the production baseline.

The implementation agents must preserve all completed behavior and existing
outputs. Do not mark an experiment as an accuracy improvement based only on
candidate-count reduction.

## Operating rules for small coding agents

1. Assign **one mini-phase task per agent run**. Do not ask one agent to
   implement an entire phase.
2. Before editing, read the listed inputs and inspect current repository state.
   Do not assume a prior task's output or overwrite it.
3. Stay within the task's listed files. If another file must change, explain
   the dependency and ask before broadening scope.
4. Keep existing APIs and algorithm behavior unless the task explicitly
   changes them. Prefer separate modules/feature flags for experimental
   detectors.
5. Add a focused test for each new behavior. Run the exact command in the task
   and report changed files, command output, and unresolved issues.
6. Never fabricate defect labels, model explanations, evaluation values, or
   performance claims. Use `Not evaluated` where evidence is absent.
7. Do not install dependencies unless an approved task explicitly needs one.
   First check whether existing OpenCV/NumPy/FastAPI/React dependencies suffice.
8. Do not commit generated datasets, user input images, large output files,
   secrets, virtual environments, or `node_modules`.

## Requirements

- **REQ-001 — Labeled evidence:** Create an agreed annotation schema and
  leakage-resistant development/validation/held-out splits for real PCB
  examples.
- **REQ-002 — Measured localization:** Preserve the baseline and compare it
  with lightweight localization alternatives using fixed, documented
  configurations and labeled evidence.
- **REQ-003 — Honest 70% target:** Measure defect-instance recall on held-out
  data; report precision, false-positive burden, latency, denominator, and
  limitations. Do not claim the target if unsupported.
- **REQ-004 — Inspection API:** Accept and validate an image pair and return
  structured inspection results and viewable artifacts.
- **REQ-005 — Dashboard:** Let a user upload the pair, run inspection, and
  view results, errors, latency, and limitations without using the CLI.
- **REQ-006 — Optional VLM:** If feasible, explain selected crop evidence with
  uncertainty; unavailable model must not disable classical inspection.
- **REQ-007 — Reproducible handoff:** Document clean setup and verify the
  end-to-end demo from a clean checkout and on both teammates' machines.

## Phases and executable task breakdown

Checkboxes are status markers: `[x]` means existing work was verified in this
workspace; `[ ]` means future work. Do not mark a future task complete until
its acceptance checks pass.

### Phase 00 — Setup and hardware verification

Current status: project scaffold/local environment are present; multi-machine
and hardware/model checks remain.

#### Mini-phase 00.1 — Record both developer environments

- [x] **T001 [Plan:00.1]** Keep the repository root, backend, frontend,
  datasets, docs, and outputs folders as the current agreed layout.
- [x] **T002 [Plan:00.1]** Keep the local Linux Python virtual environment and
  existing React/Vite scaffold; do not recreate or overwrite them.
- [ ] **T003 [Plan:00.1]** Add a small environment checklist to
  `docs/mvp-setup.md` for Python, OpenCV, Node.js, npm, Git, OS, CPU, and
  available RAM; record results separately for both teammates.
- [ ] **T004 [Plan:00.1]** Have teammate 2 follow the current setup using
  `backend/requirements.txt` and `frontend/package-lock.json`; record exact
  failures/fixes in `docs/mvp-setup.md`.
- **Acceptance:** Both teammates can start the backend health endpoint and
  frontend dev server from documented commands; environment details are
  recorded without guessing.

#### Mini-phase 00.2 — Webcam and VLM feasibility

- [ ] **T005 [Plan:00.2]** Add a manual webcam check procedure to
  `docs/mvp-setup.md`; run OpenCV camera open/read/release checks on machines
  where a camera is available. Do not add a background capture loop yet.
- [ ] **T006 [Plan:00.2]** Record existing Ollama availability, available RAM,
  and whether the proposed small VLM can be loaded on each machine in
  `docs/mvp-setup.md`. Do not download models until the team approves a model
  and machine.
- [ ] **T007 [Plan:00.2]** Choose and document the VLM host only after a real
  load/inference test; otherwise mark model deployment as deferred.
- **Acceptance:** Camera and VLM status are evidenced per machine; no VLM
  machine is chosen from hardware specifications alone.

### Phase 01 — Baseline and dataset foundation

Current status: baseline and experiments are implemented. Dataset labeling and
real performance evaluation remain incomplete. T015, T016, and T018 require
source/provenance information and human-verified image labels that are not
available in the current workspace; those tasks remain blocked rather than
being inferred from synthetic or unlabeled images.

#### Mini-phase 01.1 — Preserve and document the baseline

- [x] **T008 [Plan:01.1]** Keep the OpenCV baseline in
  `backend/app/services/inspection_baseline.py` unchanged as the benchmark.
- [x] **T009 [Plan:01.1]** Keep synthetic generation isolated in
  `backend/create_demo_images.py`; it refuses to overwrite an existing
  synthetic pair.
- [x] **T010 [Plan:01.1]** Keep baseline behavior and Phase 01 results in
  `docs/phase-01-results.md`.
- [x] **T011 [Plan:01.1]** Keep dataset paths and provenance limitations in
  `docs/phase-01-dataset-inventory.md`.
- **Acceptance:** Existing baseline tests pass and original dataset files and
  prior outputs remain untouched.

#### Mini-phase 01.2 — Complete labeled dataset specification

- [x] **T012 [Plan:01.2]** Create `docs/annotation-guidelines.md` defining
  normal/defect/uncertain labels, defect instance identity, bounding-box
  coordinates, occlusion handling, and how annotators handle ambiguous cases.
- [x] **T013 [Plan:01.2]** Add
  `datasets/labels/README.md` describing an annotation JSON format keyed by
  image/sample ID; do not put private or unlicensed imagery into Git.
- [x] **T014 [Plan:01.2]** Add a schema validator in
  `backend/app/services/annotation_schema.py` and focused tests in
  `backend/tests/test_annotation_schema.py`.
- **Acceptance:** A valid labeled sample passes; missing IDs, invalid boxes,
  and unsupported labels fail with actionable messages. Annotation meaning is
  clear enough for two people to label consistently.

#### Mini-phase 01.3 — Collect, annotate, and split the real data

- [ ] **T015 [Plan:01.3]** Collect normal and defective examples only from
  images the team may legally use; record source, board/revision if known,
  capture session, camera/lighting, and consent/license in
  `datasets/labels/dataset_manifest.csv`. **Blocked:** existing real samples
  have unknown provenance and are marked unlabeled/pending.
- [ ] **T016 [Plan:01.3]** Have two annotators independently label a subset and
  reconcile disagreements using `docs/annotation-guidelines.md`; store labels
  in the agreed schema. **Blocked:** no verified annotations from two
  annotators were supplied.
- [x] **T017 [Plan:01.3]** Add
  `backend/scripts/create_dataset_split.py` to make deterministic
  development/validation/held-out splits grouped by board or capture session,
  and save IDs (not image copies) under `datasets/labels/splits/`.
- [ ] **T018 [Plan:01.3]** Begin with at least 50 labeled defect instances and
  50 normal images overall, with at least 20 defect instances and 20 normal
  images held out; record the actual counts and warn that this small holdout
  gives imprecise estimates. **Blocked:** current labeled real-image counts
  and held-out membership do not meet the minimums.
- **Acceptance:** No board/capture session leaks across splits; annotations
  validate; manifest and split membership are reproducible. If counts are not
  met, the 70% recall goal remains blocked, not silently waived.

### Phase 02 — Define and implement a localization benchmark beyond raw difference

Current status: evaluation metrics, a fail-closed dataset runner, and an
experimental structural detector are implemented and covered by fixture tests.
The available synthetic comparison and not-evaluable held-out report are
documented. No alternative has been validated on labeled real defects because
the current manifest, annotations, and held-out split are not a valid paired
evaluation set. Do not interpret synthetic results or fixture tests as PCB
detection accuracy.

#### Mini-phase 02.1 — Establish evaluation metrics and matching

- [x] **T019 [Plan:02.1]** Add
  `backend/app/services/detection_metrics.py` for defect-instance matching
  between candidate boxes and labeled boxes using IoU >= 0.3 as an explicit
  initial rule. Prevent multiple candidates from claiming the same ground
  truth instance.
- [x] **T020 [Plan:02.1]** Report recall, precision, F1, false candidate boxes
  per normal image, per-class results, and latency in
  `backend/tests/test_detection_metrics.py` fixtures and metric JSON.
- [x] **T021 [Plan:02.1]** Ask the project owner to set an acceptable
  false-candidate budget on normal images before comparing operating points;
  record the chosen limit and rationale in the experiment report. **Approved
  MVP starting point:** mean <=5 false candidate boxes per normal image for a
  manually reviewed prototype. This is a review-workload target, not a
  production quality limit.
- **Acceptance:** Hand-calculated fixtures pass, including empty predictions,
  empty ground truth, duplicate matches, and IoU threshold boundary cases.

#### Mini-phase 02.2 — Build a controlled dataset runner

- [x] **T022 [Plan:02.2]** Add
  `backend/app/services/dataset_evaluation.py` to run a detector over the
  manifest/split IDs and produce machine-readable per-image and aggregate
  metrics.
- [x] **T023 [Plan:02.2]** Add
  `backend/run_dataset_evaluation.py` with explicit split, detector, config,
  and output arguments; refuse to overwrite existing evaluation directories.
- [x] **T024 [Plan:02.2]** Add tests using tiny temporary image/annotation
  fixtures in `backend/tests/test_dataset_evaluation.py`.
- **Acceptance:** A deterministic fixture dataset can be evaluated without
  reading or writing production dataset images; JSON includes split identity
  and fixed detector configuration.

#### Mini-phase 02.3 — Implement a separate lightweight structural candidate method

- [x] **T025 [Plan:02.3]** Add a detector interface in
  `backend/app/services/detector_protocol.py` with one stable input/output
  contract; retain baseline CLI and API behavior.
- [x] **T026 [Plan:02.3]** Add a separately named experimental detector in
  `backend/app/services/structural_anomaly_detector.py`. Compare reference/test
  images after reliable registration and valid-source masking; combine
  intensity difference with a local structural or gradient difference map.
  Keep all tunable values in an explicit config object.
- [x] **T027 [Plan:02.3]** Add small synthetic unit fixtures and tests in
  `backend/tests/test_structural_anomaly_detector.py` for identical images,
  a known local edit, invalid alignment/support, and coordinate consistency.
- **Acceptance:** The detector returns reference-coordinate candidate boxes
  and diagnostic maps, fails safely if alignment/support is invalid, and does
  not modify `inspection_baseline.py`.

#### Mini-phase 02.4 — Compare baseline and alternative on labeled splits

- [ ] **T028 [Plan:02.4]** Run baseline and structural detector on development
  and validation splits with identical image pairs and metric rules; save to
  distinct `outputs/model_selection/<run-id>/` directories.
- [x] **T029 [Plan:02.4]** Document available per-class recall, precision,
  normal-image false-candidate status, latency, parameters, failure cases,
  and visualization examples in `docs/phase-02-detector-selection.md`.
  The only available evidence is explicitly labeled synthetic; real split
  comparison and normal-image false-candidate rate remain not evaluable.
- [ ] **T030 [Plan:02.4]** Freeze the selected detector/configuration only if
  validation meets the pre-agreed false-candidate budget; otherwise keep the
  baseline available, report the recall target unmet, and list the next data
  need.
- **Acceptance:** No held-out results are used for tuning. Candidate-count
  decrease is never the selection metric by itself.

#### Mini-phase 02.5 — Held-out 70% recall gate

- [ ] **T031 [Plan:02.5]** Run the frozen detector once on the held-out split
  and save raw outputs/metrics to a new `outputs/held_out_evaluation/<run-id>/`.
- [x] **T032 [Plan:02.5]** Document the held-out recall numerator/denominator,
  matching rule, precision, false candidates per normal image, latency, split
  counts, uncertainty, and limitations in `docs/mvp-evaluation-report.md`.
  The report states not evaluable because the valid held-out split is empty
  and real labels are pending.
- **Acceptance:** State “at least 70% recall met” only if measured recall is
  >=0.70 on the defined held-out data and the false-candidate budget is met.
  Otherwise state that the target is not met or not evaluable.

### Phase 03 — Inspection service and API

Current status: the stateless upload-to-result API vertical slice is
implemented with the OpenCV baseline as a provisional default. The baseline
has not been frozen as the best detector because real-data comparison remains
blocked by dataset labeling and split gaps. See
`docs/phase-03-api.md`.

#### Mini-phase 03.1 — Define API request/response types

- [x] **T033 [Plan:03.1]** Add Pydantic request/response schemas in
  `backend/app/schemas/inspection.py` for status, candidate boxes,
  detector/config ID, artifact URLs, and measured latency.
- [x] **T034 [Plan:03.1]** Add tests in
  `backend/tests/test_inspection_schemas.py` for valid responses and invalid
  coordinates/fields.
- **Acceptance:** API returns a stable, documented schema; no claim field
  labels a candidate as a confirmed defect.

#### Mini-phase 03.2 — Create upload inspection service

- [x] **T035 [Plan:03.2]** Add
  `backend/app/services/inspection_service.py` to decode validated uploaded
  bytes, use the baseline as the provisional API default, and return result
  metadata plus generated artifact URLs. Detector selection is not frozen
  until the real-data gate is complete.
- [x] **T036 [Plan:03.2]** Add image validation for supported formats,
  undecodable bytes, zero-length files, and a documented maximum upload size
  in `backend/app/services/image_validation.py`.
- [x] **T037 [Plan:03.2]** Add unit tests in
  `backend/tests/test_inspection_service.py` using synthetic fixtures and
  mocked persistence only where required.
- **Acceptance:** Service does not trust filenames as paths, does not overwrite
  user files, returns explicit validation failures, and invokes the chosen
  detector only after both images decode.

#### Mini-phase 03.3 — Implement and test HTTP routes

- [x] **T038 [Plan:03.3]** Add `POST /api/inspect` in
  `backend/main.py` or a small `backend/app/api/inspection.py` router; accept
  reference/test multipart uploads and return typed result JSON.
- [x] **T039 [Plan:03.3]** Keep `GET /api/health` and add artifact serving only
  through validated IDs/paths that remain within the configured output root.
- [x] **T040 [Plan:03.3]** Add FastAPI tests in
  `backend/tests/test_inspection_api.py` for success, invalid image, oversize
  upload, detector failure, and artifact access.
- **Acceptance:** `POST /api/inspect` works in-process via the test client;
  errors have appropriate status codes/messages and do not expose stack traces
  or arbitrary filesystem paths.

#### Mini-phase 03.4 — Choose persistence scope

- [x] **T041 [Plan:03.4]** For the first MVP, document whether history is
  required. History is not required for this local demo; successful runs use
  unique IDs and filesystem result/artifact files.
- [x] **T042 [Plan:03.4]** Defer SQLite metadata/history because history was not
  requested. Do not add a repository or database until the owner confirms the
  feature is needed.
- **Acceptance:** No database is added just for future flexibility; if history
  is chosen, it does not store raw images by default and has a documented
  retention policy.

### Phase 04 — React dashboard vertical slice

Current status: `frontend/src/App.jsx` is the Vite starter.

#### Mini-phase 04.1 — Replace starter content with upload form

- [ ] **T043 [Plan:04.1]** Replace the Vite demo in
  `frontend/src/App.jsx` with reference/test file selectors and an Inspect
  action; keep API calls in `frontend/src/api/inspection.js`.
- [ ] **T044 [Plan:04.1]** Add upload layout and responsive styles in
  `frontend/src/App.css` and `frontend/src/index.css`; make file selections and
  labels accessible.
- **Acceptance:** User can select both files, sees filenames, cannot submit
  while one is missing, and can submit without browser console errors.

#### Mini-phase 04.2 — Connect API and handle UI states

- [ ] **T045 [Plan:04.2]** Implement typed-by-validation response parsing,
  multipart request creation, and useful error normalization in
  `frontend/src/api/inspection.js`.
- [ ] **T046 [Plan:04.2]** Add idle/loading/success/error states in
  `frontend/src/App.jsx`; do not lose selected images or display stale result
  after a failed request.
- **Acceptance:** API errors and network failures are visible and recoverable;
  loading prevents duplicate submissions.

#### Mini-phase 04.3 — Show inspection evidence

- [ ] **T047 [Plan:04.3]** Display the annotated image and candidate list with
  coordinates, dimensions, and configured detector in
  `frontend/src/App.jsx`.
- [ ] **T048 [Plan:04.3]** Display difference/mask artifacts, processing time,
  and persistent “image-difference candidates are not confirmed defects”
  wording in the dashboard.
- [ ] **T049 [Plan:04.3]** Add frontend tests for upload, success rendering,
  error handling, and no-result state using existing project tooling if
  available; do not install a test framework without approval.
- **Acceptance:** One user can complete both-image upload → inspect → view
  result without a terminal, and the result is understandable at normal
  browser sizes.

### Phase 05 — Optional VLM crop explanations

Current status: not implemented; model and host are not selected.

#### Mini-phase 05.1 — Define replaceable VLM contract

- [ ] **T050 [Plan:05.1]** Add a provider interface in
  `backend/app/services/vlm_provider.py` returning visible evidence,
  suspected category, uncertainty, and provider status.
- [ ] **T051 [Plan:05.1]** Add schema validation and tests in
  `backend/tests/test_vlm_provider.py`; invalid model output must not become a
  success-shaped answer.
- **Acceptance:** Interface can be tested with a fake provider and does not
  alter detector candidates.

#### Mini-phase 05.2 — Test Ollama on selected host

- [ ] **T052 [Plan:05.2]** After Phase 00 resource approval, add an Ollama
  adapter in `backend/app/services/ollama_vlm_provider.py` for the agreed
  model and strict timeout; keep the model name configurable.
- [ ] **T053 [Plan:05.2]** Measure load/inference time and peak memory for
  selected crop sizes; record machine/model/version and results in
  `docs/vlm-feasibility.md`.
- **Acceptance:** No full-resolution board is sent unnecessarily; model timeout
  or missing Ollama is explicit and does not fail image inspection.

#### Mini-phase 05.3 — Add optional crop explanation

- [ ] **T054 [Plan:05.3]** Add an optional endpoint/service operation for
  explaining a selected candidate crop, referencing the inspection run and
  candidate index.
- [ ] **T055 [Plan:05.3]** Add an “Explain crop” UI control and show model
  evidence/uncertainty/status without presenting generated content as verified
  truth.
- **Acceptance:** Baseline inspection works with VLM disabled/unavailable;
  VLM output is clearly marked as model-generated and includes uncertainty.

### Phase 06 — Final MVP verification and handoff

#### Mini-phase 06.1 — Clean setup and documentation

- [ ] **T056 [Plan:06.1]** Add root `README.md` or update the existing one with
  clean backend/frontend setup, startup, upload demo, tests, and generated
  output locations.
- [ ] **T057 [Plan:06.1]** Document dataset provenance/license and exclude
  virtual environments, `node_modules`, private datasets, and generated
  outputs from source control in `.gitignore` as appropriate.
- **Acceptance:** A teammate can reproduce setup from a fresh clone using
  documented commands and existing lock/requirements files.

#### Mini-phase 06.2 — Full flow regression and live rehearsal

- [ ] **T058 [Plan:06.2]** Run backend tests, frontend build/lint, and API
  integration tests; record command results in `docs/mvp-release-checklist.md`.
- [ ] **T059 [Plan:06.2]** Rehearse the upload-to-result flow on both teammate
  machines using synthetic data and at least one permitted real example.
- [ ] **T060 [Plan:06.2]** Verify the held-out evaluation report is present
  before using any 70% claim in presentation/README; otherwise label the demo
  as an unvalidated prototype.
- **Acceptance:** Clean startup, upload, output display, error path, optional
  model-unavailable path, and evaluation claim all pass review.

## Requirement mapping

| Requirement | Description | Plan items | Evidence/files |
|---|---|---|---|
| REQ-001 | Labeled real-data evidence and split | 01.2, 01.3 | `docs/annotation-guidelines.md`, `datasets/labels/`, `backend/app/services/annotation_schema.py`, `backend/scripts/create_dataset_split.py` |
| REQ-002 | Compare baseline with measured localization alternative | 02.1–02.4 | `backend/app/services/structural_anomaly_detector.py`, `backend/run_dataset_evaluation.py`, `docs/phase-02-detector-selection.md` |
| REQ-003 | Honest held-out recall and error burden | 02.1, 02.5, 06.2 | `backend/app/services/detection_metrics.py`, `docs/mvp-evaluation-report.md` |
| REQ-004 | Validated inspection API | 03.1–03.4 | `backend/app/schemas/inspection.py`, `backend/app/services/inspection_service.py`, `backend/main.py`, API tests |
| REQ-005 | Browser upload and result display | 04.1–04.3 | `frontend/src/App.jsx`, `frontend/src/api/inspection.js`, styles/tests |
| REQ-006 | Optional, uncertainty-aware VLM explanation | 00.2, 05.1–05.3 | `backend/app/services/vlm_provider.py`, optional Ollama adapter, crop explanation UI |
| REQ-007 | Reproducible handoff | 00.1, 06.1–06.2 | `docs/mvp-setup.md`, `README.md`, `docs/mvp-release-checklist.md` |

## Suggested task assignment

- Assign T012–T018 to the data/annotation owner; most are manual coordination
  and data preparation, not coding-agent tasks.
- Assign one agent at a time for T019–T024 (metrics and runner), then a
  separate agent for T025–T030 (alternative detector and selection report).
- Once the API schema is agreed, assign one agent per mini-phase 03.x and
  04.x. Avoid simultaneous edits to `backend/main.py` or `frontend/src/App.jsx`.
- Keep VLM tasks optional and gated by the resource check.
- Ask each small agent to return: files changed, behavior added, tests run,
  measured output, and known limitations. Review before marking `[x]`.

## Project structure after MVP work

```text
backend/
  app/
    api/                         # FastAPI routers (planned)
    schemas/                     # request/response and annotation schemas (planned)
    services/
      inspection_baseline.py     # existing, preserved baseline
      image_alignment.py         # existing isolated alignment module
      inspection_service.py      # planned API-facing orchestration
      structural_anomaly_detector.py # planned, separate alternative
      detection_metrics.py       # planned labeled evaluation metrics
      vlm_provider.py            # planned optional interface
  scripts/
    create_dataset_split.py      # planned
  tests/                         # existing tests plus focused new tests
  main.py                        # existing health route; planned inspect route
  requirements.txt
datasets/
  real_pcb/                      # existing, provenance/labels not verified
  synthetic/                     # existing generated demo pair
  labels/                        # planned manifests, annotations, split IDs
docs/
  phase-01-*.md                  # completed baseline/experiment reports
  mvp-implementation-plan.md     # this plan
  annotation-guidelines.md       # planned
  mvp-evaluation-report.md       # planned
frontend/
  src/
    api/inspection.js            # planned
    App.jsx                      # current Vite starter; planned MVP UI
outputs/                          # generated; keep out of source control
```

## MVP go/no-go statement

The project is ready for API/UI implementation, but it is **not ready to claim
70% real defect recall**. First collect and annotate representative real PCB
examples. If the measured held-out recall or false-candidate burden fails the
agreed criteria, present the result as an image-comparison prototype and keep
the detector improvement work open rather than making an unsupported accuracy
claim.
