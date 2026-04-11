import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Render.com stores secrets as environment variables
# We store the entire Firebase service account JSON as one env variable
firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if firebase_json:
    service_account = json.loads(firebase_json)
    cred = credentials.Certificate(service_account)
else:
    # Local dev: use a local file
    cred = credentials.Certificate("serviceAccountKey.json")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
