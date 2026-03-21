# Medication Reconciliation & Conflict Reporting Service

A FastAPI + MongoDB service that ingests medication lists from multiple clinical sources, detects conflicts across those sources, and surfaces unresolved conflicts for clinicians. Supports longitudinal version history, score-based automatic conflict resolution, and aggregation reporting.

---

## Setup

### Prerequisites
- Python 3.10+
- MongoDB running locally on port `27017` (or a MongoDB Atlas URI)

### Install & run

```bash
git clone https://github.com/Atheena-linked/effective-dollop
cd effective-dollop

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set MONGO_URL and DB_NAME if needed

# Seed the database with 20 test patients (run once before starting the app)
python seed.py

# Start the API
uvicorn app.main:app --reload
```

API live at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`  
Hosted at `https://effective-dollop-l16e.onrender.com`

---

## Architecture

```
app/
├── main.py                    # FastAPI app, router registration
├── config/
│   └── database.py            # MongoDB client + collection handles
├── data/
│   └── conflict_rules.json    # Static drug interaction rules
├── routes/
│   ├── medication_routes.py   # Ingest + retrieve medication records
│   ├── conflict_routes.py     # Detect, list, and resolve conflicts
│   ├── timeline_routes.py     # Version history, diffs, analytics
│   └── analytics.py           # Additional reporting endpoints
├── schemas/
│   ├── medication_schema.py   # Pydantic input/internal models
│   └── conflict_schema.py     # Pydantic models for conflicts
├── service/
│   ├── conflict_detection.py  # Core detection logic
│   ├── conflict_storage.py    # Dedup + persist conflicts
│   ├── conflict_resolution.py # Score-based resolution algorithm
│   └── load_rules.py          # Load and cache conflict_rules.json
└── utils/
    ├── normalization.py       # Lowercase/trim dosage and frequency
    └── versioning.py          # Auto-increment version per patient
```

**Request flow:**  
`POST /medications` → normalize → auto-version → store snapshot  
`POST /conflicts_detect_and_store/{patient_id}` → load all snapshots → detect → dedup → store

---

## API Endpoints

### Medications
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/medications` | Ingest a medication list for a patient from a source |
| `GET` | `/medications/{patient_id}` | Get all medication snapshots for a patient |

**Example POST body:**
```json
{
  "patient_id": "P001",
  "source": "clinic_emr",
  "medications": [
    { "name": "metformin", "dosage": "500mg", "frequency": "twice daily" }
  ]
}
```

---

### Conflicts
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/conflicts_detect_and_store/{patient_id}` | Run conflict detection and persist results |
| `GET` | `/conflicts/{patient_id}` | List conflicts (optional `?status=active` or `?status=resolved`) |
| `PATCH` | `/conflicts/{conflict_id}/resolve` | Manually resolve a conflict with a clinician note |
| `POST` | `/conflicts/{conflict_id}/resolve/smart` | Auto-resolve using the score-based algorithm |

---

### Timeline
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/patients/{patient_id}/timeline` | Full version history sorted by timestamp |
| `GET` | `/patients/{patient_id}/timeline/{version}` | Fetch a specific version snapshot |
| `GET` | `/patients/{patient_id}/timeline/diff/{v1}/{v2}` | Medications added, removed, and unchanged between two versions |

---

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/patients/high-conflicts` | Patients with ≥ 2 active unresolved conflicts |
| `GET` | `/analytics/conflicts-per-clinic` | Per-clinic count of patients with ≥ 2 conflicts in the last 30 days |

---

## Conflict Detection

Four conflict types are detected when `POST /conflicts_detect_and_store/{patient_id}` is called:

| Type | Description |
|------|-------------|
| `dosage_conflict` | Same drug reported by multiple sources with different doses |
| `frequency_conflict` | Same drug reported with different frequency across sources |
| `missing_medication` | Drug present in one source but absent from another |
| `drug_interaction` | Two drugs the patient is on are flagged as dangerous in `conflict_rules.json` |

Drug interactions currently flagged:
- **Aspirin + Ibuprofen** — increased risk of bleeding (high severity)
- **Paracetamol + Alcohol** — liver damage risk (medium severity)
- **Metformin + Alcohol** — risk of lactic acidosis (high severity)

Source priority (used in resolution scoring):  
`hospital_discharge (3) > clinic_emr (2) > patient_reported (1)`

---

## Conflict Resolution

Two resolution paths are available:

### Manual Resolution
`PATCH /conflicts/{conflict_id}/resolve`

A clinician provides a free-text `resolution_note` and optionally `resolved_by_source`. The conflict is marked `resolved` with a full audit trail.

```json
{
  "resolution_note": "Hospital discharge dose accepted as authoritative.",
  "resolved_by_source": "hospital_discharge"
}
```

### Smart Resolution (Score-Based)
`POST /conflicts/{conflict_id}/resolve/smart`

Automatically scores every reported `(dosage, frequency)` candidate for the conflicting medication and picks the winner. The scoring formula is:

```
score = source_priority + appearance_count + recency_bonus
```

| Factor | Description |
|--------|-------------|
| `source_priority` | Priority of the highest-trust source reporting this value (1–3) |
| `appearance_count` | Number of distinct sources reporting this exact dosage + frequency |
| `recency_bonus` | +1 if any supporting record is within the last 7 days, else 0 |

The winning value, full score breakdown, and all candidate scores are stored on the conflict document as an audit trail.

> **Note:** Drug interaction conflicts cannot be smart-resolved — they require a clinician decision via the manual endpoint.

---

## Data Model

### `medications` collection
```json
{
  "patient_id": "P001",
  "source": "clinic_emr",
  "medications": [
    { "name": "metformin", "dosage": "500mg", "frequency": "twice daily" }
  ],
  "timestamp": "2026-03-20T10:00:00Z",
  "version": 1
}
```

### `conflicts` collection
```json
{
  "patient_id": "P001",
  "medication_name": "metformin",
  "conflict_type": "dosage_conflict",
  "severity": "medium",
  "entries": [
    { "source": "clinic_emr", "dosage": "500mg", "frequency": "twice daily", "timestamp": "..." },
    { "source": "hospital_discharge", "dosage": "1000mg", "frequency": "once daily", "timestamp": "..." }
  ],
  "status": "active",
  "created_at": "2026-03-20T10:05:00Z",
  "resolved_at": null,
  "resolution_note": null,
  "resolved_by_source": null,
  "resolved_value": null
}
```

Full schema documentation including indexes and trade-off rationale: [`SCHEMA.md`](./SCHEMA.md)

---

## Seed Script

`seed.py` generates 20 patients covering all base and edge cases:

| Category | Patients | What's tested |
|----------|----------|---------------|
| Base cases | P001–P008 | Single source, all sources agree, dosage conflict, frequency conflict, missing medication, all three drug interactions |
| Edge cases | P009–P020 | Three-way conflict, dosage+frequency on same drug, multiple conflict types simultaneously, empty dosage/frequency fields, mixed-case drug names, whitespace in names, no false positives, unit notation mismatch (500mg vs 0.5g), pre-resolved conflict |

```bash
python seed.py
```

---

## Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/test_conflicts.py -v
```

**46 tests — all passing.**

| Test class | What's covered |
|------------|---------------|
| `TestNormalization` | Dosage/frequency lowercasing, space removal, None and empty string handling |
| `TestDosageAndFrequencyConflicts` | Basic conflicts, three-way conflicts, no false positives, single source |
| `TestMissingMedicationConflicts` | Detected when absent, not flagged when all sources present |
| `TestDrugInteractions` | All three interaction rules, safe drugs produce no interaction |
| `TestEdgeCases` | Empty fields, mixed case, whitespace, empty list, multiple conflict types |
| `TestIngestionEndpoint` | Valid payload, empty medications rejected, blank patient_id rejected, malformed JSON rejected |
| `TestAggregationEndpoints` | Both aggregation endpoints return 200 with correct response shape |
| `TestScoringAlgorithm` | Higher priority wins, appearance count boost, recency bonus applied/not applied, unknown medication, all scores returned, breakdown string present |
| `TestSmartResolveEndpoint` | Successful resolution, drug interaction blocked, already resolved blocked, invalid ID, not found |

> **Note:** Tests produce deprecation warnings from `datetime.utcnow()` — these are Python 3.12+ notices and do not affect functionality.

---

## Assumptions & Trade-offs

- **No canonical truth source.** Conflicts are flagged and surfaced to clinicians. The smart resolve endpoint provides a scored recommendation but a manual resolve path is always available.
- **New record = new version.** Every ingestion creates a new versioned snapshot rather than updating in place, giving a full audit trail at the cost of more documents.
- **Denormalized conflict entries.** Source details are embedded inside each conflict document rather than referenced. This makes conflict reads fast and self-contained at the cost of some duplication. Since medication snapshots are immutable, embedded data will not go stale.
- **Static drug rules.** `conflict_rules.json` is loaded once at startup and cached. A production system would replace this with a drug interaction API such as RxNorm or DrugBank.
- **Version is global per patient, not per source.** The timeline returns a true chronological history of all ingestion events regardless of source. The trade-off is that you cannot query "version 2 of the clinic EMR record" directly.

---

## Known Limitations

- **No authentication** — all endpoints are open; a real deployment would add OAuth2 or API key middleware
- **No pagination** on list endpoints — could return large payloads for patients with many records
- **Unit notation not normalized** — `500mg` and `0.5g` are treated as different dosages (flagged as a conflict even though they are clinically identical)
- **MongoDB indexes** are not created automatically on startup — should be added to `database.py` using `create_index()` calls in production

---

## AI Tools Used

Used AI to assist with debugging, code review,  generating test data and test cases and README.md and SCHEMA.md files
