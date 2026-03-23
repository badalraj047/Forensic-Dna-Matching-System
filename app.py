from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import io
import re
import random
import secrets
from datetime import datetime
from pathlib import Path

# ─── Import from project modules (no duplication) ───
from matcher import (
    CODIS_LOCI, ALLELE_RANGES,
    calculate_tanabe_score, calculate_tanabe_score_simple,
    calculate_kinship_score, calculate_rmp, full_match_analysis,
)
from encryption import DNAEncryption

# ═══════════════════════════════════════════════
# Flask app setup
# ═══════════════════════════════════════════════

app = Flask(__name__)


def _load_or_create_secret_key() -> str:
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
        return secrets.token_hex(32)


app.secret_key = _load_or_create_secret_key()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'


# ═══════════════════════════════════════════════
# In-memory database + file persistence
# ═══════════════════════════════════════════════

DATABASE = {
    'profiles': [],
    'encrypted_profiles': [],
    'match_results': [],
    'notifications': [],
    'users': [],
}

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = os.environ.get('DATABASE_FILE', str(BASE_DIR / 'profiles_database_realistic_10000.json'))
USERS_FILE = os.environ.get('USERS_FILE', str(BASE_DIR / 'users_database.json'))

crypto = DNAEncryption()

# ═══════════════════════════════════════════════
# Persistence helpers
# ═══════════════════════════════════════════════

def load_users_from_file() -> bool:
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


def save_users_to_file() -> bool:
    try:
        data = {
            'version': '1.1',
            'updated_at': datetime.now().isoformat(),
            'total_users': len(DATABASE['users']),
            'users': DATABASE['users'],
        }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠ Error saving users: {e}")
        return False


def load_database_from_file() -> bool:
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


def save_database_to_file() -> bool:
    try:
        data = {
            'version': '2.1',
            'updated_at': datetime.now().isoformat(),
            'total_profiles': len(DATABASE['profiles']),
            'codis_loci': CODIS_LOCI,
            'profiles': DATABASE['profiles'],
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠ Error saving database: {e}")
        return False


def rebuild_encrypted_profiles() -> int:
    encrypted = []
    for p in DATABASE['profiles']:
        try:
            if 'id' in p and 'markers' in p:
                encrypted.append(crypto.encrypt_profile(p))
        except Exception:
            continue
    DATABASE['encrypted_profiles'] = encrypted
    return len(encrypted)


# ═══════════════════════════════════════════════
# Validation helpers
# ═══════════════════════════════════════════════

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def normalize_markers(markers: dict, require_all_loci: bool = False) -> dict:
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
            raise ValueError(f"Missing required CODIS loci: {', '.join(missing[:5])}")
    return normalized


def normalize_profile(profile_data: dict, require_all_loci: bool = False) -> dict:
    if not isinstance(profile_data, dict):
        raise ValueError("Profile must be a JSON object")
    pid = str(profile_data.get('id', '')).strip()
    if not pid:
        raise ValueError("Profile id is required")
    markers = normalize_markers(profile_data.get('markers'), require_all_loci=require_all_loci)
    out = dict(profile_data)
    out['id'] = pid
    out['markers'] = markers
    out['region'] = str(profile_data.get('region', 'USA')).strip() or 'USA'
    out['timestamp'] = profile_data.get('timestamp', datetime.now().isoformat())
    out['type'] = profile_data.get('type', 'SYNTHETIC')
    return out


# ═══════════════════════════════════════════════
# User auth helpers
# ═══════════════════════════════════════════════

def find_user_by_email(email: str):
    for u in DATABASE['users']:
        if u['email'].lower() == email.lower():
            return u
    return None


def register_user(email, password, username):
    if find_user_by_email(email):
        return {'success': False, 'error': 'Email already registered'}
    user = {
        'id': len(DATABASE['users']) + 1,
        'email': email, 'username': username,
        'password': generate_password_hash(password),
        'created_at': datetime.now().isoformat(),
        'profiles_count': 0,
    }
    DATABASE['users'].append(user)
    return {'success': True, 'message': 'Registration successful! Please login.'}


def verify_login(email, password):
    user = find_user_by_email(email)
    if user and check_password_hash(user['password'], password):
        return {'success': True, 'user': user}
    return {'success': False, 'error': 'Invalid email or password'}


# ═══════════════════════════════════════════════
# Match result builder (shared by /match and /crime-scene)
# ═══════════════════════════════════════════════

def _classify(score, threshold):
    if score >= 0.95:
        return 'DEFINITE MATCH'
    if score >= threshold:
        return 'PROBABLE MATCH'
    if score >= 0.50:
        return 'PARTIAL MATCH'
    return 'NO MATCH'


def build_match_result(query, target, score, threshold, use_encryption=False):
    """Build a single match result dict with kinship + RMP."""
    status = _classify(score, threshold)
    region = target.get('region', 'General')

    # Full analysis: locus detail + kinship + RMP
    analysis = full_match_analysis(query, target, region=region)

    return {
        'target_id':       target['id'],
        'name':            target.get('name', 'Unknown'),
        'region':          target.get('region', 'N/A'),
        'country':         target.get('country', 'N/A'),
        'address':         target.get('address', 'N/A'),
        'city':            target.get('city', 'N/A'),
        'type':            target.get('type', 'N/A'),
        'status':          status,
        'profile_status':  target.get('status', 'N/A'),
        'verified':        target.get('verified', False),
        'quality_score':   target.get('quality_score', 0),
        'score':           score,
        'encrypted':       use_encryption,
        # ── NEW: forensic analysis ──
        'loci_details':    analysis['tanabe']['loci_details'],
        'loci_compared':   analysis['tanabe']['loci_compared'],
        'kinship':         {
            'relationship':   analysis['kinship']['relationship'],
            'ibs_mean':       analysis['kinship']['ibs_mean'],
            'obligate_share': analysis['kinship']['obligate_share'],
            'confidence':     analysis['kinship']['confidence'],
        },
        'rmp':             {
            'formatted':   analysis['rmp']['rmp_formatted'],
            'log10':       analysis['rmp']['log10_rmp'],
            'loci_counted': analysis['rmp']['loci_counted'],
        },
    }


# ═══════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════

def add_notification(title: str, message: str):
    n = {
        'id': len(DATABASE['notifications']) + 1,
        'title': title, 'message': message,
        'timestamp': datetime.now().isoformat(),
    }
    DATABASE['notifications'].append(n)
    if len(DATABASE['notifications']) > 50:
        DATABASE['notifications'] = DATABASE['notifications'][-50:]


# ═══════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════

load_users_from_file()
load_database_from_file()
rebuild_encrypted_profiles()


# ═══════════════════════════════════════════════
# Routes: pages & auth
# ═══════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = session.get('theme', 'dark')
    stats = {
        'total_profiles': len(DATABASE['profiles']),
        'encrypted_profiles': len(DATABASE['encrypted_profiles']),
        'total_matches': len(DATABASE['match_results']),
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
                return jsonify({'success': True, 'message': 'Login successful', 'redirect': '/'}), 200
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
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = session.get('theme', 'dark')
    user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
    if not user:
        return redirect(url_for('index'))
    joined_date = user.get('created_at', '')[:10] if user.get('created_at') else 'N/A'
    return render_template('profile.html',
        theme=theme, username=user['username'], email=user['email'],
        joined_date=joined_date,
        total_profiles=len(DATABASE['profiles']),
        total_matches=len(DATABASE['match_results']),
        user_id=user['id'])


@app.route('/crime-scene')
def crime_scene_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('crime-scene.html', theme=session.get('theme', 'dark'))


@app.route('/toggle-theme')
def toggle_theme():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    current = session.get('theme', 'dark')
    session['theme'] = 'dark' if current == 'light' else 'light'
    return jsonify({'theme': session['theme']})


@app.route('/api/user', methods=['GET'])
def get_user_info():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    return jsonify({'success': True, 'user': {
        'id': user['id'], 'email': user['email'],
        'username': user['username'],
        'profiles_count': user.get('profiles_count', 0),
    }})


# ═══════════════════════════════════════════════
# Generate profiles
# ═══════════════════════════════════════════════

@app.route('/generate', methods=['GET', 'POST'])
def generate_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            count = max(1, min(500, int(request.form.get('count', 1))))
            region = str(request.form.get('region', 'USA')).strip() or 'USA'
            start_count = len(DATABASE['profiles'])
            ids = []

            for i in range(count):
                pid = f"{region}_{start_count + i + 1:06d}"
                profile = {
                    'id': pid, 'markers': {}, 'timestamp': datetime.now().isoformat(),
                    'type': 'SYNTHETIC', 'region': region,
                }
                for locus in CODIS_LOCI:
                    lo, hi = ALLELE_RANGES[locus]
                    profile['markers'][locus] = sorted([random.randint(lo, hi), random.randint(lo, hi)])

                DATABASE['profiles'].append(profile)
                DATABASE['encrypted_profiles'].append(crypto.encrypt_profile(profile))
                ids.append(pid)

            user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
            if user:
                user['profiles_count'] = int(user.get('profiles_count', 0)) + count
                save_users_to_file()

            save_database_to_file()
            add_notification('✨ Profiles Generated', f'Generated {count} profile(s) from {region}')
            return jsonify({'success': True, 'message': f'Generated {count} profile(s) from {region}', 'profile_ids': ids})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('generate.html', theme=session.get('theme', 'dark'))


# ═══════════════════════════════════════════════
# Upload profile
# ═══════════════════════════════════════════════

@app.route('/upload', methods=['GET', 'POST'])
def upload_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            if 'id' not in data or 'markers' not in data:
                return jsonify({'success': False, 'error': 'Invalid profile format'}), 400
            for locus in data['markers']:
                alleles = data['markers'][locus]
                if not isinstance(alleles, list) or len(alleles) != 2:
                    return jsonify({'success': False, 'error': 'Each marker must have 2 alleles'}), 400
                data['markers'][locus] = [int(a) for a in alleles]
            if not data.get('region'):
                data['region'] = 'USA'
            store = bool(data.pop('store_in_database', False))
            session['last_uploaded_profile'] = data

            if store:
                if any(p.get('id') == data['id'] for p in DATABASE['profiles']):
                    return jsonify({'success': False, 'error': 'Profile ID already exists'}), 409
                DATABASE['profiles'].append(data)
                DATABASE['encrypted_profiles'].append(crypto.encrypt_profile(data))
                save_database_to_file()
                add_notification('📤 Profile Uploaded', f'Profile {data["id"]} stored in database')
                msg = 'Profile uploaded, encrypted, and stored in database'
            else:
                add_notification('🧪 Query Sample Uploaded', f'Profile {data["id"]} uploaded for matching')
                msg = 'Profile uploaded for matching only (not added to dataset)'

            return jsonify({'success': True, 'message': msg, 'profile_id': data['id'], 'stored_in_database': store})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('upload.html', theme=session.get('theme', 'dark'))


# ═══════════════════════════════════════════════
# Match profiles — NOW WITH LOCUS DETAIL + KINSHIP + RMP
# ═══════════════════════════════════════════════

@app.route('/match', methods=['GET', 'POST'])
def match_profiles():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            query_id = request.form.get('query_id')
            threshold = max(0.50, min(1.0, float(request.form.get('threshold', 0.70))))
            use_encryption = request.form.get('use_encryption') == 'true'
            filter_region = request.form.get('filter_region') == 'true'

            if query_id == '__LAST_UPLOADED__':
                query_profile = session.get('last_uploaded_profile')
            else:
                query_profile = next((p for p in DATABASE['profiles'] if p['id'] == query_id), None)

            if not query_profile:
                return jsonify({'success': False, 'error': 'Query profile not found'}), 404

            qid = query_profile.get('id')
            results = []

            for target in DATABASE['profiles']:
                if target.get('id') == qid:
                    continue
                if filter_region and query_profile.get('region') != target.get('region'):
                    continue

                score = calculate_tanabe_score_simple(query_profile, target)

                if score >= threshold:
                    results.append(build_match_result(
                        query_profile, target, score, threshold, use_encryption
                    ))

            results.sort(key=lambda x: x['score'], reverse=True)
            results = results[:10]

            match_record = {
                'query_id': qid,
                'timestamp': datetime.now().isoformat(),
                'threshold': threshold,
                'matches_found': len(results),
                'results': results,
            }
            DATABASE['match_results'].append(match_record)

            if len(results) > 0:
                add_notification('🔍 Match Found!', f'{len(results)} profile(s) matched!')

            return jsonify({
                'success': True,
                'query_id': qid,
                'matches_found': len(results),
                'results': results,
                'message': f'Found {len(results)} match(es)',
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    theme = session.get('theme', 'dark')
    available_profiles = [p['id'] for p in DATABASE['profiles']]
    last_uploaded_profile_id = None
    if session.get('last_uploaded_profile'):
        last_uploaded_profile_id = session['last_uploaded_profile'].get('id')
    return render_template('match.html',
        profiles=available_profiles, theme=theme,
        last_uploaded_profile_id=last_uploaded_profile_id)


# ═══════════════════════════════════════════════
# Crime scene matching — NOW WITH KINSHIP + RMP
# ═══════════════════════════════════════════════

@app.route('/api/crime-scene-match', methods=['POST'])
def crime_scene_match():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    try:
        crime_sample = request.get_json(silent=True) or {}
        if 'markers' not in crime_sample:
            return jsonify({'success': False, 'error': 'Invalid crime scene sample'}), 400

        crime_sample['markers'] = normalize_markers(crime_sample['markers'], require_all_loci=False)
        if not str(crime_sample.get('id', '')).strip():
            crime_sample['id'] = 'CRIME_SCENE_' + datetime.now().strftime('%Y%m%d_%H%M%S')

        results = []
        for profile in DATABASE['profiles']:
            score = calculate_tanabe_score_simple(crime_sample, profile)

            if score >= 0.95:
                status, confidence = 'DEFINITE MATCH', 'VERY HIGH'
            elif score >= 0.80:
                status, confidence = 'PROBABLE MATCH', 'HIGH'
            elif score >= 0.50:
                status, confidence = 'POSSIBLE MATCH', 'MEDIUM'
            else:
                status, confidence = 'NO MATCH', 'LOW'

            # Full analysis for top candidates
            analysis = full_match_analysis(crime_sample, profile, region=profile.get('region', 'General'))

            results.append({
                'suspect_id': profile.get('id', 'Unknown'),
                'suspect_name': profile.get('name', 'Unknown'),
                'arrest_date': profile.get('arrest_date', 'Unknown'),
                'similarity_score': score,
                'similarity_percentage': f"{score * 100:.2f}%",
                'status': status,
                'confidence': confidence,
                'region': profile.get('region', 'Unknown'),
                'case_type': profile.get('case_type', 'Unknown'),
                # ── NEW ──
                'loci_details': analysis['tanabe']['loci_details'],
                'loci_compared': analysis['tanabe']['loci_compared'],
                'kinship': {
                    'relationship': analysis['kinship']['relationship'],
                    'ibs_mean': analysis['kinship']['ibs_mean'],
                    'obligate_share': analysis['kinship']['obligate_share'],
                    'confidence': analysis['kinship']['confidence'],
                },
                'rmp': {
                    'formatted': analysis['rmp']['rmp_formatted'],
                    'log10': analysis['rmp']['log10_rmp'],
                },
            })

        results.sort(key=lambda x: x['similarity_score'], reverse=True)

        definite = sum(1 for r in results if r['similarity_score'] >= 0.95)
        probable = sum(1 for r in results if 0.80 <= r['similarity_score'] < 0.95)

        match_record = {
            'crime_sample_id': crime_sample['id'],
            'timestamp': datetime.now().isoformat(),
            'total_profiles_searched': len(DATABASE['profiles']),
            'definite_matches': definite,
            'probable_matches': probable,
            'top_10_matches': results[:10],
        }
        DATABASE['match_results'].append(match_record)

        if definite > 0:
            add_notification('🚨 CRIME SCENE MATCH!', f"{definite} definite match(es)!")

        include_all = bool(crime_sample.get('include_all', False))
        return jsonify({
            'success': True,
            'crime_sample_id': crime_sample['id'],
            'total_profiles_searched': len(DATABASE['profiles']),
            'definite_matches': definite,
            'probable_matches': probable,
            'top_10_suspects': results[:10],
            'all_results': results if include_all else [],
        }), 200

    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════
# NEW: RMP + Kinship API endpoints
# ═══════════════════════════════════════════════

@app.route('/api/rmp/<profile_id>', methods=['GET'])
def get_rmp(profile_id):
    """Get Random Match Probability for a specific profile."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    profile = next((p for p in DATABASE['profiles'] if p['id'] == profile_id), None)
    if not profile:
        return jsonify({'success': False, 'error': 'Profile not found'}), 404
    region = profile.get('region', 'General')
    rmp = calculate_rmp(profile, region=region)
    return jsonify({'success': True, 'profile_id': profile_id, 'rmp': rmp})


@app.route('/api/kinship', methods=['POST'])
def get_kinship():
    """Compare two profiles for familial relationship."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json(silent=True) or {}
    id1 = data.get('profile1_id')
    id2 = data.get('profile2_id')
    p1 = next((p for p in DATABASE['profiles'] if p['id'] == id1), None)
    p2 = next((p for p in DATABASE['profiles'] if p['id'] == id2), None)
    if not p1 or not p2:
        return jsonify({'success': False, 'error': 'One or both profiles not found'}), 404
    result = calculate_kinship_score(p1, p2)
    return jsonify({'success': True, 'profile1': id1, 'profile2': id2, 'kinship': result})


# ═══════════════════════════════════════════════
# Results, stats, notifications, import/export
# ═══════════════════════════════════════════════

@app.route('/results')
def view_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('results.html', results=DATABASE['match_results'],
                           theme=session.get('theme', 'dark'))


@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({'success': True, 'count': len(DATABASE['profiles']),
                    'profiles': DATABASE['profiles']})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({
        'total_profiles': len(DATABASE['profiles']),
        'encrypted_profiles': len(DATABASE['encrypted_profiles']),
        'total_matches': len(DATABASE['match_results']),
        'last_update': datetime.now().isoformat(),
    })


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    seen = session.get('seen_notification_ids', [])
    out = []
    for n in DATABASE['notifications']:
        c = dict(n)
        c['seen'] = n['id'] in seen
        out.append(c)
    unread = sum(1 for n in out if not n['seen'])
    return jsonify({'success': True, 'notifications': out, 'unread_count': unread})


@app.route('/api/notifications/mark-seen', methods=['POST'])
def mark_notifications_seen():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    session['seen_notification_ids'] = [n['id'] for n in DATABASE['notifications']]
    session.modified = True
    return jsonify({'success': True})


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
        'last_update': datetime.now().isoformat(),
    }), 200


@app.route('/api/import-database', methods=['POST'])
def import_database():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        data = json.load(request.files['file'])
        raw = data.get('profiles')
        if not isinstance(raw, list):
            return jsonify({'success': False, 'error': 'Invalid database format'}), 400
        valid, invalid = [], 0
        for p in raw:
            try:
                valid.append(normalize_profile(p, require_all_loci=False))
            except Exception:
                invalid += 1
        DATABASE['profiles'] = valid
        rebuild_encrypted_profiles()
        save_database_to_file()
        add_notification('📥 DATABASE IMPORTED', f"Imported {len(valid)} profiles ({invalid} skipped)")
        return jsonify({'success': True, 'message': f"Imported {len(valid)} profiles",
                        'total_profiles': len(valid), 'invalid_profiles_skipped': invalid}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export-database', methods=['GET'])
def export_database():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        data = {'version': '2.1', 'exported_at': datetime.now().isoformat(),
                'total_profiles': len(DATABASE['profiles']), 'profiles': DATABASE['profiles']}
        output = io.BytesIO()
        output.write(json.dumps(data, indent=2).encode())
        output.seek(0)
        return send_file(output, mimetype='application/json', as_attachment=True,
                         download_name=f'forensic_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    print("=" * 80)
    print("🧬 Privacy-Aware Forensic DNA Evidence Matching System")
    print("=" * 80)
    print(f"✓ Total Profiles in Database: {len(DATABASE['profiles'])}")
    print(f"✓ Encrypted Profiles In Memory: {len(DATABASE['encrypted_profiles'])}")
    print(f"✓ Database File: {DATABASE_FILE}")
    print("✓ NEW: Locus-by-locus comparison enabled")
    print("✓ NEW: Kinship / familial matching enabled")
    print("✓ NEW: Random Match Probability (RMP) enabled")
    print("✓ Access: http://127.0.0.1:5000")
    print("=" * 80)

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
