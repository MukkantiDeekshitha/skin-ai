import os
import base64
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import google.generativeai as genai

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///skinai.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
login_manager.login_message_category = 'info'

# ─── Models ────────────────────────────────────────────────────────────────────

class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    analyses      = db.relationship('Analysis', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)


class Analysis(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type         = db.Column(db.String(20), nullable=False)   # 'image' or 'symptoms'
    input_data   = db.Column(db.Text)                         # symptoms text or image filename
    disease_name = db.Column(db.String(200))
    confidence   = db.Column(db.String(50))
    description  = db.Column(db.Text)
    treatments   = db.Column(db.Text)                         # JSON list
    remedies     = db.Column(db.Text)                         # JSON list
    precautions  = db.Column(db.Text)                         # JSON list
    when_to_see  = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def treatments_list(self):
        try: return json.loads(self.treatments)
        except: return []

    def remedies_list(self):
        try: return json.loads(self.remedies)
        except: return []

    def precautions_list(self):
        try: return json.loads(self.precautions)
        except: return []


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_gemini_model():
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=1024,
            temperature=0.3,
        )
    )


ANALYSIS_PROMPT = """You are DermAI, an expert dermatology AI assistant.
Analyze the provided input and return ONLY a valid JSON object (no markdown, no explanation outside JSON) with this exact structure:
{
  "disease_name": "Name of the most likely skin condition",
  "confidence": "High / Medium / Low",
  "description": "Clear 2-3 sentence description of this condition",
  "treatments": ["Treatment 1", "Treatment 2", "Treatment 3", "Treatment 4"],
  "remedies": ["Home remedy 1", "Home remedy 2", "Home remedy 3"],
  "precautions": ["Precaution 1", "Precaution 2", "Precaution 3"],
  "when_to_see_doctor": "Brief guidance on when professional consultation is needed",
  "disclaimer": "Standard medical disclaimer"
}
Always include a disclaimer that this is not a substitute for professional medical diagnosis."""


def parse_ai_response(text):
    """Extract JSON from Gemini's response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
    # Find JSON object boundaries
    start = text.find('{')
    end   = text.rfind('}') + 1
    if start != -1 and end > start:
        text = text[start:end]
    return json.loads(text)


def analyze_image_with_claude(image_path, media_type):
    model = get_gemini_model()
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    image_part = {
        "mime_type": media_type,
        "data": image_bytes
    }
    prompt = ANALYSIS_PROMPT + "\n\nAnalyze this skin image and identify any visible skin condition. Return ONLY the JSON response."
    response = model.generate_content([prompt, image_part])
    return parse_ai_response(response.text)


def analyze_symptoms_with_claude(symptoms_text):
    model = get_gemini_model()
    prompt = (
        ANALYSIS_PROMPT +
        f"\n\nBased on these skin symptoms described by the patient, identify the most likely skin condition:\n\n{symptoms_text}\n\nReturn ONLY the JSON response."
    )
    response = model.generate_content(prompt)
    return parse_ai_response(response.text)

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm]):
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Welcome to DermAI!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')
        remember   = bool(request.form.get('remember'))

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    recent = Analysis.query.filter_by(user_id=current_user.id)\
                           .order_by(Analysis.created_at.desc()).limit(5).all()
    total  = Analysis.query.filter_by(user_id=current_user.id).count()
    return render_template('dashboard.html', recent=recent, total=total)


@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    if request.method == 'POST':
        if 'image' not in request.files or request.files['image'].filename == '':
            flash('Please select an image to upload.', 'error')
            return redirect(request.url)

        file = request.files['image']
        if not allowed_file(file.filename):
            flash('Allowed formats: PNG, JPG, JPEG, WEBP.', 'error')
            return redirect(request.url)

        filename  = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        filename  = f"{current_user.id}_{timestamp}_{filename}"
        filepath  = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        ext = filename.rsplit('.', 1)[1].lower()
        media_type_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
        media_type = media_type_map.get(ext, 'image/jpeg')

        try:
            result = analyze_image_with_claude(filepath, media_type)
        except Exception as e:
            flash(f'Analysis failed: {str(e)}', 'error')
            return redirect(request.url)

        analysis = Analysis(
            user_id      = current_user.id,
            type         = 'image',
            input_data   = filename,
            disease_name = result.get('disease_name', 'Unknown'),
            confidence   = result.get('confidence', 'N/A'),
            description  = result.get('description', ''),
            treatments   = json.dumps(result.get('treatments', [])),
            remedies     = json.dumps(result.get('remedies', [])),
            precautions  = json.dumps(result.get('precautions', [])),
            when_to_see  = result.get('when_to_see_doctor', '')
        )
        db.session.add(analysis)
        db.session.commit()
        return redirect(url_for('result', analysis_id=analysis.id))

    return render_template('analyze.html')


@app.route('/symptoms', methods=['GET', 'POST'])
@login_required
def symptoms():
    if request.method == 'POST':
        symptoms_text = request.form.get('symptoms', '').strip()
        if not symptoms_text or len(symptoms_text) < 10:
            flash('Please describe your symptoms in more detail (at least 10 characters).', 'error')
            return redirect(request.url)

        try:
            result = analyze_symptoms_with_claude(symptoms_text)
        except Exception as e:
            flash(f'Analysis failed: {str(e)}', 'error')
            return redirect(request.url)

        analysis = Analysis(
            user_id      = current_user.id,
            type         = 'symptoms',
            input_data   = symptoms_text,
            disease_name = result.get('disease_name', 'Unknown'),
            confidence   = result.get('confidence', 'N/A'),
            description  = result.get('description', ''),
            treatments   = json.dumps(result.get('treatments', [])),
            remedies     = json.dumps(result.get('remedies', [])),
            precautions  = json.dumps(result.get('precautions', [])),
            when_to_see  = result.get('when_to_see_doctor', '')
        )
        db.session.add(analysis)
        db.session.commit()
        return redirect(url_for('result', analysis_id=analysis.id))

    return render_template('symptoms.html')


@app.route('/result/<int:analysis_id>')
@login_required
def result(analysis_id):
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    return render_template('result.html', analysis=analysis)


@app.route('/history')
@login_required
def history():
    page     = request.args.get('page', 1, type=int)
    analyses = Analysis.query.filter_by(user_id=current_user.id)\
                             .order_by(Analysis.created_at.desc())\
                             .paginate(page=page, per_page=10, error_out=False)
    return render_template('history.html', analyses=analyses)


@app.route('/history/delete/<int:analysis_id>', methods=['POST'])
@login_required
def delete_analysis(analysis_id):
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first_or_404()
    if analysis.type == 'image' and analysis.input_data:
        path = os.path.join(app.config['UPLOAD_FOLDER'], analysis.input_data)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(analysis)
    db.session.commit()
    flash('Record deleted.', 'success')
    return redirect(url_for('history'))


# ─── Init ──────────────────────────────────────────────────────────────────────

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"[DB] Table init skipped (already exists): {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
