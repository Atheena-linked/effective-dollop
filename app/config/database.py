from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "medication_db")

client = AsyncIOMotorClient(MONGO_URL)

database = client[DB_NAME]

medication_collection = database.get_collection("medications")
conflict_collection = database.get_collection("conflicts")