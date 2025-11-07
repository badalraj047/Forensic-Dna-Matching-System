import random
import json

# CODIS 20 core loci used in forensic DNA profiling
CODIS_LOCI = [
    'CSF1PO', 'D3S1358', 'D5S818', 'D7S820', 'D8S1179',
    'D13S317', 'D16S539', 'D18S51', 'D21S11', 'FGA',
    'TH01', 'TPOX', 'vWA', 'D1S1656', 'D2S441',
    'D2S1338', 'D10S1248', 'D12S391', 'D19S433', 'D22S1045'
]

# Typical allele ranges for each STR locus (based on forensic standards)
ALLELE_RANGES = {
    'CSF1PO': (6, 16),
    'D3S1358': (12, 20),
    'D5S818': (7, 16),
    'D7S820': (6, 15),
    'D8S1179': (8, 19),
    'D13S317': (8, 16),
    'D16S539': (5, 16),
    'D18S51': (9, 27),
    'D21S11': (24, 38),
    'FGA': (17, 30),
    'TH01': (4, 11),
    'TPOX': (6, 13),
    'vWA': (11, 21),
    'D1S1656': (9, 20),
    'D2S441': (8, 17),
    'D2S1338': (15, 28),
    'D10S1248': (8, 19),
    'D12S391': (15, 26),
    'D19S433': (9, 17),
    'D22S1045': (8, 19)
}

def generate_synthetic_profile(profile_id):
    """
    Generate one synthetic STR profile with random allele values
    Each person has 2 alleles per locus (diploid organism)
    """
    profile = {
        'id': profile_id,
        'markers': {}
    }

    for locus in CODIS_LOCI:
        min_val, max_val = ALLELE_RANGES[locus]
        # Generate two alleles (one from each parent)
        allele1 = random.randint(min_val, max_val)
        allele2 = random.randint(min_val, max_val)
        profile['markers'][locus] = sorted([allele1, allele2])

    return profile

def generate_multiple_profiles(count=100):
    """Generate multiple synthetic profiles"""
    profiles = []
    for i in range(count):
        profile = generate_synthetic_profile(f"PROFILE_{i:04d}")
        profiles.append(profile)
    return profiles

def save_profiles_to_file(profiles, filename='synthetic_profiles.json'):
    """Save profiles to JSON file"""
    with open(filename, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"Saved {len(profiles)} profiles to {filename}")

if __name__ == '__main__':
    # Generate 50 synthetic profiles for testing
    profiles = generate_multiple_profiles(50)
    save_profiles_to_file(profiles)
    print("Sample profile:")
    print(json.dumps(profiles[0], indent=2))
