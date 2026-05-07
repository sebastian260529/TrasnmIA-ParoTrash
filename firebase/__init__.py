# Firebase connection
__all__ = ["firebase_db", "init_firebase", "get_collection"]

import os
import firebase_admin
from firebase_admin import credentials, firestore

# Get base directory (ChatBot folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "data", "serviceAccountKey.json")

# Global Firestore client
firebase_db = None

def init_firebase():
    """Initialize Firebase connection."""
    global firebase_db
    
    if firebase_admin._apps:
        # Already initialized
        firebase_db = firestore.client()
        return firebase_db
    
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(f"serviceAccountKey.json not found at {SERVICE_ACCOUNT_PATH}")
    
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    firebase_db = firestore.client()
    
    return firebase_db

def get_collection(name: str):
    """Get a Firestore collection."""
    global firebase_db
    if firebase_db is None:
        init_firebase()
    return firebase_db.collection(name)