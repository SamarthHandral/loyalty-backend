# Loyalty Card Backend — FastAPI

## Local Setup

### 1. Create virtual environment
```bash
cd loyalty-backend
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up Firebase
1. Go to https://console.firebase.google.com
2. Create a new project (free Spark plan)
3. Click "Firestore Database" → Create database → Start in test mode
4. Go to Project Settings → Service Accounts → Generate new private key
5. Download the JSON file
6. Either:
   - Rename it to `serviceAccountKey.json` and place it in this folder (local dev only)
   - OR paste the entire JSON content into `FIREBASE_SERVICE_ACCOUNT` in your `.env`

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in your values
```

### 5. Run locally
```bash
uvicorn main:app --reload
```
API is now running at: http://localhost:8000
Interactive docs at: http://localhost:8000/docs

---

## Deploy to Railway (Recommended)

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub (easiest)

2. **Deploy from GitHub**
   - Click "New Project" → "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your `loyalty-backend` repository

3. **Configure Environment**
   - Railway will auto-detect Python
   - Go to "Variables" tab and add:
     ```
     OWNER_TOKEN=your_secure_random_token_here
     OWNER_PASSWORD=your_secure_dashboard_password
     FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}
     ```
   - Generate secure token: `openssl rand -hex 32`

4. **Deploy**
   - Click "Deploy"
   - Railway will build and deploy automatically
   - Your API will be live at: `https://your-project.railway.app`

5. **Update CORS** (After deployment)
   - In `main.py`, update the `allow_origins` with your Railway URL:
   ```python
   allow_origins=["https://your-frontend.vercel.app", "https://your-project.railway.app"]
   ```

---

## Deploy to Render.com (Alternative)

1. Push this folder to a GitHub repository
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Fill in:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Under "Environment Variables", add:
   - `OWNER_TOKEN` → your secret token
   - `OWNER_PASSWORD` → your dashboard password
   - `FIREBASE_SERVICE_ACCOUNT` → paste entire contents of your serviceAccountKey.json
6. Click Deploy

Your API will be live at: `https://your-app-name.onrender.com`

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | None | Health check |
| GET | `/settings/public` | None | Shop name + reward info |
| POST | `/checkin` | None | GPS check + stamp visit |
| GET | `/customer/{phone}` | None | Customer card lookup |
| POST | `/owner/login` | None | Returns owner token |
| GET | `/dashboard` | Bearer token | All customers list |
| PUT | `/settings` | Bearer token | Update shop settings |

---

## Firestore Data Structure

```
firestore/
├── config/
│   └── settings          ← shop name, GPS coords, reward config
└── customers/
    └── {phone}/          ← one document per customer
        ├── name
        ├── phone
        ├── visits
        ├── last_visit    ← Unix timestamp ms
        ├── total_rewards
        └── visit_log/    ← sub-collection
            └── {auto}/
                ├── timestamp
                ├── lat
                ├── lng
                └── distance_meters
```
