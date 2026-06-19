import os
from pymongo import MongoClient

# Use env var with a fallback
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "docai")

# Create a single reusable client
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
job_logs = db["job_logs"]
