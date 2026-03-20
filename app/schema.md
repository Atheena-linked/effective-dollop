# MongoDB Schema Description

## Overview

Two collections power the service: **medications** and **conflicts**.  
There is no separate `patients` collection — the `patient_id` string acts as the patient identifier and is embedded directly in both collections. This is an intentional denormalization trade-off discussed below.

---

## Collection 1: `medications`

Stores every ingested medication snapshot. Each document represents one source's medication list for one patient at a point in time. A new document is inserted on every ingestion — records are **never overwritten** — giving a full longitudinal history.

```json
{
  "_id":          "ObjectId",
  "patient_id":   "P001",
  "source":       "hospital_discharge",
  "version":      3,
  "timestamp":    "2025-01-15T10:30:00Z",
  "medications": [
    {
      "name":      "aspirin",
      "dosage":    "100mg",
      "frequency": "once daily"
    },
    {
      "name":      "metformin",
      "dosage":    "500mg",
      "frequency": "twice daily"
    }
  ]
}
```

### Field Notes

| Field | Type | Notes |
|---|---|---|
| `patient_id` | string | Shared identifier across both collections |
| `source` | string | One of `hospital_discharge`, `clinic_emr`, `patient_reported` |
| `version` | int | Monotonically increasing per patient. Version 1 = first ever ingestion |
| `timestamp` | datetime | Set at ingestion time (UTC) |
| `medications` | array | Normalized — names lowercased, units trimmed |

---

## Collection 2: `conflicts`

Stores one document per detected conflict. Conflicts are **never duplicated** — `store_conflicts()` checks for an existing active conflict before inserting. Conflicts are resolved in place by updating `status`, `resolved_at`, and `resolution_note`.

```json
{
  "_id":             "ObjectId",
  "patient_id":      "P001",
  "medication_name": "aspirin + ibuprofen",
  "conflict_type":   "drug_interaction",
  "severity":        "high",
  "description":     "Increased risk of bleeding",
  "entries": [
    {
      "source":    "hospital_discharge",
      "medication": "aspirin",
      "dosage":    "100mg",
      "frequency": "once daily",
      "timestamp": "2025-01-15T10:30:00Z"
    },
    {
      "source":    "clinic_emr",
      "medication": "ibuprofen",
      "dosage":    "200mg",
      "frequency": "twice daily",
      "timestamp": "2025-01-15T09:00:00Z"
    }
  ],
  "status":          "active",
  "created_at":      "2025-01-15T10:30:00Z",
  "resolved_at":     null,
  "resolution_note": null
}
```

### Field Notes

| Field | Type | Notes |
|---|---|---|
| `conflict_type` | string | One of `missing_medication`, `dosage_conflict`, `frequency_conflict`, `drug_interaction` |
| `severity` | string | `high`, `medium`, `low` — populated from `conflict_rules.json` for drug interactions, defaults to `medium` for others |
| `entries` | array | Each entry captures the source and drug details involved in the conflict |
| `status` | string | `active` or `resolved` |
| `resolved_at` | datetime | Null until a clinician resolves the conflict |
| `resolution_note` | string | Free-text reason for resolution (e.g. "Hospital record trusted over patient report") |

---

## Indexes

### `medications` collection

```python
# 1. Primary query pattern — fetch all records for a patient
{ "patient_id": 1 }

# 2. Timeline query — fetch history sorted by time
{ "patient_id": 1, "timestamp": -1 }

# 3. Fetch a specific version of a patient's record
{ "patient_id": 1, "version": -1 }

# 4. Fetch all records for a patient from a specific source
{ "patient_id": 1, "source": 1 }
```

### `conflicts` collection

```python
# 1. Fetch all conflicts for a patient (most common query)
{ "patient_id": 1 }

# 2. Reporting — filter by patient + status (active/resolved)
{ "patient_id": 1, "status": 1 }

# 3. Deduplication check in store_conflicts()
{ "patient_id": 1, "medication_name": 1, "status": 1 }

# 4. Clinic-level reporting — count patients with unresolved conflicts
{ "status": 1 }
```

---

## Design Trade-offs

### 1. No separate `patients` collection
**Decision:** `patient_id` is embedded directly in both collections rather than referencing a separate patients document.

**Reason:** The service's job is medication reconciliation, not patient management. A patients collection would add a join (lookup) on every query with no benefit given the current feature set.

**Trade-off:** If patient metadata (name, clinic, demographics) is needed later, it would have to be added to every document or a patients collection introduced at that point.

---

### 2. Insert-only medications (no updates)
**Decision:** Every ingestion creates a new document. Existing records are never modified.

**Reason:** This gives a full audit trail — you can always see what any source reported at any point in time. The `version` field makes it easy to navigate history.

**Trade-off:** The collection grows indefinitely. For a patient with frequent updates across 3 sources, you accumulate documents quickly. Mitigation: a TTL index or archival policy could be added later.

---

### 3. Medications embedded as an array (not a separate collection)
**Decision:** The medications list is an array inside the snapshot document rather than individual documents in a `medications` collection.

**Reason:** Medications are always read and written together as a list — they have no independent existence outside a snapshot. Embedding avoids multi-document reads on every ingestion and query.

**Trade-off:** MongoDB documents have a 16MB size limit. For a patient on an extremely large number of medications across many versions this is not a practical concern, but it is a theoretical ceiling.

---

### 4. Conflicts resolved in-place
**Decision:** Resolving a conflict updates the existing document (`status`, `resolved_at`, `resolution_note`) rather than inserting a new resolved document.

**Reason:** A conflict has a clear lifecycle (active → resolved) and clinicians query by status. In-place updates keep the model simple and avoid needing to reconcile two documents for the same conflict.

**Trade-off:** There is no history of who resolved a conflict or whether it was re-opened. A future improvement would be to add a `resolution_history` array to track multiple state changes.
