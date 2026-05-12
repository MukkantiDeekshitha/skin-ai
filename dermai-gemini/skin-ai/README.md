# 🔬 DermAI — AI-Powered Skin Disease Detection

A Flask web application that uses **Claude AI (Vision + Text)** to detect skin diseases from uploaded images or described symptoms.

## ✨ Features

- 📸 **Image Scan** — Upload a skin photo for instant AI analysis
- 📝 **Symptom Checker** — Describe symptoms in natural language
- 💊 **Treatment Plans** — Medical treatments, home remedies & precautions
- 🔐 **User Auth** — Register, login, persistent sessions
- 📂 **History** — All analyses saved per user
- 📱 **Responsive** — Works on mobile, tablet & desktop

## 🛠️ Tech Stack

- **Backend**: Python 3.11 + Flask
- **Database**: SQLite (local) / PostgreSQL (production)
- **AI**: Anthropic Claude (claude-sonnet-4-20250514)
- **Auth**: Flask-Login + Werkzeug password hashing
- **Deploy**: Railway

---

## 🚀 Local Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd skin-ai
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables

Create a `.env` file (or export directly):

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
export SECRET_KEY=your-super-secret-key-here
```

### 5. Run the app

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## ☁️ Deploy to Railway

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial DermAI commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/dermai.git
git push -u origin main
```

### Step 2 — Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `dermai` repository
4. Railway auto-detects Python via Nixpacks ✅

### Step 3 — Add Environment Variables

In your Railway project → **Variables** tab, add:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-your-key-here` |
| `SECRET_KEY` | `any-long-random-string` |
| `PORT` | `5000` *(Railway sets this automatically)* |

### Step 4 — Deploy

Railway will automatically build and deploy. Your app will be live at:
`https://dermai-production.up.railway.app` (or your custom domain)

---

## 📁 Project Structure

```
skin-ai/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Procfile                # Railway start command
├── railway.toml            # Railway config
├── static/
│   ├── css/style.css       # All styles
│   ├── js/main.js          # Client JS
│   └── uploads/            # User uploaded images
└── templates/
    ├── base.html           # Base layout
    ├── index.html          # Landing page
    ├── login.html          # Login page
    ├── register.html       # Register page
    ├── dashboard.html      # User dashboard
    ├── analyze.html        # Image upload
    ├── symptoms.html       # Symptom checker
    ├── result.html         # Analysis result
    └── history.html        # Analysis history
```

---

## ⚠️ Medical Disclaimer

DermAI is for **informational purposes only**. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified dermatologist.

---

## 📄 License

MIT License — free to use, modify, and distribute.
