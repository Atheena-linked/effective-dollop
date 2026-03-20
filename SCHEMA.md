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
  "resolved_by_source": null
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
| `resolved_at` | datetime / null | UTC time a clinician marked it resolved |
| `resolution_note` | string / null | Free-text reason the clinician provided for resolution |
| `resolved_by_source` | string / null | Which source was chosen as authoritative when resolving |

### Conflict Types

| `conflict_type` | Meaning |
|---|---|
| `dosage_conflict` | Same drug, different dose across sources |
| `frequency_conflict` | Same drug, different frequency across sources |
| `missing_medication` | Drug present in one source, absent in another |
| `drug_interaction` | Two drugs the patient is on are flagged as dangerous in `conflict_rules.json` |

### Resolution Design Decision

Resolution is explicit — a clinician must call `PATCH /conflicts/{id}/resolve` with a `resolution_note` and optionally `resolved_by_source`. The system does not auto-resolve because there is no canonical truth source. The `resolved_by_source` field records which source the clinician trusted, providing an audit trail for why the conflict was closed.

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
| `(patient_id, status)` | Analytics and conflict list endpoints always filter by both fields together |
| `(patient_id, medication_name, status)` | The dedup check in `conflict_storage.py` runs this exact query on every ingestion — needs to be fast |
| `(created_at)` | The 30-day analytics window does a range scan on this field across the full collection |

---

## Design Trade-offs

### Denormalization vs references

Conflict `entries` embed the source, dosage, frequency, and timestamp directly inside each conflict document rather than referencing the originating medication document by `_id`. This means conflict records are self-contained and readable without a join, which suits an audit-trail use case. The trade-off is that if a medication record were ever corrected, the embedded entries in conflict documents would not reflect the change — acceptable here since medication snapshots are immutable by design.

### Document size

Each medication snapshot stores the full list of medications for that source. For typical patients (5–20 medications) this is well under MongoDB's 16MB document limit. A patient with hundreds of medications and thousands of ingestion events would grow the collection but not individual documents, since each ingestion is a new document.

### Future extensibility

- Adding a new conflict type requires only a new detector function in `conflict_detection.py` and a new `conflict_type` value — no schema migration needed.
- Adding clinic metadata (e.g. `clinic_id`, `clinic_name`) to conflicts would require storing it at ingestion time in the medication document and propagating it to conflict entries — the current schema does not carry clinic identity beyond the `source` field.
- Time-to-live (TTL) indexes could be added to auto-archive resolved conflicts older than a threshold, keeping the active working set small.
