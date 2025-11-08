from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime
from pathlib import Path
import secrets
import random

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# In-memory storage
DATABASE = {
    'profiles': [],
    'encrypted_profiles': [],
    'match_results': [],
    'notifications': [],
    'users': []
}

# ===== DATABASE PERSISTENCE =====
DATABASE_FILE = 'profiles_database.json'

def load_database_from_file():
    """Load all profiles from persistent JSON file"""
    global DATABASE
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r') as f:
                data = json.load(f)
                DATABASE['profiles'] = data.get('profiles', [])
                print(f"✓ Loaded {len(DATABASE['profiles'])} profiles from database")
                return True
        except Exception as e:
            print(f"⚠ Error loading database: {e}")
            return False
    return False

def save_database_to_file():
    """Save all profiles to persistent JSON file"""
    try:
        data = {
            'version': '2.0',
            'created_at': datetime.now().isoformat(),
            'total_profiles': len(DATABASE['profiles']),
            'profiles': DATABASE['profiles']
        }
        with open(DATABASE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠ Error saving database: {e}")
        return False

# ===== END DATABASE PERSISTENCE =====

# ===== USER AUTHENTICATION =====
def find_user_by_email(email):
    """Find a user by email"""
    for user in DATABASE['users']:
        if user['email'].lower() == email.lower():
            return user
    return None

def register_user(email, password, username):
    """Register a new user"""
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

def verify_login(email, password):
    """Verify user credentials"""
    user = find_user_by_email(email)
    if user and check_password_hash(user['password'], password):
        return {'success': True, 'user': user}
    return {'success': False, 'error': 'Invalid email or password'}

# ===== END USER AUTHENTICATION =====

# Encryption class
class DNAEncryption:
    def __init__(self):
        self.key = "forensic_key_2025"
    
    def encrypt_profile(self, profile):
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

crypto = DNAEncryption()

# FIXED: Proper Tanabe score calculation
def calculate_tanabe_score(profile1, profile2):
    """Calculate Tanabe similarity score for DNA profiles"""
    shared_alleles = 0
    total_alleles = 0
    for locus in profile1['markers']:
        if locus in profile2['markers']:
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
    score = (2 * shared_alleles) / total_alleles
    return round(score, 4)

# Function to create notifications
def add_notification(title, message):
    """Add a notification to the database"""
    notification = {
        'id': len(DATABASE['notifications']),
        'title': title,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    DATABASE['notifications'].append(notification)
    if len(DATABASE['notifications']) > 20:
        DATABASE['notifications'].pop(0)

# ===== AUTHENTICATION ROUTES =====

# HOME ROUTE - REDIRECTS TO LOGIN IF NOT AUTHENTICATED
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

# REGISTER ROUTE - FIRST PAGE USERS VISIT
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()
            username = data.get('username', '').strip()
            confirm_password = data.get('confirm_password', '').strip()

            # Validation
            if not email or not password or not username:
                return jsonify({'success': False, 'error': 'All fields required'}), 400
            if len(password) < 6:
                return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
            if password != confirm_password:
                return jsonify({'success': False, 'error': 'Passwords do not match'}), 400

            result = register_user(email, password, username)
            if result['success']:
                return jsonify(result), 201
            else:
                return jsonify(result), 409
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    return render_template('register.html')

# LOGIN ROUTE - SHOWN AFTER REGISTRATION
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()

            if not email or not password:
                return jsonify({'success': False, 'error': 'Email and password required'}), 400

            result = verify_login(email, password)
            if result['success']:
                user = result['user']
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['username'] = user['username']
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'redirect': '/'
                }), 200
            else:
                return jsonify(result), 401
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/user', methods=['GET'])
def get_user_info():
    """Get current user info"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    user = next((u for u in DATABASE['users'] if u['id'] == session['user_id']), None)
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user['username'],
                'profiles_count': user['profiles_count']
            }
        })
    return jsonify({'success': False, 'error': 'User not found'}), 404

# ===== END AUTHENTICATION ROUTES =====

@app.route('/toggle-theme')
def toggle_theme():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    current = session.get('theme', 'dark')
    session['theme'] = 'light' if current == 'dark' else 'dark'
    return jsonify({'theme': session['theme']})

@app.route('/generate', methods=['GET', 'POST'])
def generate_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        count = int(request.form.get('count', 1))
        region = request.form.get('region', 'USA')
        profiles_generated = []

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

        for i in range(count):
            profile_id = f"{region}_{len(DATABASE['profiles']) + i + 1:04d}"
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
            encrypted = crypto.encrypt_profile(profile)
            DATABASE['encrypted_profiles'].append(encrypted)
            profiles_generated.append(profile_id)
            add_notification('✨ Profile Generated', f'Profile {profile_id} from {region} region')

        return jsonify({
            'success': True,
            'message': f'Generated {count} profile(s) from {region}',
            'profile_ids': profiles_generated
        })

    theme = session.get('theme', 'dark')
    return render_template('generate.html', theme=theme)

@app.route('/upload', methods=['GET', 'POST'])
def upload_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            profile_data = request.get_json()
            if 'id' not in profile_data or 'markers' not in profile_data:
                return jsonify({'success': False, 'error': 'Invalid profile format'}), 400

            for locus in profile_data['markers']:
                alleles = profile_data['markers'][locus]
                if not isinstance(alleles, list) or len(alleles) != 2:
                    return jsonify({'success': False, 'error': f'Each marker must have 2 alleles'}), 400
                profile_data['markers'][locus] = [int(a) for a in alleles]

            if 'region' not in profile_data:
                profile_data['region'] = 'USA'

            DATABASE['profiles'].append(profile_data)
            encrypted = crypto.encrypt_profile(profile_data)
            DATABASE['encrypted_profiles'].append(encrypted)
            add_notification('📤 Profile Uploaded', f'Profile {profile_data["id"]} uploaded successfully')

            return jsonify({
                'success': True,
                'message': 'Profile uploaded and encrypted',
                'profile_id': profile_data['id']
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
            use_encryption = request.form.get('use_encryption') == 'true'
            filter_region = request.form.get('filter_region') == 'true'

            query_profile = next((p for p in DATABASE['profiles'] if p['id'] == query_id), None)
            if not query_profile:
                return jsonify({'success': False, 'error': 'Query profile not found'}), 404

            results = []
            for target_profile in DATABASE['profiles']:
                if target_profile['id'] == query_id:
                    score = 1.0
                    status = 'PERFECT MATCH (SELF)'
                else:
                    score = calculate_tanabe_score(query_profile, target_profile)
                    if score >= 0.95:
                        status = 'DEFINITE MATCH'
                    elif score >= threshold:
                        status = 'PROBABLE MATCH'
                    elif score >= 0.50:
                        status = 'PARTIAL MATCH'
                    else:
                        status = 'NO MATCH'

                if filter_region:
                    if query_profile.get('region') != target_profile.get('region'):
                        continue

                if score >= threshold or target_profile['id'] == query_id:
                    results.append({
                        'target_id': target_profile['id'],
                        'score': score,
                        'status': status,
                        'encrypted': use_encryption,
                        'region': target_profile.get('region', 'USA')
                    })

            results.sort(key=lambda x: x['score'], reverse=True)

            match_result = {
                'query_id': query_id,
                'timestamp': datetime.now().isoformat(),
                'threshold': threshold,
                'matches_found': len([r for r in results if r['score'] >= threshold]),
                'results': results[:10]
            }

            DATABASE['match_results'].append(match_result)

            matches_count = len([r for r in results if r['score'] >= threshold])
            if matches_count > 0:
                add_notification('🔍 Match Found!', f'{matches_count} profile(s) matched!')

            return jsonify({
                'success': True,
                'query_id': query_id,
                'matches_found': len([r for r in results if r['score'] >= threshold]),
                'results': results[:10],
                'message': f'Found {len([r for r in results if r["score"] >= threshold])} match(es)'
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    theme = session.get('theme', 'dark')
    available_profiles = [p['id'] for p in DATABASE['profiles']]
    return render_template('match.html', profiles=available_profiles, theme=theme)

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
    """Get all notifications"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    return jsonify({
        'success': True,
        'notifications': DATABASE['notifications']
    })

# ===== CRIME SCENE MATCHING - NEW FEATURE =====

@app.route('/api/crime-scene-match', methods=['POST'])
def crime_scene_match():
    """Match crime scene DNA against entire database (1000+ profiles)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        crime_sample = request.get_json()
        if not crime_sample or 'markers' not in crime_sample:
            return jsonify({'success': False, 'error': 'Invalid crime scene sample'}), 400

        if 'id' not in crime_sample:
            crime_sample['id'] = 'CRIME_SCENE_' + datetime.now().strftime('%Y%m%d_%H%M%S')

        results = []

        # LOOP THROUGH ALL PROFILES IN DATABASE
        for profile in DATABASE['profiles']:
            score = calculate_tanabe_score(crime_sample, profile)

            # Classify match
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
        save_database_to_file()

        if definite_count > 0:
            add_notification(
                '🚨 CRIME SCENE MATCH FOUND!',
                f"{definite_count} definite match(es)!"
            )

        return jsonify({
            'success': True,
            'crime_sample_id': crime_sample['id'],
            'total_profiles_searched': len(DATABASE['profiles']),
            'definite_matches': definite_count,
            'probable_matches': probable_count,
            'top_10_suspects': results[:10],
            'all_results': results
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database-stats', methods=['GET'])
def database_stats():
    """Get database statistics"""
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
    """Import database from uploaded JSON file"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        data = json.load(file)

        DATABASE['profiles'] = data.get('profiles', [])

        save_database_to_file()

        add_notification('📥 DATABASE IMPORTED', f"Imported {len(DATABASE['profiles'])} profiles")

        return jsonify({
            'success': True,
            'message': f"Imported {len(DATABASE['profiles'])} profiles",
            'total_profiles': len(DATABASE['profiles'])
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export-database', methods=['GET'])
def export_database():
    """Export database as JSON file"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        data = {
            'version': '2.0',
            'exported_at': datetime.now().isoformat(),
            'total_profiles': len(DATABASE['profiles']),
            'profiles': DATABASE['profiles']
        }

        from flask import send_file
        import io

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

# ===== END CRIME SCENE MATCHING =====

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    # LOAD DATABASE ON STARTUP
    load_database_from_file()

    print("=" * 80)
    print("🧬 Privacy-Aware Forensic DNA Matching System - WITH DATABASE")
    print("=" * 80)
    print("✓ Server starting...")
    print(f"✓ Total Profiles in Database: {len(DATABASE['profiles'])}")
    print(f"✓ Database File: {DATABASE_FILE}")
    print("✓ Access the application at: http://127.0.0.1:5000")
    print("✓ You will be redirected to REGISTER page first")
    print("✓ After registration, LOGIN page will appear")
    print("=" * 80)

    app.run(debug=True, host='0.0.0.0', port=5000)
