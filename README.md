# Privacy-Aware Forensic DNA Evidence Matching System

## Capstone Project: Using Synthetic STR Profiles

### Project Overview

A full-stack **Privacy-Aware Forensic DNA Matching System** implementing real forensic science algorithms:

- **20 CODIS Core STR Loci** for forensic DNA profiling
- **Tanabe Similarity Score** with locus-by-locus comparison
- **Kinship / Familial Matching** — detect parent-child and sibling relationships
- **Random Match Probability (RMP)** — court-standard statistical analysis using Hardy-Weinberg equilibrium
- **Hash-based encrypted comparison** (HE-inspired demo) for privacy-preserving matching
- **Synthetic Profile Generation** for ethical testing
- **User Authentication** with registration, login, and sessions

---

## Project Structure

```
forensic-dna-matching-system/
├── app.py                          # Flask web app (imports from modules below)
├── matcher.py                      # Tanabe score, kinship analysis, RMP calculation
├── encryption.py                   # SHA-256 privacy-preserving encryption
├── profile_generator.py            # Synthetic STR profile generator
├── create_database.py              # Database creator with realistic metadata
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── Dockerfile                      # Docker configuration
├── Procfile                        # Deployment config
├── profiles_database_realistic_10000.json  # Pre-built database (10,000 profiles)
├── templates/
│   ├── index.html                  # Dashboard homepage
│   ├── login.html                  # Login page
│   ├── register.html               # Registration page
│   ├── profile.html                # User profile page
│   ├── generate.html               # Profile generation page
│   ├── upload.html                 # Profile upload page
│   ├── match.html                  # Matching interface with locus comparison
│   ├── crime-scene.html            # Crime scene matching
│   └── results.html                # Results history
└── wsgi.py                         # WSGI entry point
```

---

## Installation & Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Generate Database (optional — 10,000 profiles included)

```bash
python create_database.py
```

### Step 3: Run the Application

```bash
python app.py
```

Access at: **http://127.0.0.1:5000**

---

## Features

### 1. Tanabe Similarity Score with Locus-by-Locus Comparison

Every match result includes a detailed breakdown of all 20 CODIS loci showing:
- Query alleles vs target alleles at each locus
- Color-coded match status: full match (both alleles), partial (one allele), mismatch (none)
- Total shared alleles and overall similarity score

**Formula:** `Score = (2 × shared_alleles) / (total_alleles_in_both_profiles)`

**Classification:**
| Score | Classification |
|-------|---------------|
| ≥ 0.95 | DEFINITE MATCH |
| ≥ 0.80 | PROBABLE MATCH |
| ≥ 0.50 | PARTIAL MATCH |
| < 0.50 | NO MATCH |

### 2. Kinship / Familial Matching

Detects biological relationships between DNA profiles using Identity By State (IBS) analysis:
- **Parent-Child:** Share at least 1 allele at every locus (obligate allele sharing = 100%)
- **Sibling:** Average IBS ≈ 1.5 per locus
- **Unrelated:** Average IBS ≈ 0.9–1.0 per locus

This is the technique used to identify the Golden State Killer via familial DNA searching.

### 3. Random Match Probability (RMP)

Calculates the statistical probability that a DNA match is coincidental — the metric used in courtroom testimony.

**Method:** Hardy-Weinberg equilibrium with population allele frequency tables.

- Heterozygous locus (a ≠ b): `P = 2 × freq(a) × freq(b)`
- Homozygous locus (a = b): `P = freq(a)²`
- Product rule: multiply probabilities across all 20 loci

Typical RMP values: **1 in billions to trillions**, establishing statistical certainty of identity.

### 4. Privacy-Preserving Encryption

Hash-based encrypted comparison using SHA-256:
- Each allele is hashed with a keyed salt per locus
- Matching is performed on encrypted hashes — raw DNA never exposed
- Demonstrates the concept of homomorphic encryption for DNA forensics

**Note:** This is a demonstration. Production systems would use true HE libraries (Microsoft SEAL, Paillier).

### 5. User Authentication

- Registration with email, username, and password
- Secure login with bcrypt password hashing
- Session management with theme preferences
- User profile page with activity statistics

### 6. Crime Scene Matching

- Upload partial DNA samples (fewer than 20 loci supported)
- Match against the entire database
- Includes kinship analysis and RMP for each suspect result

---

## Code Architecture

```
app.py  ──imports──>  matcher.py    (Tanabe, kinship, RMP algorithms)
        ──imports──>  encryption.py (SHA-256 privacy-preserving encryption)
```

All matching logic lives in `matcher.py`. All encryption logic lives in `encryption.py`. The Flask app (`app.py`) imports and uses these modules — **no code duplication**.

### Key Module: `matcher.py`

| Function | Purpose |
|----------|---------|
| `calculate_tanabe_score()` | Full Tanabe score with per-locus detail |
| `calculate_tanabe_score_simple()` | Lightweight float-only score for bulk scans |
| `calculate_kinship_score()` | IBS-based familial relationship detection |
| `calculate_rmp()` | Hardy-Weinberg random match probability |
| `full_match_analysis()` | Runs all three in a single call |

### Key Module: `encryption.py`

| Method | Purpose |
|--------|---------|
| `encrypt_profile()` | Hash all allele markers with SHA-256 |
| `compute_similarity_encrypted()` | Tanabe score on encrypted profiles |
| `verify_integrity()` | Validate encrypted profile structure |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/match` | POST | Match profiles (returns locus detail + kinship + RMP) |
| `/api/crime-scene-match` | POST | Crime scene matching |
| `/api/rmp/<profile_id>` | GET | Get RMP for a specific profile |
| `/api/kinship` | POST | Compare two profiles for kinship |
| `/api/profiles` | GET | List all profiles |
| `/api/stats` | GET | Database statistics |
| `/api/export-database` | GET | Download database as JSON |
| `/api/import-database` | POST | Upload replacement database |

---

## CODIS 20 Core Loci

CSF1PO, D3S1358, D5S818, D7S820, D8S1179, D13S317, D16S539, D18S51, D21S11, FGA, TH01, TPOX, vWA, D1S1656, D2S441, D2S1338, D10S1248, D12S391, D19S433, D22S1045

---

## Technology Stack

- **Backend:** Python 3, Flask
- **Algorithms:** Tanabe similarity, Hardy-Weinberg RMP, IBS kinship analysis
- **Encryption:** SHA-256 keyed hashing (HE-inspired demo)
- **Frontend:** HTML5, CSS3, JavaScript (no framework — vanilla)
- **Data:** JSON file storage with in-memory caching

---

## Testing Scenarios

1. **Identity match:** Same profile → score = 1.0, RMP = very rare
2. **Partial match:** Modified profile → score 0.5–0.9, locus table shows which loci differ
3. **Kinship test:** Parent-child pair → IBS mean ≥ 1.0, obligate share = 100%
4. **Privacy test:** Encrypted profiles produce same match results as plaintext

---

## References

1. CODIS Database — FBI Forensic Science Communications
2. Tanabe et al. — STR Matching Algorithms for Cell Authentication
3. Hardy-Weinberg Equilibrium — Population Genetics (Hartl & Clark)
4. NIST STR Database — allele frequency reference data
5. Familial DNA Searching — NIJ Forensic Science Research

---

## Project Checklist

- [x] Synthetic profile generation (20 CODIS loci)
- [x] Tanabe similarity scoring
- [x] Locus-by-locus comparison (color-coded)
- [x] Kinship / familial matching (IBS analysis)
- [x] Random Match Probability (Hardy-Weinberg)
- [x] Hash-based privacy-preserving encryption
- [x] User authentication (register / login / sessions)
- [x] Crime scene partial-sample matching
- [x] Dark/light theme toggle
- [x] Import/export database
- [x] Notification system
- [x] Modular code architecture (no duplication)
- [x] Documentation
- [ ] True homomorphic encryption (Microsoft SEAL — future)
- [ ] MongoDB / PostgreSQL integration (future)
- [ ] PDF report generation (future)

---

## License

This project is for educational and research purposes only.
