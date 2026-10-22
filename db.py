from pymongo import MongoClient
from config import Config

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(Config.MONGO_URI)
        _db = _client[Config.DB_NAME]
    return _db


def init_db():
    db = get_db()
    db.users.create_index('username', unique=True)
    db.surveys.create_index('survey_key', unique=True)
    db.surveys.create_index('creator_id')
    db.questions.create_index([('survey_id', 1), ('order', 1)], unique=True)
    db.responses.create_index('survey_id')
