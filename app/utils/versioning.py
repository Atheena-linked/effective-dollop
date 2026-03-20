async def get_next_version(collection, patient_id: str) :
    """
    Returns the next version number for a given patient.
    If no records exist, starts from version 1.
    """

    latest_record = await collection.find_one(
        {"patient_id": patient_id},
        sort=[("version", -1)]
    )

    if not latest_record:
        return 1

    current_version = latest_record.get("version", 0)
    return current_version + 1