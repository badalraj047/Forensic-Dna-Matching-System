from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime
from pathlib import Path
import secrets
import random
import re
import io

app = Flask(__name__)

# ===============================
# Security / session configuration
# ===============================
def _load_or_create_secret_key() -> str:
    """Load SECRET_KEY from env, else from secret_key.txt, else generate one."""
    env_key = os.environ.get('SECRET_KEY', '').strip()
    if len(env_key) >= 32:
        return env_key

    key_file = Path('secret_key.txt')
    try:
        if key_file.exists():
            file_key = key_file.read_text(encoding='utf-8').strip()
            if len(file_key) >= 32:
                return file_key

        generated = secrets.token_hex(32)
        key_file.write_text(generated, encoding='utf-8')
        return generated
    except Exception:
        # Last-resort fallback (non-persistent)
        return secrets.token_hex(32)


app.secret_key = _load_or_create_secret_key()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'


# ===============================
# In-memory storage with persistence
# ===============================
DATABASE = {
    'profiles': [],
    'encrypted_profiles': [],
    'match_results': [],
    'notifications': [],
    'users': []
}

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = os.environ.get('DATABASE_FILE', str(BASE_DIR / 'profiles_database_realistic_10000.json'))
USERS_FILE = os.environ.get('USERS_FILE', str(BASE_DIR / 'users_database.json'))


# CODIS constants used across routes
CODIS_LOCI = [
    'CSF1PO', 'D3S1358', 'D5S818', 'D7S820', 'D8S1179',
    'D13S317', 'D16S539', 'D18S51', 'D21S11', 'FGA',
    'TH01', 'TPOX', 'vWA', 'D1S1656', 'D2S441',
    'D2S1338', 'D10S1248', 'D12S391', 'D19S433', 'D22S1045'
]

ALLELE_RANGES = {
    'CSF1PO': (6, 16), 'D3S1358': (12, 20), 'D5S818': (7, 16),
    'D7S820': (6, 15), 'D8S1179': (8, 19), 'D13S317': (8, 16),
    'D16S539': (5, 16), 'D18S51': (9, 27), 'D21S11': (24, 38),
    'FGA': (17, 30), 'TH01': (4, 11), 'TPOX': (6, 13),
    'vWA': (11, 21), 'D1S1656': (9, 20), 'D2S441': (8, 17),
    'D2S1338': (15, 28), 'D10S1248': (8, 19), 'D12S391': (15, 26),
    'D19S433': (9, 17), 'D22S1045': (8, 19)
}


# ===============================
# Persistence helpers
# ===============================
def load_users_from_file() -> bool:
    """Load users from persistent JSON file."""
    global DATABASE
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            DATABASE['users'] = data.get('users', [])
            print(f"✓ Loaded {len(DATABASE['users'])} users from {USERS_FILE}")
            return True
        except Exception as e:
            print(f"⚠ Error loading users: {e}")
            return False
    return False


def save_users_to_file() -> bool:
    """Persist users to JSON file."""
    try:
        data = {
            'version': '1.1',
            'updated_at': datetime.now().isoformat(),
            'total_users': len(DATABASE['users']),
            'users': DATABASE['users']
        }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠ Error saving users: {e}")
        return False


def load_database_from_file() -> bool:
    """Load profiles from persistent JSON file."""
    global DATABASE
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            DATABASE['profiles'] = data.get('profiles', [])
            print(f"✓ Loaded {len(DATABASE['profiles'])} profiles from {DATABASE_FILE}")
            return True
        except Exception as e:
            print(f"⚠ Error loading database: {e}")
            return False
    return False


def save_database_to_file() -> bool:
    """Persist profiles to JSON file."""
    try:
        data = {
            'version': '2.1',
            'updated_at': datetime.now().isoformat(),
            'total_profiles': len(DATABASE['profiles']),
            'codis_loci': CODIS_LOCI,
            'profiles': DATABASE['profiles']
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠ Error saving database: {e}")
        return False


# ===============================
# Validation helpers
# ===============================
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def normalize_markers(markers: dict, require_all_loci: bool = False) -> dict:
    """
    Normalize markers -> {locus: [int, int]}
    - requires list of length 2 for each provided locus
    - if require_all_loci=True, all CODIS loci must be present
    """
    if not isinstance(markers, dict) or not markers:
        raise ValueError("Markers must be a non-empty object")

    normalized = {}

    for locus, alleles in markers.items():
        if not isinstance(alleles, list) or len(alleles) != 2:
            raise ValueError(f"Locus {locus}: each marker must have exactly 2 alleles")
        try:
            a1, a2 = int(alleles[0]), int(alleles[1])
        except Exception as ex:
            raise ValueError(f"Locus {locus}: alleles must be integers") from ex
        normalized[locus] = sorted([a1, a2])

    if require_all_loci:
        missing = [l for l in CODIS_LOCI if l not in normalized]
        if missing:
            raise ValueError(f"Missing required CODIS loci: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

    return normalized


def normalize_profile(profile_data: dict, require_all_loci: bool = False) -> dict:
    if not isinstance(profile_data, dict):
        raise ValueError("Profile must be a JSON object")

    profile_id = str(profile_data.get('id', '')).strip()
    if not profile_id:
        raise ValueError("Profile id is required")

    markers = normalize_markers(profile_data.get('markers'), require_all_loci=require_all_loci)

    normalized = dict(profile_data)
    normalized['id'] = profile_id
    normalized['markers'] = markers
    normalized['region'] = str(profile_data.get('region', 'USA')).strip() or 'USA'
    normalized['timestamp'] = profile_data.get('timestamp', datetime.now().isoformat())
    normalized['type'] = profile_data.get('type', 'SYNTHETIC')
    return normalized


# ===============================
# User auth helpers
# ===============================
def find_user_by_email(email: str):
    for user in DATABASE['users']:
        if user['email'].lower() == email.lower():
            return user
    return None


def register_user(email: str, password: str, username: str):
    if find_user_by_email(email):
        return {'success': False, 'error': 'Email already registered'}

    user = {
        'id': len(DATABASE['users']) + 1,
        'email': email,
        'username': username,
        'password': generate_password_hash(password),
        'created_at': datetime.now().isoformat(),
        'profiles_count': 0
    }
    DATABASE['users'].append(user)
    return {'success': True, 'message': 'Registration successful! Please login.'}


def verify_login(email: str, password: str):
    user = find_user_by_email(email)
    if user and check_password_hash(user['password'], password):
        return {'success': True, 'user': user}
    return {'success': False, 'error': 'Invalid email or password'}


# ===============================
# Crypto + similarity
# ===============================
class DNAEncryption:
    def __init__(self):
        self.key = os.environ.get("DNA_ENCRYPTION_KEY", "forensic_key_2025")

    def encrypt_profile(self, profile: dict):
        import hashlib

        encrypted = {
            'id': profile['id'],
            'encrypted_markers': {},
            'is_encrypted': True,
            'timestamp': datetime.now().isoformat(),
            'region': profile.get('region', 'USA')
        }

        for locus, alleles in profile['markers'].items():
            encrypted['encrypted_markers'][locus] = [
                hashlib.sha256(f"{self.key}:{locus}:{a}".encode()).hexdigest()
                for a in alleles
            ]

        return encrypted

    def compute_similarity_encrypted(self, profile1_enc: dict, profile2_enc: dict) -> float:
        """
        Deterministic hash-comparison score.
        NOTE: This is hash-based secure matching demo, not true homomorphic encryption.
        """
        total_alleles = 0
        shared_alleles = 0

        for locus, alleles1 in profile1_enc.get('encrypted_markers', {}).items():
            alleles2 = profile2_enc.get('encrypted_markers', {}).get(locus)
            if not alleles2:
                continue

            set1 = set(alleles1)
            set2 = set(alleles2)
            shared = len(set1.intersection(set2))

            shared_alleles += shared
            total_alleles += len(set1) + len(set2)

        if total_alleles == 0:
            return 0.0
        return round((2 * shared_alleles) / total_alleles, 4)


crypto = DNAEncryption()


def calculate_tanabe_score(profile1: dict, profile2: dict) -> float:
    shared_alleles = 0
    total_alleles = 0

    for locus in profile1.get('markers', {}):
        if locus in profile2.get('markers', {}):
            alleles1 = profile1['markers'][locus]
            alleles2 = profile2['markers'][locus]

            if not isinstance(alleles1, list):
                alleles1 = list(alleles1)
            if not isinstance(alleles2, list):
                alleles2 = list(alleles2)

            set1 = set(alleles1)
            set2 = set(alleles2)
            shared = len(set1.intersection(set2))

            shared_alleles += shared
            total_alleles += len(set1) + len(set2)

    if total_alleles == 0:
        return 0.0
    return round((2 * shared_alleles) / total_alleles, 4)


def classify_score(score: float, threshold: float) -> str:
    if score >= 0.95:
        return 'DEFINITE MATCH'
    if score >= threshold:
        return 'PROBABLE MATCH'
    if score >= 0.50:
        return 'PARTIAL MATCH'
    return 'NO MATCH'


def rebuild_encrypted_profiles() -> int:
    """Rebuild encrypted profile list from plaintext profiles."""
    encrypted_profiles = []
    for profile in DATABASE['profiles']:
        try:
            if 'id' in profile and 'markers' in profile:
                encrypted_profiles.append(crypto.encrypt_profile(profile))
        except Exception:
            continue
    DATABASE['encrypted_profiles'] = encrypted_profiles
    return len(encrypted_profiles)


# ===============================
# Notification helper
# ===============================
def add_notification(title: str, message: str):
    notification = {
        'id': len(DATABASE['notifications']) + 1,
        'title': title,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    DATABASE['notifications'].append(notification)
    if len(DATABASE['notifications']) > 50:
        DATABASE['notifications'] = DATABASE['notifications'][-50:]


# ===============================
# Startup loading
# ===============================
load_users_from_file()
load_database_from_file()
rebuild_encrypted_profiles()


# ===============================
# Routes: auth + pages
# ===============================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    theme = session.get('theme', 'dark')
    stats = {
        'total_profiles': len(DATABASE['profiles']),
        'encrypted_profiles': len(DATABASE['encrypted_profiles']),
        'total_matches': len(DATABASE['match_results'])
    }
    return render_template('index.html', stats=stats, theme=theme)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            email = str(data.get('email', '')).strip()
            password = str(data.get('password', '')).strip()
            username = str(data.get('username', '')).strip()
            confirm_password = str(data.get('confirm_password', '')).strip()

            if not email or not password or not username:
                return jsonify({'success': False, 'error': 'All fields required'}), 400
            if not is_valid_email(email):
                return jsonify({'success': False, 'error': 'Please enter a valid email address'}), 400
            if len(password) < 6:
                return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
            if password != confirm_password:
                return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

            result = register_user(email, password, username)
            if result['success']:
                save_users_to_file()
                return jsonify(result), 201
            return jsonify(result), 409
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            email = str(data.get('email', '')).strip()
            password = str(data.get('password', '')).strip()

            if not email or not password:
                return jsonify({'success': False, 'error': 'Email and password required'}), 400

            result = verify_login(email, password)
            if result['success']:
                user = result['user']
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['username'] = user['username']
                session['theme'] = 'dark'
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'redirect': '/'
                }), 200

            return jsonify(result), 401
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/profile')
def profile_redirect():
    # Placeholder route to avoid 404 from navbar profile link
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('index'))


@app.route('/crime-scene')
def crime_scene_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = session.get('theme', 'dark')
    return render_template('crime-scene.html', theme=theme)


@app.route('/api/user', methods=['GET'])
def get_user_info():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'profiles_count': user.get('profiles_count', 0)
        }
    })


@app.route('/toggle-theme')
def toggle_theme():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    current = session.get('theme', 'dark')
    session['theme'] = 'dark' if current == 'light' else 'light'
    return jsonify({'theme': session['theme']})


@app.route('/generate', methods=['GET', 'POST'])
def generate_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            try:
                count = int(request.form.get('count', 1))
            except Exception:
                count = 1

            if count < 1 or count > 500:
                return jsonify({'success': False, 'error': 'Count must be between 1 and 500'}), 400

            region = str(request.form.get('region', 'USA')).strip() or 'USA'

            profiles_generated = []
            start_count = len(DATABASE['profiles'])

            for i in range(count):
                profile_id = f"{region}_{start_count + i + 1:06d}"
                profile = {
                    'id': profile_id,
                    'markers': {},
                    'timestamp': datetime.now().isoformat(),
                    'type': 'SYNTHETIC',
                    'region': region
                }

                for locus in CODIS_LOCI:
                    min_val, max_val = ALLELE_RANGES[locus]
                    allele1 = random.randint(min_val, max_val)
                    allele2 = random.randint(min_val, max_val)
                    profile['markers'][locus] = sorted([int(allele1), int(allele2)])

                DATABASE['profiles'].append(profile)
                DATABASE['encrypted_profiles'].append(crypto.encrypt_profile(profile))
                profiles_generated.append(profile_id)

            user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
            if user:
                user['profiles_count'] = int(user.get('profiles_count', 0)) + count
                save_users_to_file()

            save_database_to_file()
            add_notification('✨ Profiles Generated', f'Generated {count} profile(s) from {region}')

            return jsonify({
                'success': True,
                'message': f'Generated {count} profile(s) from {region}',
                'profile_ids': profiles_generated
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    theme = session.get('theme', 'dark')
    return render_template('generate.html', theme=theme)


@app.route('/upload', methods=['GET', 'POST'])
def upload_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            profile_data = request.get_json(silent=True) or {}
            if 'id' not in profile_data or 'markers' not in profile_data:
                return jsonify({'success': False, 'error': 'Invalid profile format'}), 400

            for locus in profile_data['markers']:
                alleles = profile_data['markers'][locus]
                if not isinstance(alleles, list) or len(alleles) != 2:
                    return jsonify({'success': False, 'error': 'Each marker must have 2 alleles'}), 400
                profile_data['markers'][locus] = [int(a) for a in alleles]

            if 'region' not in profile_data or not profile_data['region']:
                profile_data['region'] = 'USA'

            store_in_database = bool(profile_data.get('store_in_database', False))
            profile_data.pop('store_in_database', None)

            session['last_uploaded_profile'] = profile_data

            if store_in_database:
                if any(p.get('id') == profile_data['id'] for p in DATABASE['profiles']):
                    return jsonify({'success': False, 'error': 'Profile ID already exists in database'}), 409

                DATABASE['profiles'].append(profile_data)
                encrypted = crypto.encrypt_profile(profile_data)
                DATABASE['encrypted_profiles'].append(encrypted)
                save_database_to_file()
                add_notification('📤 Profile Uploaded', f'Profile {profile_data["id"]} uploaded and stored in database')
                message = 'Profile uploaded, encrypted, and stored in database'
            else:
                add_notification('🧪 Query Sample Uploaded', f'Profile {profile_data["id"]} uploaded for matching (not stored in database)')
                message = 'Profile uploaded for matching only (not added to dataset)'

            return jsonify({
                'success': True,
                'message': message,
                'profile_id': profile_data['id'],
                'stored_in_database': store_in_database
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    theme = session.get('theme', 'dark')
    return render_template('upload.html', theme=theme)


@app.route('/match', methods=['GET', 'POST'])
def match_profiles():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            query_id = request.form.get('query_id')
            threshold = float(request.form.get('threshold', 0.70))
            threshold = max(0.50, min(1.0, threshold))
            use_encryption = request.form.get('use_encryption') == 'true'
            filter_region = request.form.get('filter_region') == 'true'

            # Query source: dropdown profile OR last uploaded (not stored) sample
            if query_id == '__LAST_UPLOADED__':
                query_profile = session.get('last_uploaded_profile')
            else:
                query_profile = next((p for p in DATABASE['profiles'] if p['id'] == query_id), None)

            if not query_profile:
                return jsonify({'success': False, 'error': 'Query profile not found'}), 404

            query_profile_id = query_profile.get('id')
            results = []

            for target_profile in DATABASE['profiles']:
                # Self profile skip -> 100% self-match bug fix
                if target_profile.get('id') == query_profile_id:
                    continue

                if filter_region and query_profile.get('region') != target_profile.get('region'):
                    continue

                score = calculate_tanabe_score(query_profile, target_profile)

                if score >= 0.95:
                    status = 'DEFINITE MATCH'
                elif score >= threshold:
                    status = 'PROBABLE MATCH'
                elif score >= 0.50:
                    status = 'PARTIAL MATCH'
                else:
                    status = 'NO MATCH'

                if score >= threshold:
                    results.append({
                        'target_id': target_profile['id'],
                        'score': score,
                        'status': status,
                        'encrypted': use_encryption,
                        'region': target_profile.get('region', 'USA')
                    })

            results.sort(key=lambda x: x['score'], reverse=True)

            match_result = {
                'query_id': query_profile_id,
                'timestamp': datetime.now().isoformat(),
                'threshold': threshold,
                'matches_found': len(results),
                'results': results[:10]
            }

            DATABASE['match_results'].append(match_result)

            matches_count = len(results)
            if matches_count > 0:
                add_notification('🔍 Match Found!', f'{matches_count} profile(s) matched!')

            return jsonify({
                'success': True,
                'query_id': query_profile_id,
                'matches_found': matches_count,
                'results': results[:10],
                'message': f'Found {matches_count} match(es)'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    theme = session.get('theme', 'dark')
    available_profiles = [p['id'] for p in DATABASE['profiles']]
    last_uploaded_profile_id = None
    if session.get('last_uploaded_profile'):
        last_uploaded_profile_id = session['last_uploaded_profile'].get('id')

    return render_template(
        'match.html',
        profiles=available_profiles,
        theme=theme,
        last_uploaded_profile_id=last_uploaded_profile_id
    )


@app.route('/results')
def view_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    theme = session.get('theme', 'dark')
    return render_template('results.html', results=DATABASE['match_results'], theme=theme)


@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({
        'success': True,
        'count': len(DATABASE['profiles']),
        'profiles': DATABASE['profiles']
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({
        'total_profiles': len(DATABASE['profiles']),
        'encrypted_profiles': len(DATABASE['encrypted_profiles']),
        'total_matches': len(DATABASE['match_results']),
        'last_update': datetime.now().isoformat()
    })


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    seen_ids = session.get('seen_notification_ids', [])
    notifications_with_status = []
    for n in DATABASE['notifications']:
        n_copy = dict(n)
        n_copy['seen'] = n['id'] in seen_ids
        notifications_with_status.append(n_copy)
    unread_count = sum(1 for n in notifications_with_status if not n['seen'])
    return jsonify({
        'success': True,
        'notifications': notifications_with_status,
        'unread_count': unread_count
    })


@app.route('/api/notifications/mark-seen', methods=['POST'])
def mark_notifications_seen():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    all_ids = [n['id'] for n in DATABASE['notifications']]
    session['seen_notification_ids'] = all_ids
    session.modified = True
    return jsonify({'success': True})


# ===== CRIME SCENE MATCHING =====
@app.route('/api/crime-scene-match', methods=['POST'])
def crime_scene_match():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    try:
        crime_sample = request.get_json(silent=True) or {}
        if 'markers' not in crime_sample:
            return jsonify({'success': False, 'error': 'Invalid crime scene sample'}), 400

        # Partial markers are allowed for crime-scene input
        crime_markers = normalize_markers(crime_sample['markers'], require_all_loci=False)
        crime_sample['markers'] = crime_markers

        if 'id' not in crime_sample or not str(crime_sample.get('id', '')).strip():
            crime_sample['id'] = 'CRIME_SCENE_' + datetime.now().strftime('%Y%m%d_%H%M%S')

        results = []
        for profile in DATABASE['profiles']:
            score = calculate_tanabe_score(crime_sample, profile)

            if score >= 0.95:
                status = 'DEFINITE MATCH'
                confidence = 'VERY HIGH'
            elif score >= 0.80:
                status = 'PROBABLE MATCH'
                confidence = 'HIGH'
            elif score >= 0.50:
                status = 'POSSIBLE MATCH'
                confidence = 'MEDIUM'
            else:
                status = 'NO MATCH'
                confidence = 'LOW'

            results.append({
                'suspect_id': profile.get('id', 'Unknown'),
                'suspect_name': profile.get('name', 'Unknown'),
                'arrest_date': profile.get('arrest_date', 'Unknown'),
                'similarity_score': score,
                'similarity_percentage': f"{score * 100:.2f}%",
                'status': status,
                'confidence': confidence,
                'region': profile.get('region', 'Unknown'),
                'case_type': profile.get('case_type', 'Unknown')
            })

        results.sort(key=lambda x: x['similarity_score'], reverse=True)

        definite_count = len([r for r in results if r['similarity_score'] >= 0.95])
        probable_count = len([r for r in results if 0.80 <= r['similarity_score'] < 0.95])

        match_record = {
            'crime_sample_id': crime_sample['id'],
            'timestamp': datetime.now().isoformat(),
            'total_profiles_searched': len(DATABASE['profiles']),
            'definite_matches': definite_count,
            'probable_matches': probable_count,
            'top_10_matches': results[:10]
        }
        DATABASE['match_results'].append(match_record)

        if definite_count > 0:
            add_notification('🚨 CRIME SCENE MATCH FOUND!', f"{definite_count} definite match(es)!")

        include_all = bool(crime_sample.get('include_all', False))
        return jsonify({
            'success': True,
            'crime_sample_id': crime_sample['id'],
            'total_profiles_searched': len(DATABASE['profiles']),
            'definite_matches': definite_count,
            'probable_matches': probable_count,
            'top_10_suspects': results[:10],
            'all_results': results if include_all else []
        }), 200
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/database-stats', methods=['GET'])
def database_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({
        'success': True,
        'total_profiles': len(DATABASE['profiles']),
        'total_matches_performed': len(DATABASE['match_results']),
        'database_file_path': DATABASE_FILE,
        'database_file_exists': os.path.exists(DATABASE_FILE),
        'database_file_size_kb': os.path.getsize(DATABASE_FILE) / 1024 if os.path.exists(DATABASE_FILE) else 0,
        'last_update': datetime.now().isoformat()
    }), 200


@app.route('/api/import-database', methods=['POST'])
def import_database():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        data = json.load(file)

        raw_profiles = data.get('profiles')
        if not isinstance(raw_profiles, list):
            return jsonify({'success': False, 'error': 'Invalid database format: profiles list missing'}), 400

        valid_profiles = []
        invalid_count = 0

        for p in raw_profiles:
            try:
                valid_profiles.append(normalize_profile(p, require_all_loci=False))
            except Exception:
                invalid_count += 1

        DATABASE['profiles'] = valid_profiles
        rebuild_encrypted_profiles()
        save_database_to_file()

        add_notification('📥 DATABASE IMPORTED', f"Imported {len(valid_profiles)} profiles ({invalid_count} skipped)")

        return jsonify({
            'success': True,
            'message': f"Imported {len(valid_profiles)} profiles",
            'total_profiles': len(valid_profiles),
            'invalid_profiles_skipped': invalid_count
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export-database', methods=['GET'])
def export_database():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    try:
        data = {
            'version': '2.1',
            'exported_at': datetime.now().isoformat(),
            'total_profiles': len(DATABASE['profiles']),
            'profiles': DATABASE['profiles']
        }

        output = io.BytesIO()
        output.write(json.dumps(data, indent=2).encode())
        output.seek(0)

        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'forensic_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    load_database_from_file()
    rebuild_encrypted_profiles()

    print("=" * 80)
    print("🧬 Privacy-Aware Forensic DNA Evidence Matching System - WITH DATABASE")
    print("=" * 80)
    print("✓ Server starting...")
    print(f"✓ Total Profiles in Database: {len(DATABASE['profiles'])}")
    print(f"✓ Encrypted Profiles In Memory: {len(DATABASE['encrypted_profiles'])}")
    print(f"✓ Database File: {DATABASE_FILE}")
    print("✓ Access the application at: http://127.0.0.1:5000")
    print("✓ You will be redirected to REGISTER page first")
    print("✓ After registration, LOGIN page will appear")
    print("=" * 80)

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
