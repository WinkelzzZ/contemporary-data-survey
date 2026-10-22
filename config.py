import os

class Config:
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
    DB_NAME = os.environ.get('DB_NAME', 'survey_system')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
