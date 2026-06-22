import os
import sqlite3
import hashlib
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['DATABASE'] = os.path.join(app.root_path, 'health_diagnosis.db')

# ==================== DATABASE ====================

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, phone_no TEXT, location TEXT, date_of_birth TEXT, user_type TEXT DEFAULT "patient", created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS symptoms (symptom_id INTEGER PRIMARY KEY AUTOINCREMENT, symptom_name TEXT NOT NULL UNIQUE, symptom_category TEXT, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS diseases (disease_id INTEGER PRIMARY KEY AUTOINCREMENT, disease_name TEXT NOT NULL UNIQUE, description TEXT, severity_level TEXT, common_symptoms TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS disease_symptom_rules (rule_id INTEGER PRIMARY KEY AUTOINCREMENT, disease_id INTEGER NOT NULL, symptom_id INTEGER NOT NULL, confidence_weight REAL DEFAULT 1.0, FOREIGN KEY (disease_id) REFERENCES diseases(disease_id), FOREIGN KEY (symptom_id) REFERENCES symptoms(symptom_id))')
    db.execute('CREATE TABLE IF NOT EXISTS patient_symptom_input (input_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, session_id TEXT NOT NULL, symptom_ids TEXT NOT NULL, duration_days INTEGER, input_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id))')
    db.execute('CREATE TABLE IF NOT EXISTS diagnosis_results (diagnosis_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, input_id INTEGER NOT NULL, disease_id INTEGER NOT NULL, confidence_score REAL NOT NULL, diagnosis_method TEXT NOT NULL, diagnosis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (input_id) REFERENCES patient_symptom_input(input_id), FOREIGN KEY (disease_id) REFERENCES diseases(disease_id))')
    db.execute('CREATE TABLE IF NOT EXISTS recommendations (rec_id INTEGER PRIMARY KEY AUTOINCREMENT, diagnosis_id INTEGER NOT NULL, rec_type TEXT NOT NULL, rec_text TEXT NOT NULL, urgency_level TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_results(diagnosis_id))')
    db.execute('CREATE TABLE IF NOT EXISTS system_settings (setting_id INTEGER PRIMARY KEY AUTOINCREMENT, setting_name TEXT UNIQUE NOT NULL, setting_value TEXT NOT NULL, description TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.commit()
    seed_database()

def seed_database():
    db = get_db()
    cursor = db.execute('SELECT COUNT(*) as count FROM symptoms')
    if cursor.fetchone()['count'] > 0:
        return
    symptoms = [
        ('Fever', 'General', 'Elevated body temperature'),
        ('Chills', 'General', 'Feeling of coldness with shivering'),
        ('Sweating', 'General', 'Excessive perspiration'),
        ('Headache', 'General', 'Pain in the head or upper neck'),
        ('Fatigue', 'General', 'Extreme tiredness or exhaustion'),
        ('Nausea', 'Digestive', 'Feeling of sickness with inclination to vomit'),
        ('Vomiting', 'Digestive', 'Forceful expulsion of stomach contents'),
        ('Abdominal Pain', 'Digestive', 'Pain in the stomach area'),
        ('Diarrhea', 'Digestive', 'Loose, watery stools'),
        ('Cough', 'Respiratory', 'Sudden expulsion of air from lungs'),
        ('Sore Throat', 'Respiratory', 'Pain or irritation in the throat'),
        ('Runny Nose', 'Respiratory', 'Excess nasal discharge'),
        ('Difficulty Breathing', 'Respiratory', 'Shortness of breath or breathlessness'),
        ('Chest Pain', 'Respiratory', 'Pain or discomfort in the chest'),
        ('Body Ache', 'General', 'Generalized muscle or body pain'),
        ('Weakness', 'General', 'Lack of physical or mental strength'),
        ('Loss of Appetite', 'Digestive', 'Reduced desire to eat'),
        ('Joint Pain', 'General', 'Pain in joints'),
        ('Rash', 'Skin', 'Visible skin eruption or discoloration'),
        ('Dizziness', 'General', 'Feeling of lightheadedness or unsteadiness'),
    ]
    db.executemany('INSERT OR IGNORE INTO symptoms (symptom_name, symptom_category, description) VALUES (?, ?, ?)', symptoms)
    diseases = [
        ('Malaria', 'A mosquito-borne infectious disease causing fever and other symptoms', 'High', 'Fever, Chills, Sweating, Headache, Fatigue, Nausea, Body Ache'),
        ('Typhoid Fever', 'Bacterial infection causing high fever and gastrointestinal symptoms', 'High', 'Fever, Headache, Abdominal Pain, Weakness, Loss of Appetite, Diarrhea, Nausea'),
        ('Influenza', 'Viral respiratory infection commonly known as the flu', 'Moderate', 'Fever, Cough, Sore Throat, Runny Nose, Body Ache, Fatigue, Headache'),
        ('Pneumonia', 'Infection that inflames air sacs in one or both lungs', 'High', 'Cough, Difficulty Breathing, Chest Pain, Fever, Fatigue, Nausea'),
        ('Common Cold', 'Viral infection of the upper respiratory tract', 'Low', 'Runny Nose, Sore Throat, Cough, Mild Fever, Fatigue'),
        ('Gastroenteritis', 'Inflammation of the stomach and intestines', 'Moderate', 'Nausea, Vomiting, Diarrhea, Abdominal Pain, Fever, Weakness'),
        ('Dengue Fever', 'Mosquito-borne viral infection causing severe flu-like illness', 'High', 'Fever, Severe Headache, Joint Pain, Rash, Nausea, Weakness'),
        ('COVID-19', 'Respiratory illness caused by the SARS-CoV-2 virus', 'High', 'Fever, Cough, Difficulty Breathing, Fatigue, Loss of Appetite, Body Ache'),
    ]
    db.executemany('INSERT OR IGNORE INTO diseases (disease_name, description, severity_level, common_symptoms) VALUES (?, ?, ?, ?)', diseases)
    db.commit()
    symptom_map = {}
    cursor = db.execute('SELECT symptom_id, symptom_name FROM symptoms')
    for row in cursor.fetchall():
        symptom_map[row['symptom_name']] = row['symptom_id']
    disease_map = {}
    cursor = db.execute('SELECT disease_id, disease_name FROM diseases')
    for row in cursor.fetchall():
        disease_map[row['disease_name']] = row['disease_id']
    rules = [
        ('Malaria', ['Fever', 'Chills', 'Sweating', 'Headache', 'Fatigue'], 0.90),
        ('Malaria', ['Fever', 'Headache', 'Nausea', 'Body Ache'], 0.85),
        ('Typhoid Fever', ['Fever', 'Abdominal Pain', 'Nausea', 'Weakness', 'Loss of Appetite'], 0.85),
        ('Typhoid Fever', ['Fever', 'Headache', 'Diarrhea', 'Fatigue'], 0.80),
        ('Influenza', ['Fever', 'Cough', 'Sore Throat', 'Runny Nose', 'Body Ache'], 0.80),
        ('Influenza', ['Fever', 'Cough', 'Fatigue', 'Headache'], 0.75),
        ('Pneumonia', ['Cough', 'Difficulty Breathing', 'Chest Pain', 'Fever'], 0.88),
        ('Pneumonia', ['Cough', 'Fever', 'Fatigue', 'Nausea'], 0.82),
        ('Common Cold', ['Runny Nose', 'Sore Throat', 'Cough', 'Fever'], 0.85),
        ('Common Cold', ['Runny Nose', 'Sore Throat', 'Fatigue'], 0.75),
        ('Gastroenteritis', ['Nausea', 'Vomiting', 'Diarrhea', 'Abdominal Pain'], 0.88),
        ('Gastroenteritis', ['Abdominal Pain', 'Fever', 'Weakness', 'Nausea'], 0.80),
        ('Dengue Fever', ['Fever', 'Headache', 'Joint Pain', 'Rash'], 0.90),
        ('Dengue Fever', ['Fever', 'Nausea', 'Weakness', 'Rash'], 0.82),
        ('COVID-19', ['Fever', 'Cough', 'Difficulty Breathing', 'Fatigue'], 0.88),
        ('COVID-19', ['Fever', 'Cough', 'Loss of Appetite', 'Body Ache'], 0.85),
    ]
    rule_data = []
    for disease_name, symptom_names, weight in rules:
        disease_id = disease_map.get(disease_name)
        for symptom_name in symptom_names:
            symptom_id = symptom_map.get(symptom_name)
            if disease_id and symptom_id:
                rule_data.append((disease_id, symptom_id, weight))
    db.executemany('INSERT OR IGNORE INTO disease_symptom_rules (disease_id, symptom_id, confidence_weight) VALUES (?, ?, ?)', rule_data)
    settings = [
        ('fusion_weight_alpha', '0.6', 'Weight for ML component in hybrid fusion (0-1)'),
        ('min_confidence_threshold', '0.30', 'Minimum confidence score to return diagnosis'),
        ('max_diagnoses', '3', 'Maximum number of diagnoses to return'),
        ('system_name', 'Nigerian Health Diagnosis System', 'Name of the system'),
        ('system_version', '1.0', 'Current version of the system'),
    ]
    db.executemany('INSERT OR IGNORE INTO system_settings (setting_name, setting_value, description) VALUES (?, ?, ?)', settings)
    db.commit()
    print('Database seeded successfully!')

# ==================== AUTH HELPERS ====================

def hash_password(password):
    salt = secrets.token_hex(16)
    pwdhash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwdhash}"

def verify_password(stored_password, provided_password):
    try:
        salt, pwdhash = stored_password.split('$')
        test_hash = hashlib.sha256((provided_password + salt).encode()).hexdigest()
        return pwdhash == test_hash
    except:
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        if session.get('user_type') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== HYBRID AI ENGINE ====================

class HybridDiagnosisEngine:
    def __init__(self, db):
        self.db = db
        self.alpha = self._get_fusion_weight()
        self.diseases = self._load_diseases()
        self.symptoms = self._load_symptoms()
        self.rules = self._load_rules()
        self.ml_model = self._train_naive_bayes()

    def _get_fusion_weight(self):
        cursor = self.db.execute("SELECT setting_value FROM system_settings WHERE setting_name = 'fusion_weight_alpha'")
        row = cursor.fetchone()
        return float(row['setting_value']) if row else 0.6

    def _load_diseases(self):
        cursor = self.db.execute('SELECT * FROM diseases')
        return {row['disease_id']: dict(row) for row in cursor.fetchall()}

    def _load_symptoms(self):
        cursor = self.db.execute('SELECT * FROM symptoms')
        return {row['symptom_id']: dict(row) for row in cursor.fetchall()}

    def _load_rules(self):
        cursor = self.db.execute('SELECT r.*, d.disease_name, s.symptom_name FROM disease_symptom_rules r JOIN diseases d ON r.disease_id = d.disease_id JOIN symptoms s ON r.symptom_id = s.symptom_id')
        rules = {}
        for row in cursor.fetchall():
            disease_id = row['disease_id']
            if disease_id not in rules:
                rules[disease_id] = []
            rules[disease_id].append({'symptom_id': row['symptom_id'], 'symptom_name': row['symptom_name'], 'confidence_weight': row['confidence_weight']})
        return rules

    def _train_naive_bayes(self):
        disease_symptom_counts = {}
        disease_counts = {}
        total_cases = 0
        for disease_id, rule_list in self.rules.items():
            disease_counts[disease_id] = len(rule_list) * 10
            total_cases += disease_counts[disease_id]
            if disease_id not in disease_symptom_counts:
                disease_symptom_counts[disease_id] = {}
            for rule in rule_list:
                symptom_id = rule['symptom_id']
                if symptom_id not in disease_symptom_counts[disease_id]:
                    disease_symptom_counts[disease_id][symptom_id] = 0
                disease_symptom_counts[disease_id][symptom_id] += int(rule['confidence_weight'] * 10)
        priors = {}
        likelihoods = {}
        for disease_id in self.diseases:
            priors[disease_id] = disease_counts.get(disease_id, 1) / total_cases if total_cases > 0 else 1/len(self.diseases)
            likelihoods[disease_id] = {}
            total_symptoms_for_disease = sum(disease_symptom_counts.get(disease_id, {}).values())
            num_unique_symptoms = len(self.symptoms)
            for symptom_id in self.symptoms:
                count = disease_symptom_counts.get(disease_id, {}).get(symptom_id, 0)
                likelihoods[disease_id][symptom_id] = (count + 1) / (total_symptoms_for_disease + num_unique_symptoms)
        return {'priors': priors, 'likelihoods': likelihoods}

    def rule_based_diagnosis(self, symptom_ids):
        scores = {}
        for disease_id, rules in self.rules.items():
            rule_symptom_ids = {r['symptom_id'] for r in rules}
            matching_symptoms = set(symptom_ids) & rule_symptom_ids
            if matching_symptoms:
                total_weight = sum(r['confidence_weight'] for r in rules)
                matched_weight = sum(r['confidence_weight'] for r in rules if r['symptom_id'] in matching_symptoms)
                match_ratio = len(matching_symptoms) / len(rule_symptom_ids)
                weight_ratio = matched_weight / total_weight if total_weight > 0 else 0
                scores[disease_id] = (match_ratio * 0.5 + weight_ratio * 0.5)
            else:
                scores[disease_id] = 0.0
        max_score = max(scores.values()) if scores else 1
        if max_score > 0:
            scores = {k: v/max_score for k, v in scores.items()}
        return scores

    def naive_bayes_diagnosis(self, symptom_ids):
        scores = {}
        symptom_id_set = set(symptom_ids)
        for disease_id in self.diseases:
            prior = self.ml_model['priors'].get(disease_id, 1/len(self.diseases))
            likelihood = 1.0
            for symptom_id in symptom_id_set:
                likelihood *= self.ml_model['likelihoods'].get(disease_id, {}).get(symptom_id, 0.001)
            for symptom_id in self.symptoms:
                if symptom_id not in symptom_id_set:
                    likelihood *= (1 - self.ml_model['likelihoods'].get(disease_id, {}).get(symptom_id, 0.001))
            scores[disease_id] = prior * likelihood
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        return scores

    def hybrid_diagnosis(self, symptom_ids):
        rb_scores = self.rule_based_diagnosis(symptom_ids)
        ml_scores = self.naive_bayes_diagnosis(symptom_ids)
        hybrid_scores = {}
        for disease_id in self.diseases:
            rb_score = rb_scores.get(disease_id, 0)
            ml_score = ml_scores.get(disease_id, 0)
            hybrid_scores[disease_id] = self.alpha * ml_score + (1 - self.alpha) * rb_score
        sorted_scores = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores

    def get_recommendations(self, disease_id, confidence_score):
        disease = self.diseases.get(disease_id, {})
        disease_name = disease.get('disease_name', 'Unknown')
        severity = disease.get('severity_level', 'Moderate')
        recommendations = []
        if severity == 'Low':
            recommendations.append({'type': 'Self-Care', 'text': f'For {disease_name}: Rest adequately, stay hydrated, and monitor your symptoms. Over-the-counter medications may help relieve symptoms.', 'urgency': 'Low'})
        elif severity == 'Moderate':
            recommendations.append({'type': 'Self-Care', 'text': f'For {disease_name}: Rest in a comfortable environment, drink plenty of fluids, and take prescribed medications if available. Monitor symptoms closely.', 'urgency': 'Moderate'})
        else:
            recommendations.append({'type': 'Self-Care', 'text': f'For {disease_name}: Rest immediately, avoid strenuous activities, and maintain hydration. Do not self-medicate without professional guidance.', 'urgency': 'High'})
        if 'Malaria' in disease_name:
            recommendations.append({'type': 'Preventive', 'text': 'Use insecticide-treated mosquito nets, wear long-sleeved clothing, and eliminate standing water around your home. Consider prophylactic antimalarial medication if traveling to endemic areas.', 'urgency': 'Moderate'})
        elif 'Typhoid' in disease_name:
            recommendations.append({'type': 'Preventive', 'text': 'Practice good hand hygiene, drink only treated or boiled water, and ensure food is properly cooked. Avoid raw fruits and vegetables that cannot be peeled.', 'urgency': 'Moderate'})
        elif 'Influenza' in disease_name or 'Cold' in disease_name:
            recommendations.append({'type': 'Preventive', 'text': 'Practice respiratory hygiene by covering your mouth when coughing, wash hands frequently, avoid close contact with sick individuals, and consider annual flu vaccination.', 'urgency': 'Low'})
        elif 'Pneumonia' in disease_name:
            recommendations.append({'type': 'Preventive', 'text': 'Maintain good respiratory hygiene, avoid smoking and air pollutants, ensure proper ventilation, and consider pneumococcal vaccination for high-risk groups.', 'urgency': 'High'})
        elif 'COVID-19' in disease_name:
            recommendations.append({'type': 'Preventive', 'text': 'Isolate yourself from others, wear a mask if you must be around people, practice hand hygiene, and ensure good ventilation in your living space.', 'urgency': 'High'})
        else:
            recommendations.append({'type': 'Preventive', 'text': 'Maintain good personal hygiene, eat a balanced diet, exercise regularly, and ensure adequate sleep to boost your immune system.', 'urgency': 'Low'})
        if severity == 'High' or confidence_score > 0.80:
            recommendations.append({'type': 'Referral', 'text': f'URGENT: Based on the high probability of {disease_name}, please visit the nearest healthcare facility or hospital immediately for professional medical evaluation and treatment.', 'urgency': 'Critical'})
        elif severity == 'Moderate' or confidence_score > 0.60:
            recommendations.append({'type': 'Referral', 'text': f'IMPORTANT: Please consult a healthcare provider within 24-48 hours for {disease_name}. Early medical intervention can prevent complications.', 'urgency': 'High'})
        else:
            recommendations.append({'type': 'Referral', 'text': f'If symptoms persist or worsen after 2-3 days, please consult a healthcare provider for {disease_name}.', 'urgency': 'Moderate'})
        return recommendations

# ==================== ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone_no = request.form.get('phone_no', '').strip()
        location = request.form.get('location', '').strip()
        date_of_birth = request.form.get('date_of_birth', '')
        if not all([full_name, email, password]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('register'))
        db = get_db()
        cursor = db.execute('SELECT user_id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Email already registered. Please log in.', 'warning')
            return redirect(url_for('login'))
        password_hash = hash_password(password)
        db.execute('INSERT INTO users (full_name, email, password_hash, phone_no, location, date_of_birth, user_type) VALUES (?, ?, ?, ?, ?, ?, "patient")', (full_name, email, password_hash, phone_no, location, date_of_birth))
        db.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone_no = request.form.get('phone_no', '').strip()
        admin_code = request.form.get('admin_code', '')
        if not all([full_name, email, password, admin_code]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('admin_register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('admin_register'))
        if admin_code != 'ADMIN2024':
            flash('Invalid admin registration code.', 'danger')
            return redirect(url_for('admin_register'))
        db = get_db()
        cursor = db.execute('SELECT user_id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Email already registered.', 'warning')
            return redirect(url_for('login'))
        password_hash = hash_password(password)
        db.execute('INSERT INTO users (full_name, email, password_hash, phone_no, user_type) VALUES (?, ?, ?, ?, "admin")', (full_name, email, password_hash, phone_no))
        db.commit()
        flash('Admin registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('admin_register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not all([email, password]):
            flash('Please enter both email and password.', 'danger')
            return redirect(url_for('login'))
        db = get_db()
        cursor = db.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        if user and verify_password(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            session['user_type'] = user['user_type']
            session.permanent = True
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            if user['user_type'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('user_type') == 'admin':
        return redirect(url_for('admin_dashboard'))
    db = get_db()
    cursor = db.execute('SELECT dr.*, d.disease_name, d.severity_level FROM diagnosis_results dr JOIN diseases d ON dr.disease_id = d.disease_id WHERE dr.user_id = ? ORDER BY dr.diagnosis_date DESC LIMIT 5', (session['user_id'],))
    recent_diagnoses = cursor.fetchall()
    cursor = db.execute('SELECT COUNT(*) as count FROM diagnosis_results WHERE user_id = ?', (session['user_id'],))
    diagnosis_count = cursor.fetchone()['count']
    cursor = db.execute('SELECT * FROM users WHERE user_id = ?', (session['user_id'],))
    user = cursor.fetchone()
    return render_template('user/dashboard.html', recent_diagnoses=recent_diagnoses, diagnosis_count=diagnosis_count, user=user)

@app.route('/symptom-checker', methods=['GET', 'POST'])
@login_required
def symptom_checker():
    if session.get('user_type') == 'admin':
        return redirect(url_for('admin_dashboard'))
    db = get_db()
    cursor = db.execute('SELECT * FROM symptoms ORDER BY symptom_category, symptom_name')
    symptoms = cursor.fetchall()
    symptoms_by_category = {}
    for symptom in symptoms:
        category = symptom['symptom_category'] or 'General'
        if category not in symptoms_by_category:
            symptoms_by_category[category] = []
        symptoms_by_category[category].append(symptom)
    if request.method == 'POST':
        selected_symptoms = request.form.getlist('symptoms')
        duration_days = request.form.get('duration_days', 1)
        if not selected_symptoms:
            flash('Please select at least one symptom.', 'warning')
            return redirect(url_for('symptom_checker'))
        symptom_ids = [int(s) for s in selected_symptoms]
        session_id = secrets.token_hex(16)
        db.execute('INSERT INTO patient_symptom_input (user_id, session_id, symptom_ids, duration_days) VALUES (?, ?, ?, ?)', (session['user_id'], session_id, ','.join(map(str, symptom_ids)), duration_days))
        db.commit()
        input_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        engine = HybridDiagnosisEngine(db)
        diagnoses = engine.hybrid_diagnosis(symptom_ids)
        cursor = db.execute("SELECT setting_value FROM system_settings WHERE setting_name = 'min_confidence_threshold'")
        row = cursor.fetchone()
        min_confidence = float(row['setting_value']) if row else 0.30
        valid_diagnoses = [(d_id, score) for d_id, score in diagnoses if score >= min_confidence]
        if not valid_diagnoses:
            valid_diagnoses = diagnoses[:1]
        saved_diagnoses = []
        for disease_id, confidence in valid_diagnoses[:3]:
            db.execute('INSERT INTO diagnosis_results (user_id, input_id, disease_id, confidence_score, diagnosis_method) VALUES (?, ?, ?, ?, "Hybrid")', (session['user_id'], input_id, disease_id, round(confidence * 100, 2)))
            db.commit()
            diagnosis_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            recommendations = engine.get_recommendations(disease_id, confidence)
            for rec in recommendations:
                db.execute('INSERT INTO recommendations (diagnosis_id, rec_type, rec_text, urgency_level) VALUES (?, ?, ?, ?)', (diagnosis_id, rec['type'], rec['text'], rec['urgency']))
            db.commit()
            saved_diagnoses.append({'diagnosis_id': diagnosis_id, 'disease': engine.diseases.get(disease_id, {}), 'confidence': round(confidence * 100, 2), 'recommendations': recommendations})
        return render_template('user/diagnosis_result.html', diagnoses=saved_diagnoses, symptom_ids=symptom_ids, symptoms_list=symptoms, duration_days=duration_days)
    return render_template('user/symptom_checker.html', symptoms_by_category=symptoms_by_category)

@app.route('/history')
@login_required
def history():
    if session.get('user_type') == 'admin':
        return redirect(url_for('admin_dashboard'))
    db = get_db()
    cursor = db.execute('SELECT dr.*, d.disease_name, d.severity_level, d.description as disease_description, psi.duration_days, psi.input_date as symptom_date FROM diagnosis_results dr JOIN diseases d ON dr.disease_id = d.disease_id JOIN patient_symptom_input psi ON dr.input_id = psi.input_id WHERE dr.user_id = ? ORDER BY dr.diagnosis_date DESC', (session['user_id'],))
    diagnoses = cursor.fetchall()
    diagnosis_data = []
    for diag in diagnoses:
        cursor = db.execute("SELECT * FROM recommendations WHERE diagnosis_id = ? ORDER BY CASE urgency_level WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Moderate' THEN 3 ELSE 4 END", (diag['diagnosis_id'],))
        recs = cursor.fetchall()
        diagnosis_data.append({'diagnosis': diag, 'recommendations': recs})
    return render_template('user/history.html', diagnosis_data=diagnosis_data)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if session.get('user_type') == 'admin':
        return redirect(url_for('admin_dashboard'))
    db = get_db()
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone_no = request.form.get('phone_no', '').strip()
        location = request.form.get('location', '').strip()
        date_of_birth = request.form.get('date_of_birth', '')
        db.execute('UPDATE users SET full_name = ?, phone_no = ?, location = ?, date_of_birth = ? WHERE user_id = ?', (full_name, phone_no, location, date_of_birth, session['user_id']))
        db.commit()
        session['user_name'] = full_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    cursor = db.execute('SELECT * FROM users WHERE user_id = ?', (session['user_id'],))
    user = cursor.fetchone()
    return render_template('user/profile.html', user=user)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.execute("SELECT COUNT(*) as count FROM users WHERE user_type = 'patient'")
    total_patients = cursor.fetchone()['count']
    cursor = db.execute('SELECT COUNT(*) as count FROM diagnosis_results')
    total_diagnoses = cursor.fetchone()['count']
    cursor = db.execute('SELECT COUNT(*) as count FROM diseases')
    total_diseases = cursor.fetchone()['count']
    cursor = db.execute('SELECT COUNT(*) as count FROM symptoms')
    total_symptoms = cursor.fetchone()['count']
    cursor = db.execute('SELECT dr.*, u.full_name, d.disease_name FROM diagnosis_results dr JOIN users u ON dr.user_id = u.user_id JOIN diseases d ON dr.disease_id = d.disease_id ORDER BY dr.diagnosis_date DESC LIMIT 10')
    recent_diagnoses = cursor.fetchall()
    cursor = db.execute('SELECT d.disease_name, COUNT(*) as count FROM diagnosis_results dr JOIN diseases d ON dr.disease_id = d.disease_id GROUP BY dr.disease_id ORDER BY count DESC')
    disease_distribution = cursor.fetchall()
    return render_template('admin/dashboard.html', total_patients=total_patients, total_diagnoses=total_diagnoses, total_diseases=total_diseases, total_symptoms=total_symptoms, recent_diagnoses=recent_diagnoses, disease_distribution=disease_distribution)

@app.route('/admin/diseases')
@admin_required
def admin_diseases():
    db = get_db()
    cursor = db.execute('SELECT * FROM diseases ORDER BY disease_name')
    diseases = cursor.fetchall()
    return render_template('admin/diseases.html', diseases=diseases)

@app.route('/admin/diseases/add', methods=['POST'])
@admin_required
def add_disease():
    db = get_db()
    disease_name = request.form.get('disease_name', '').strip()
    description = request.form.get('description', '').strip()
    severity_level = request.form.get('severity_level', 'Moderate')
    common_symptoms = request.form.get('common_symptoms', '').strip()
    if not disease_name:
        flash('Disease name is required.', 'danger')
        return redirect(url_for('admin_diseases'))
    try:
        db.execute('INSERT INTO diseases (disease_name, description, severity_level, common_symptoms) VALUES (?, ?, ?, ?)', (disease_name, description, severity_level, common_symptoms))
        db.commit()
        flash('Disease added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Disease already exists.', 'warning')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/diseases/edit/<int:disease_id>', methods=['POST'])
@admin_required
def edit_disease(disease_id):
    db = get_db()
    disease_name = request.form.get('disease_name', '').strip()
    description = request.form.get('description', '').strip()
    severity_level = request.form.get('severity_level', 'Moderate')
    common_symptoms = request.form.get('common_symptoms', '').strip()
    db.execute('UPDATE diseases SET disease_name = ?, description = ?, severity_level = ?, common_symptoms = ? WHERE disease_id = ?', (disease_name, description, severity_level, common_symptoms, disease_id))
    db.commit()
    flash('Disease updated successfully!', 'success')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/diseases/delete/<int:disease_id>')
@admin_required
def delete_disease(disease_id):
    db = get_db()
    cursor = db.execute('SELECT COUNT(*) as count FROM diagnosis_results WHERE disease_id = ?', (disease_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete disease with existing diagnoses.', 'warning')
        return redirect(url_for('admin_diseases'))
    db.execute('DELETE FROM disease_symptom_rules WHERE disease_id = ?', (disease_id,))
    db.execute('DELETE FROM diseases WHERE disease_id = ?', (disease_id,))
    db.commit()
    flash('Disease deleted successfully!', 'success')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/symptoms')
@admin_required
def admin_symptoms():
    db = get_db()
    cursor = db.execute('SELECT * FROM symptoms ORDER BY symptom_category, symptom_name')
    symptoms = cursor.fetchall()
    return render_template('admin/symptoms.html', symptoms=symptoms)

@app.route('/admin/symptoms/add', methods=['POST'])
@admin_required
def add_symptom():
    db = get_db()
    symptom_name = request.form.get('symptom_name', '').strip()
    symptom_category = request.form.get('symptom_category', 'General')
    description = request.form.get('description', '').strip()
    if not symptom_name:
        flash('Symptom name is required.', 'danger')
        return redirect(url_for('admin_symptoms'))
    try:
        db.execute('INSERT INTO symptoms (symptom_name, symptom_category, description) VALUES (?, ?, ?)', (symptom_name, symptom_category, description))
        db.commit()
        flash('Symptom added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Symptom already exists.', 'warning')
    return redirect(url_for('admin_symptoms'))

@app.route('/admin/symptoms/edit/<int:symptom_id>', methods=['POST'])
@admin_required
def edit_symptom(symptom_id):
    db = get_db()
    symptom_name = request.form.get('symptom_name', '').strip()
    symptom_category = request.form.get('symptom_category', 'General')
    description = request.form.get('description', '').strip()
    db.execute('UPDATE symptoms SET symptom_name = ?, symptom_category = ?, description = ? WHERE symptom_id = ?', (symptom_name, symptom_category, description, symptom_id))
    db.commit()
    flash('Symptom updated successfully!', 'success')
    return redirect(url_for('admin_symptoms'))

@app.route('/admin/symptoms/delete/<int:symptom_id>')
@admin_required
def delete_symptom(symptom_id):
    db = get_db()
    cursor = db.execute('SELECT COUNT(*) as count FROM disease_symptom_rules WHERE symptom_id = ?', (symptom_id,))
    if cursor.fetchone()['count'] > 0:
        flash('Cannot delete symptom with existing rules.', 'warning')
        return redirect(url_for('admin_symptoms'))
    db.execute('DELETE FROM symptoms WHERE symptom_id = ?', (symptom_id,))
    db.commit()
    flash('Symptom deleted successfully!', 'success')
    return redirect(url_for('admin_symptoms'))

@app.route('/admin/rules')
@admin_required
def admin_rules():
    db = get_db()
    cursor = db.execute('SELECT r.*, d.disease_name, s.symptom_name FROM disease_symptom_rules r JOIN diseases d ON r.disease_id = d.disease_id JOIN symptoms s ON r.symptom_id = s.symptom_id ORDER BY d.disease_name, s.symptom_name')
    rules = cursor.fetchall()
    cursor = db.execute('SELECT * FROM diseases ORDER BY disease_name')
    diseases = cursor.fetchall()
    cursor = db.execute('SELECT * FROM symptoms ORDER BY symptom_name')
    symptoms = cursor.fetchall()
    return render_template('admin/rules.html', rules=rules, diseases=diseases, symptoms=symptoms)

@app.route('/admin/rules/add', methods=['POST'])
@admin_required
def add_rule():
    db = get_db()
    disease_id = request.form.get('disease_id')
    symptom_id = request.form.get('symptom_id')
    confidence_weight = request.form.get('confidence_weight', 1.0)
    if not disease_id or not symptom_id:
        flash('Both disease and symptom are required.', 'danger')
        return redirect(url_for('admin_rules'))
    try:
        db.execute('INSERT INTO disease_symptom_rules (disease_id, symptom_id, confidence_weight) VALUES (?, ?, ?)', (disease_id, symptom_id, confidence_weight))
        db.commit()
        flash('Rule added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Rule already exists.', 'warning')
    return redirect(url_for('admin_rules'))

@app.route('/admin/rules/delete/<int:rule_id>')
@admin_required
def delete_rule(rule_id):
    db = get_db()
    db.execute('DELETE FROM disease_symptom_rules WHERE rule_id = ?', (rule_id,))
    db.commit()
    flash('Rule deleted successfully!', 'success')
    return redirect(url_for('admin_rules'))

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    cursor = db.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = cursor.fetchall()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('Cannot delete your own account.', 'warning')
        return redirect(url_for('admin_users'))
    db = get_db()
    db.execute('DELETE FROM recommendations WHERE diagnosis_id IN (SELECT diagnosis_id FROM diagnosis_results WHERE user_id = ?)', (user_id,))
    db.execute('DELETE FROM diagnosis_results WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM patient_symptom_input WHERE user_id = ?', (user_id,))
    db.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    db.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        fusion_weight = request.form.get('fusion_weight_alpha', '0.6')
        min_confidence = request.form.get('min_confidence_threshold', '0.30')
        max_diagnoses = request.form.get('max_diagnoses', '3')
        system_name = request.form.get('system_name', 'Nigerian Health Diagnosis System')
        db.execute("UPDATE system_settings SET setting_value = ? WHERE setting_name = 'fusion_weight_alpha'", (fusion_weight,))
        db.execute("UPDATE system_settings SET setting_value = ? WHERE setting_name = 'min_confidence_threshold'", (min_confidence,))
        db.execute("UPDATE system_settings SET setting_value = ? WHERE setting_name = 'max_diagnoses'", (max_diagnoses,))
        db.execute("UPDATE system_settings SET setting_value = ? WHERE setting_name = 'system_name'", (system_name,))
        db.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_settings'))
    cursor = db.execute('SELECT * FROM system_settings')
    settings = {row['setting_name']: row for row in cursor.fetchall()}
    return render_template('admin/settings.html', settings=settings)

@app.route('/admin/reports')
@admin_required
def admin_reports():
    db = get_db()
    cursor = db.execute("SELECT strftime('%Y-%m', diagnosis_date) as month, COUNT(*) as count FROM diagnosis_results GROUP BY month ORDER BY month DESC LIMIT 12")
    monthly_stats = cursor.fetchall()
    cursor = db.execute('SELECT d.disease_name, COUNT(*) as count, AVG(dr.confidence_score) as avg_confidence FROM diagnosis_results dr JOIN diseases d ON dr.disease_id = d.disease_id GROUP BY dr.disease_id ORDER BY count DESC')
    top_diseases = cursor.fetchall()
    cursor = db.execute("SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count FROM users WHERE user_type = 'patient' GROUP BY month ORDER BY month DESC LIMIT 12")
    user_growth = cursor.fetchall()
    return render_template('admin/reports.html', monthly_stats=monthly_stats, top_diseases=top_diseases, user_growth=user_growth)

@app.route('/api/symptoms')
def api_symptoms():
    db = get_db()
    cursor = db.execute('SELECT * FROM symptoms ORDER BY symptom_name')
    symptoms = [dict(row) for row in cursor.fetchall()]
    return jsonify(symptoms)

@app.route('/api/diseases')
def api_diseases():
    db = get_db()
    cursor = db.execute('SELECT * FROM diseases ORDER BY disease_name')
    diseases = [dict(row) for row in cursor.fetchall()]
    return jsonify(diseases)

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)