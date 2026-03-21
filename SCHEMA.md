# MongoDB Schema — Medication Reconciliation Service

## Collections Overview

The service uses two collections: `medications` and `conflicts`.

---

## `medications` Collection

Stores every medication list ingestion as an immutable versioned snapshot. Each document represents one source's report of a patient's medications at a point in time. Records are never updated — a new ingestion always creates a new document with an incremented version.

### Document Structure

```json
{
  "_id": "ObjectId",
  "patient_id": "P001",
  "source": "clinic_emr",
  "version": 3,
  "timestamp": "2026-03-20T10:00:00Z",
  "medications": [
    {
      "name": "metformin",
      "dosage": "500mg",
      "frequency": "twice daily"
    },
    {
      "name": "lisinopril",
      "dosage": "10mg",
      "frequency": "once daily"
    }
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key |
| `patient_id` | string | Unique patient identifier |
| `source` | string | One of `clinic_emr`, `hospital_discharge`, `patient_reported` |
| `version` | integer | Auto-incremented per patient across all sources. Starts at 1 |
| `timestamp` | datetime | UTC time of ingestion |
| `medications` | array | List of medication objects for this snapshot |
| `medications[].name` | string | Normalised drug name (lowercased, trimmed) |
| `medications[].dosage` | string | Normalised dosage string e.g. `500mg` |
| `medications[].frequency` | string | Normalised frequency string e.g. `twice daily` |

### Versioning Design Decision

Version is a single counter per patient across all sources, not per source. This means the timeline endpoint returns a true chronological history of all ingestion events regardless of which source submitted them. The trade-off is that you cannot query "version 2 of the clinic EMR record" directly — you query by `(patient_id, version)` and the source is a field on that document.

---

## `conflicts` Collection

Stores detected conflicts as auditable records. A conflict is created when the same patient's medication records from different sources disagree. Conflicts are never deleted — they are either `active` or `resolved`.

### Document Structure

```json
{
  "_id": "ObjectId",
  "patient_id": "P001",
  "medication_name": "metformin",
  "conflict_type": "dosage_conflict",
  "severity": "medium",
  "description": null,
  "entries": [
    {
      "source": "clinic_emr",
      "dosage": "500mg",
      "frequency": "twice daily",
      "timestamp": "2026-03-20T10:00:00Z"
    },
    {
      "source": "hospital_discharge",
      "dosage": "1000mg",
      "frequency": "once daily",
      "timestamp": "2026-03-20T10:00:00Z"
    }
  ],
  "status": "active",
  "created_at": "2026-03-20T10:05:00Z",
  "resolved_at": null,
  "resolution_note": null,
  "resolved_by_source": null,
  "resolved_value": null
}
```

### Document Structure — After Smart Resolution

When resolved via `POST /conflicts/{id}/resolve/smart`, the document is updated with the full scoring audit trail:

```json
{
  "status": "resolved",
  "resolved_at": "2026-03-20T11:00:00Z",
  "resolution_note": "'1000mg once daily' chosen — score 5 (priority=3, appearances=1, recency=1), supported by: hospital_discharge",
  "resolved_by_source": "hospital_discharge",
  "resolved_value": {
    "dosage": "1000mg",
    "frequency": "once daily",
    "score": 5,
    "supporting_sources": ["hospital_discharge"],
    "all_scores": [
      {
        "dosage": "1000mg",
        "frequency": "once daily",
        "score": 5,
        "breakdown": {
          "source_priority": 3,
          "appearance_count": 1,
          "recency_bonus": 1
        },
        "supporting_sources": ["hospital_discharge"]
      },
      {
        "dosage": "500mg",
        "frequency": "twice daily",
        "score": 3,
        "breakdown": {
          "source_priority": 2,
          "appearance_count": 1,
          "recency_bonus": 0
        },
        "supporting_sources": ["clinic_emr"]
      }
    ]
  }
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Auto-generated MongoDB primary key |
| `patient_id` | string | Patient this conflict belongs to |
| `medication_name` | string | Drug name, or `"drug_a + drug_b"` for interaction conflicts |
| `conflict_type` | string | One of `dosage_conflict`, `frequency_conflict`, `missing_medication`, `drug_interaction` |
| `severity` | string | `low`, `medium`, or `high` — sourced from conflict rules for interactions, defaults to `medium` for others |
| `description` | string / null | Human-readable explanation, populated for drug interaction conflicts from `conflict_rules.json` |
| `entries` | array | The per-source data that triggered this conflict |
| `entries[].source` | string | Which source this entry came from |
| `entries[].dosage` | string / null | Dosage reported by this source (`null` for missing medication entries) |
| `entries[].frequency` | string / null | Frequency reported by this source |
| `entries[].timestamp` | datetime | When this source's record was ingested |
| `status` | string | `active` or `resolved` |
| `created_at` | datetime | UTC time the conflict was first detected |
| `resolved_at` | datetime / null | UTC time the conflict was resolved |
| `resolution_note` | string / null | Free-text clinician note, or auto-generated scoring breakdown for smart resolution |
| `resolved_by_source` | string / null | Which source was chosen as authoritative when resolving |
| `resolved_value` | object / null | Populated by smart resolution only — contains the winning dosage/frequency and full scoring breakdown for all candidates |

### Conflict Types

| `conflict_type` | Meaning |
|---|---|
| `dosage_conflict` | Same drug, different dose across sources |
| `frequency_conflict` | Same drug, different frequency across sources |
| `missing_medication` | Drug present in one source, absent in another |
| `drug_interaction` | Two drugs the patient is on are flagged as dangerous in `conflict_rules.json` |

### Resolution Design Decision

Two resolution paths exist:

**Manual resolution** — a clinician calls `PATCH /conflicts/{id}/resolve` with a `resolution_note` and optionally `resolved_by_source`. Used for drug interaction conflicts and any case where clinical judgement overrides the algorithm.

**Smart resolution** — a clinician calls `POST /conflicts/{id}/resolve/smart`. The system scores every reported `(dosage, frequency)` candidate using:

```
score = source_priority + appearance_count + recency_bonus
```

| Factor | Description |
|---|---|
| `source_priority` | Priority of the highest-trust source reporting this value: `hospital_discharge=3`, `clinic_emr=2`, `patient_reported=1` |
| `appearance_count` | Number of distinct sources reporting this exact dosage + frequency combination |
| `recency_bonus` | +1 if any supporting record is within the last 7 days, else 0 |

The highest-scoring candidate is chosen. Ties are broken by source priority. The full scoring breakdown for all candidates is stored in `resolved_value` as an auditable record. Drug interaction conflicts are excluded from smart resolution — they require a clinician decision.

---

## Conflict Rules — `conflict_rules.json`

Not a MongoDB collection — a static JSON file loaded once at startup. Defines dangerous drug combinations checked during conflict detection.

```json
{
  "conflicts": [
    {
      "drug_1": "Aspirin",
      "drug_2": "Ibuprofen",
      "severity": "high",
      "description": "Increased risk of bleeding"
    },
    {
      "drug_1": "Paracetamol",
      "drug_2": "Alcohol",
      "severity": "medium",
      "description": "Liver damage risk"
    },
    {
      "drug_1": "Metformin",
      "drug_2": "Alcohol",
      "severity": "high",
      "description": "Risk of lactic acidosis"
    }
  ]
}
```

This is acceptable for the current scope. A production system would replace this with calls to a drug interaction API such as RxNorm or DrugBank.

---

## Indexes

### `medications` collection

```python
# Compound index — primary access pattern: fetch all records for a patient
# Used by: conflict detection, timeline endpoint, GET /medications/{patient_id}
medication_collection.create_index([("patient_id", 1), ("version", -1)])

# Used by: get_next_version() which sorts by version descending to find the latest
medication_collection.create_index([("patient_id", 1), ("timestamp", -1)])
```

### `conflicts` collection

```python
# Compound index — most read queries filter by patient + status
# Used by: GET /conflicts/{patient_id}?status=active, analytics pipeline
conflict_collection.create_index([("patient_id", 1), ("status", 1)])

# Used by: deduplication check in conflict_storage.py
# Checks for existing active conflict on (patient_id, medication_name, status)
conflict_collection.create_index([
    ("patient_id", 1),
    ("medication_name", 1),
    ("status", 1)
])

# Used by: /analytics/conflicts-per-clinic — filters by created_at >= last 30 days
conflict_collection.create_index([("created_at", -1)])
```

### Indexing Rationale

| Index | Reason |
|---|---|
| `(patient_id, version)` | Every conflict detection run fetches all records for a patient — without this it is a full collection scan |
| `(patient_id, timestamp)` | `get_next_version()` sorts by version descending on every ingestion — needs to be fast |
| `(patient_id, status)` | Analytics and conflict list endpoints always filter by both fields together |
| `(patient_id, medication_name, status)` | The dedup check in `conflict_storage.py` runs this exact query on every ingestion — needs to be fast |
| `(created_at)` | The 30-day analytics window does a range scan on this field across the full collection |

---

## Trade-offs

### Denormalization vs references

Conflict `entries` embed the source, dosage, frequency, and timestamp directly inside each conflict document rather than referencing the originating medication document by `_id`. This means conflict records are self-contained and readable without a join, which suits an audit-trail use case. The trade-off is that if a medication record were ever corrected, the embedded entries in conflict documents would not reflect the change — acceptable here since medication snapshots are immutable by design.

### Document size

Each medication snapshot stores the full list of medications for that source. For typical patients (5–20 medications) this is well under MongoDB's 16MB document limit. A patient with hundreds of medications and thousands of ingestion events would grow the collection but not individual documents, since each ingestion is a new document.

### Resolved value storage

Smart resolution stores the full `all_scores` array inside the conflict document. For a patient with many sources and many medications this array stays small (one entry per unique dosage/frequency pair), so document size is not a concern. The benefit is a fully self-contained audit trail — no separate collection needed to explain why a conflict was resolved the way it was.

### Future extensibility

- Adding a new conflict type requires only a new detector function in `conflict_detection.py` and a new `conflict_type` value — no schema migration needed.
- Adding clinic metadata (e.g. `clinic_id`, `clinic_name`) to conflicts would require storing it at ingestion time in the medication document and propagating it to conflict entries — the current schema does not carry clinic identity beyond the `source` field.
- The smart resolution scoring weights (`SOURCE_PRIORITY`, `RECENCY_DAYS`) are constants in `conflict_resolution.py` — moving them to a config file or database document would allow tuning without a code deploy.
- Time-to-live (TTL) indexes could be added to auto-archive resolved conflicts older than a threshold, keeping the active working set small.
- Update endpoint can be added
- A mechanism to create a new snapshot after resolution with source as resolution 