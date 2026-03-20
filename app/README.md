# Medication Reconciliation & Conflict Reporting Service

A FastAPI + MongoDB service that ingests medication lists from multiple clinical sources, detects conflicts across those sources, and surfaces unresolved conflicts for clinicians.

---

## Setup

### Prerequisites
- Python 3.10+
- MongoDB running locally on port `27017` (or a MongoDB Atlas URI)

### Install & run

```bash
git clone <your-repo-url>
cd <repo-folder>

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set MONGO_URL and DB_NAME if needed

uvicorn app.main:app --reload
```

API will be live at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

## Architecture

```
app/
├── main.py                  # FastAPI app, router registration
├── config/
│   └── database.py          # MongoDB client + collection handles
├── data/
│   └── conflict_rules.json  # Static drug interaction rules
├── routes/
│   ├── medication_routes.py # Ingest + retrieve medication records
│   ├── conflict_routes.py   # Detect, list, and resolve conflicts
│   ├── timeline_routes.py   # Version history and diffs
│   └── analytics.py         # Reporting / aggregation endpoints
├── schemas/
│   ├── medication_schema.py # Pydantic models for ingestion
│   └── conflict_schema.py   # Pydantic models for conflicts
├── service/
│   ├── conflict_detection.py  # Core detection logic (dosage, missing, interactions)
│   ├── conflict_storage.py    # Dedup + persist conflicts to MongoDB
│   └── load_rules.py          # Load and cache conflict_rules.json
└── utils/
    ├── normalization.py     # Lowercase/trim dosage and frequency
    └── versioning.py        # Auto-increment version per patient
```

**Request flow:**  
`POST /medications` → normalize → version → store snapshot  
`POST /conflicts_detect_and_store/{patient_id}` → load all snapshots → detect conflicts → dedup → store

---

## API Endpoints

### Medications
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/medications` | Ingest a medication list for a patient from a source |
| `GET` | `/medications/{patient_id}` | Get all medication snapshots for a patient |

### Conflicts
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/conflicts_detect_and_store/{patient_id}` | Run conflict detection and persist results |
| `GET` | `/conflicts/{patient_id}` | List conflicts (optional `?status=active\|resolved`) |
| `PATCH` | `/conflicts/{conflict_id}/resolve` | Mark a conflict resolved with a reason |

### Timeline
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/patients/{patient_id}/timeline` | Full version history sorted by time |
| `GET` | `/patients/{patient_id}/timeline/{version}` | Specific version snapshot |
| `GET` | `/patients/{patient_id}/timeline/diff/{v1}/{v2}` | Medications added/removed between two versions |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/patients/high-conflicts` | Patients with ≥ 2 unresolved conflicts |
| `GET` | `/analytics/conflicts-per-clinic` | Clinics with patients having ≥ 2 conflicts in last 30 days |

---

## Conflict Detection

Three types of conflicts are detected:

- **Dosage conflict** — same drug reported by multiple sources with different doses
- **Missing medication** — drug present in one source but absent from another
- **Drug interaction** — two drugs the patient is on are flagged as a dangerous combination in `conflict_rules.json`

Source priority (used to indicate which source is most authoritative):  
`hospital_discharge (3) > clinic_emr (2) > patient_reported (1)`

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
  "resolved_by_source": null
}
```

**Indexes recommended:**
- `medications`: compound index on `(patient_id, version)`
- `conflicts`: index on `(patient_id, status)`
- `conflicts`: index on `created_at` for the 30-day analytics window

---

## Assumptions & Trade-offs

- **No canonical truth source.** Conflicts are flagged and surfaced to clinicians — the system does not auto-resolve. Resolution requires an explicit `PATCH` call with a `resolution_note` and optional `resolved_by_source`.
- **New record = new version.** Every ingestion from any source creates a new versioned snapshot rather than updating in place. This gives a full audit trail at the cost of more documents.
- **Denormalized conflict entries.** Source details are embedded inside each conflict document rather than referenced. This makes conflict reads fast and self-contained, at the cost of some duplication.
- **Static drug rules.** `conflict_rules.json` is loaded once at startup and cached. Suitable for this scope; a production system would use a drug interaction API.
- **Sources are validated** against `clinic_emr`, `hospital_discharge`, `patient_reported` on ingestion.

---

## Known Limitations & What I'd Do Next

- **No seed script yet** — add a `seed.py` to generate 10–20 patients with varied conflicts for demo purposes
- **No tests yet** — priority additions: conflict detection edge cases (missing fields, same drug same dose, malformed payload) and one aggregation test
- **No authentication** — all endpoints are open; a real deployment would add OAuth2 or API key middleware
- **No pagination** on `GET /medications/{patient_id}` — could return large payloads for patients with many records
- **MongoDB indexes** are not created automatically on startup — should be added to `database.py` using `create_index()` calls

---

## AI Tools Used

- Used Claude to review the codebase for bugs before submission — identified the hardcoded file path in `load_rules.py`, the `dict["key", default]` syntax error in `timeline_routes.py`, and the analytics pipeline querying wrong collection fields.
- Manually reviewed and applied each fix, checking that the logic matched the intended behavior rather than accepting suggestions blindly.
- Disagreed with the suggestion to add MongoDB index creation inside `database.py` at import time — this runs on every cold start and can cause startup failures if MongoDB is briefly unavailable. Deferred to a migration script instead.
