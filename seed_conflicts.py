import asyncio
from datetime import datetime, timedelta
from app.config.database import conflict_collection

async def seed_data():
    now = datetime.utcnow()

    data = [
        # clinicA - p1 (3 conflicts ✅)
        {"patient_id": "p1", "source": "clinicA", "timestamp": now - timedelta(days=5)},
        {"patient_id": "p1", "source": "clinicA", "timestamp": now - timedelta(days=4)},
        {"patient_id": "p1", "source": "clinicA", "timestamp": now - timedelta(days=3)},

        # clinicA - p2 (2 conflicts ✅)
        {"patient_id": "p2", "source": "clinicA", "timestamp": now - timedelta(days=6)},
        {"patient_id": "p2", "source": "clinicA", "timestamp": now - timedelta(days=2)},

        # clinicA - p3 (1 conflict ❌)
        {"patient_id": "p3", "source": "clinicA", "timestamp": now - timedelta(days=1)},

        # clinicB - p4 (2 conflicts ✅)
        {"patient_id": "p4", "source": "clinicB", "timestamp": now - timedelta(days=7)},
        {"patient_id": "p4", "source": "clinicB", "timestamp": now - timedelta(days=3)},

        # clinicB - p5 (1 conflict ❌)
        {"patient_id": "p5", "source": "clinicB", "timestamp": now - timedelta(days=2)},
    ]

    await conflict_collection.insert_many(data)

    print("✅ Test data inserted successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())