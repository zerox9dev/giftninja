import os
from typing import Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

# Ensure environment variables are loaded
load_dotenv(override=False)

_mongo_client: Optional[AsyncIOMotorClient] = None


def _get_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        _mongo_client = AsyncIOMotorClient(uri)
    return _mongo_client


def get_db_name() -> str:
    return os.getenv("MONGODB_DB", "TelegramGiftsBot")


def get_configs_collection() -> AsyncIOMotorCollection:
    client = _get_client()
    db = client[get_db_name()]
    return db["configs"]


