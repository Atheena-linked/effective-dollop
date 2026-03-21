"""
Tests for medication reconciliation service.

Covers:
  - Conflict detection edge cases (dose mismatches, missing fields, malformed payloads)
  - At least one aggregation endpoint

Run from the project root:
    pip install pytest pytest-asyncio httpx
    pytest tests/test_conflicts.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.service.conflict_detection import (
    detect_conflicts,
    build_med_index,
    detect_dosage_and_freq_conflicts,
    detect_missing_medication_conflicts,
    detect_drug_interactions,
)
from app.utils.normalization import normalize_dosage, normalize_frequency

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────
# HELPERS — build fake medication records the same way the DB would
# ─────────────────────────────────────────────────────────────────

def make_record(patient_id, source, medications):
    return {
        "patient_id": patient_id,
        "source": source,
        "medications": medications,
    }


# ─────────────────────────────────────────────────────────────────
# NORMALIZATION UNIT TESTS
# ─────────────────────────────────────────────────────────────────

class TestNormalization:

    def test_dosage_lowercased(self):
        assert normalize_dosage("500MG") == "500mg"

    def test_dosage_spaces_removed(self):
        assert normalize_dosage("100 mg") == "100mg"

    def test_dosage_empty_string(self):
        assert normalize_dosage("") == ""

    def test_dosage_none(self):
        assert normalize_dosage(None) == ""

    def test_frequency_lowercased(self):
        assert normalize_frequency("Once Daily") == "once daily"

    def test_frequency_strips_whitespace(self):
        assert normalize_frequency("  twice daily  ") == "twice daily"

    def test_frequency_empty_string(self):
        assert normalize_frequency("") == ""

    def test_frequency_none(self):
        assert normalize_frequency(None) == ""


# ─────────────────────────────────────────────────────────────────
# CONFLICT DETECTION — DOSAGE & FREQUENCY
# ─────────────────────────────────────────────────────────────────

class TestDosageAndFrequencyConflicts:

    def test_dosage_conflict_detected(self):
        records = [
            make_record("P001", "clinic_emr", [{"name": "metformin", "dosage": "500mg", "frequency": "twice daily"}]),
            make_record("P001", "hospital_discharge", [{"name": "metformin", "dosage": "1000mg", "frequency": "twice daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types

    def test_frequency_conflict_detected(self):
        records = [
            make_record("P001", "clinic_emr", [{"name": "amlodipine", "dosage": "5mg", "frequency": "once daily"}]),
            make_record("P001", "hospital_discharge", [{"name": "amlodipine", "dosage": "5mg", "frequency": "twice daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "frequency_conflict" in types

    def test_no_conflict_when_all_sources_agree(self):
        records = [
            make_record("P002", "clinic_emr", [{"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"}]),
            make_record("P002", "hospital_discharge", [{"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"}]),
            make_record("P002", "patient_reported", [{"name": "amlodipine", "dosage": "10mg", "frequency": "once daily"}]),
        ]
        conflicts = detect_conflicts(records)
        assert conflicts == []

    def test_three_way_dosage_conflict(self):
        records = [
            make_record("P009", "clinic_emr", [{"name": "prednisolone", "dosage": "5mg", "frequency": "once daily"}]),
            make_record("P009", "hospital_discharge", [{"name": "prednisolone", "dosage": "10mg", "frequency": "once daily"}]),
            make_record("P009", "patient_reported", [{"name": "prednisolone", "dosage": "20mg", "frequency": "once daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types

    def test_dosage_and_frequency_conflict_on_same_drug(self):
        records = [
            make_record("P010", "clinic_emr", [{"name": "sertraline", "dosage": "50mg", "frequency": "once daily"}]),
            make_record("P010", "hospital_discharge", [{"name": "sertraline", "dosage": "100mg", "frequency": "twice daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types
        assert "frequency_conflict" in types

    def test_single_source_no_conflict(self):
        records = [
            make_record("P001", "clinic_emr", [{"name": "levothyroxine", "dosage": "50mcg", "frequency": "once daily"}]),
        ]
        conflicts = detect_conflicts(records)
        assert conflicts == []


# ─────────────────────────────────────────────────────────────────
# CONFLICT DETECTION — MISSING MEDICATION
# ─────────────────────────────────────────────────────────────────

class TestMissingMedicationConflicts:

    def test_missing_medication_detected(self):
        records = [
            make_record("P005", "clinic_emr", [
                {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
                {"name": "simvastatin", "dosage": "40mg", "frequency": "once daily"},
            ]),
            make_record("P005", "patient_reported", [
                {"name": "ramipril", "dosage": "5mg", "frequency": "once daily"},
                # simvastatin missing
            ]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "missing_medication" in types

    def test_no_missing_medication_when_all_present(self):
        records = [
            make_record("P002", "clinic_emr", [
                {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
            ]),
            make_record("P002", "hospital_discharge", [
                {"name": "furosemide", "dosage": "40mg", "frequency": "once daily"},
            ]),
        ]
        conflicts = detect_conflicts(records)
        missing = [c for c in conflicts if c["conflict_type"] == "missing_medication"]
        assert missing == []


# ─────────────────────────────────────────────────────────────────
# CONFLICT DETECTION — DRUG INTERACTIONS
# ─────────────────────────────────────────────────────────────────

class TestDrugInteractions:

    def test_aspirin_ibuprofen_interaction(self):
        records = [
            make_record("P006", "clinic_emr", [{"name": "aspirin", "dosage": "75mg", "frequency": "once daily"}]),
            make_record("P006", "hospital_discharge", [{"name": "ibuprofen", "dosage": "400mg", "frequency": "three times daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "drug_interaction" in types

    def test_paracetamol_alcohol_interaction(self):
        records = [
            make_record("P007", "clinic_emr", [{"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"}]),
            make_record("P007", "patient_reported", [
                {"name": "paracetamol", "dosage": "500mg", "frequency": "four times daily"},
                {"name": "alcohol", "dosage": "n/a", "frequency": "occasionally"},
            ]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "drug_interaction" in types

    def test_metformin_alcohol_interaction(self):
        records = [
            make_record("P008", "clinic_emr", [{"name": "metformin", "dosage": "500mg", "frequency": "once daily"}]),
            make_record("P008", "patient_reported", [
                {"name": "metformin", "dosage": "500mg", "frequency": "once daily"},
                {"name": "alcohol", "dosage": "n/a", "frequency": "daily"},
            ]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "drug_interaction" in types

    def test_no_interaction_for_safe_drugs(self):
        records = [
            make_record("P002", "clinic_emr", [
                {"name": "levothyroxine", "dosage": "50mcg", "frequency": "once daily"},
                {"name": "omeprazole", "dosage": "20mg", "frequency": "once daily"},
            ]),
        ]
        conflicts = detect_conflicts(records)
        interactions = [c for c in conflicts if c["conflict_type"] == "drug_interaction"]
        assert interactions == []


# ─────────────────────────────────────────────────────────────────
# EDGE CASES — MISSING / MALFORMED FIELDS
# ─────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dosage_field_does_not_crash(self):
        records = [
            make_record("P013", "clinic_emr", [{"name": "lisinopril", "dosage": "", "frequency": "once daily"}]),
            make_record("P013", "hospital_discharge", [{"name": "lisinopril", "dosage": "10mg", "frequency": "once daily"}]),
        ]
        # Should not raise — empty dosage normalizes to ""
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types

    def test_empty_frequency_field_does_not_crash(self):
        records = [
            make_record("P014", "clinic_emr", [{"name": "atorvastatin", "dosage": "20mg", "frequency": ""}]),
            make_record("P014", "hospital_discharge", [{"name": "atorvastatin", "dosage": "20mg", "frequency": "once daily"}]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "frequency_conflict" in types

    def test_mixed_case_drug_name_normalizes(self):
        records = [
            make_record("P015", "clinic_emr", [{"name": "MeTfOrMiN", "dosage": "500mg", "frequency": "twice daily"}]),
            make_record("P015", "hospital_discharge", [{"name": "metformin", "dosage": "1000mg", "frequency": "once daily"}]),
        ]
        conflicts = detect_conflicts(records)
        # Both should normalize to "metformin" and trigger dosage + frequency conflicts
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types

    def test_whitespace_in_drug_name_normalizes(self):
        records = [
            make_record("P016", "clinic_emr", [{"name": "  aspirin  ", "dosage": "75mg", "frequency": "once daily"}]),
            make_record("P016", "hospital_discharge", [{"name": "ibuprofen", "dosage": "400mg", "frequency": "twice daily"}]),
        ]
        # "  aspirin  " should strip to "aspirin" and trigger the aspirin+ibuprofen interaction
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "drug_interaction" in types

    def test_empty_medications_list_does_not_crash(self):
        records = [
            make_record("P999", "clinic_emr", []),
        ]
        conflicts = detect_conflicts(records)
        assert conflicts == []

    def test_no_records_does_not_crash(self):
        conflicts = detect_conflicts([])
        assert conflicts == []

    def test_multiple_conflict_types_on_one_patient(self):
        records = [
            make_record("P011", "clinic_emr", [
                {"name": "warfarin", "dosage": "2mg", "frequency": "once daily"},
                {"name": "aspirin", "dosage": "75mg", "frequency": "once daily"},
            ]),
            make_record("P011", "hospital_discharge", [
                {"name": "warfarin", "dosage": "5mg", "frequency": "once daily"},
                {"name": "ibuprofen", "dosage": "400mg", "frequency": "twice daily"},
            ]),
        ]
        conflicts = detect_conflicts(records)
        types = [c["conflict_type"] for c in conflicts]
        assert "dosage_conflict" in types
        assert "drug_interaction" in types


# ─────────────────────────────────────────────────────────────────
# API ENDPOINT TESTS — INGESTION
# ─────────────────────────────────────────────────────────────────

class TestIngestionEndpoint:

    @patch("app.routes.medication_routes.medication_collection")
    @patch("app.routes.medication_routes.get_next_version", new_callable=AsyncMock)
    def test_valid_payload_returns_200(self, mock_version, mock_collection):
        mock_version.return_value = 1
        mock_collection.insert_one = AsyncMock(return_value=MagicMock())

        response = client.post("/medications", json={
            "patient_id": "P001",
            "source": "clinic_emr",
            "medications": [
                {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"}
            ]
        })
        assert response.status_code == 200
        assert response.json() == {"message": "Record stored"}

    def test_empty_medications_list_rejected(self):
        # Test the validator directly — empty list should raise ValueError
        with pytest.raises(Exception) as exc_info:
            from app.schemas.medication_schema import MedicationRecord
            MedicationRecord(
                patient_id="P001",
                source="clinic_emr",
                medications=[]
            )
        assert "empty" in str(exc_info.value).lower()

    def test_blank_patient_id_rejected(self):
        # Test the validator directly — blank patient_id should raise ValueError
        with pytest.raises(Exception) as exc_info:
            from app.schemas.medication_schema import MedicationRecord
            MedicationRecord(
                patient_id="   ",
                source="clinic_emr",
                medications=[
                    {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"}
                ]
            )
        assert "blank" in str(exc_info.value).lower()

    def test_missing_required_field_rejected(self):
        # Missing "source"
        response = client.post("/medications", json={
            "patient_id": "P001",
            "medications": [
                {"name": "metformin", "dosage": "500mg", "frequency": "twice daily"}
            ]
        })
        assert response.status_code == 422

    def test_malformed_json_rejected(self):
        response = client.post(
            "/medications",
            data="not-json-at-all",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


# ─────────────────────────────────────────────────────────────────
# AGGREGATION ENDPOINT TEST
# ─────────────────────────────────────────────────────────────────

class TestAggregationEndpoints:

    @patch("app.routes.timeline_routes.conflict_collection")
    def test_high_conflicts_returns_200(self, mock_collection):
        # Motor's aggregate returns a cursor directly (not a coroutine)
        # so mock it as a regular MagicMock with __aiter__ support
        class FakeCursor:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration

        mock_collection.aggregate = MagicMock(return_value=FakeCursor())

        response = client.get("/patients/high-conflicts")
        assert response.status_code == 200
        assert "patients" in response.json()

    @patch("app.routes.timeline_routes.conflict_collection")
    def test_conflicts_per_clinic_returns_200(self, mock_collection):
        class FakeCursor:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration

        mock_collection.aggregate = MagicMock(return_value=FakeCursor())

        response = client.get("/analytics/conflicts-per-clinic")
        assert response.status_code == 200
        assert "clinics" in response.json()
