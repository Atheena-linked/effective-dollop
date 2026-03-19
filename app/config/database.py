from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGO_URL)

database = client.medication_db

medication_collection = database.get_collection("medications")
conflict_collection = database.get_collection("conflicts")