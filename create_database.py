import json
import random
from datetime import datetime, timedelta

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

# Regions for diversity
REGIONS = ['USA', 'India', 'Europe', 'Canada', 'Australia', 'UK', 'Japan', 'China']

# Case types
CASE_TYPES = ['Robbery', 'Assault', 'Homicide', 'Burglary', 'Missing Person', 'Cold Case', 'Sexual Assault', 'Terrorism']

# Generate random names
FIRST_NAMES = ['John', 'Michael', 'David', 'James', 'Robert', 'William', 'Richard', 'Thomas', 'Charles', 'Daniel',
               'Mary', 'Patricia', 'Jennifer', 'Linda', 'Barbara', 'Elizabeth', 'Susan', 'Jessica', 'Sarah', 'Karen',
               'Raj', 'Amit', 'Priya', 'Anita', 'Vikram', 'Sanjay', 'Deepak', 'Ravi', 'Neha', 'Pooja']

LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Kumar', 'Singh', 'Sharma', 'Patel', 'Gupta', 'Khan', 'Reddy', 'Rao', 'Mehta', 'Verma']

def generate_random_name():
    """Generate a random full name"""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_random_date(start_year=2015, end_year=2025):
    """Generate random date between start_year and end_year"""
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)
    random_date = start_date + timedelta(days=random_days)
    return random_date.strftime('%Y-%m-%d')

def generate_profile(profile_num):
    """Generate one realistic DNA profile with metadata"""
    
    # Select region and generate appropriate name
    region = random.choice(REGIONS)
    
    profile = {
        'id': f'SUSPECT_{profile_num:04d}',
        'name': generate_random_name(),
        'age': random.randint(18, 75),
        'gender': random.choice(['Male', 'Female']),
        'region': region,
        'case_type': random.choice(CASE_TYPES),
        'arrest_date': generate_random_date(2015, 2025),
        'case_number': f'CASE-{random.randint(2015, 2025)}-{random.randint(1000, 9999)}',
        'status': random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'CLOSED', 'PENDING']),  # More ACTIVE cases
        'quality_score': round(random.uniform(0.85, 1.0), 2),
        'verified': random.choice([True, True, True, False]),  # 75% verified
        'lab_id': f'LAB_{random.randint(1, 50):03d}',
        'confirmed_by': f'Dr. {random.choice(LAST_NAMES)}',
        'timestamp': datetime.now().isoformat(),
        'type': 'SYNTHETIC',
        'markers': {}
    }
    
    # Generate alleles for all 20 CODIS loci
    for locus in CODIS_LOCI:
        min_val, max_val = ALLELE_RANGES[locus]
        allele1 = random.randint(min_val, max_val)
        allele2 = random.randint(min_val, max_val)
        profile['markers'][locus] = sorted([int(allele1), int(allele2)])
    
    return profile

def create_database(num_profiles=1000):
    """Create database with specified number of profiles"""
    
    print(f"\n🧬 Generating {num_profiles} DNA profiles...")
    print("=" * 70)
    
    profiles = []
    
    # Generate profiles with progress updates
    for i in range(1, num_profiles + 1):
        profile = generate_profile(i)
        profiles.append(profile)
        
        # Progress indicator
        if i % 100 == 0:
            print(f"✓ Generated {i}/{num_profiles} profiles ({(i/num_profiles)*100:.0f}%)")
    
    # Create complete database structure
    database = {
        'version': '2.0',
        'created_at': datetime.now().isoformat(),
        'description': 'Forensic DNA Database with synthetic STR profiles',
        'total_profiles': len(profiles),
        'codis_loci': CODIS_LOCI,
        'regions': REGIONS,
        'profiles': profiles
    }
    
    # Save to JSON file
    filename = 'profiles_database.json'
    with open(filename, 'w') as f:
        json.dump(database, f, indent=2)
    
    # Calculate file size
    import os
    file_size = os.path.getsize(filename)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"\n{'=' * 70}")
    print(f"✓ SUCCESS! Database created successfully!")
    print(f"{'=' * 70}")
    print(f"📁 Filename:        {filename}")
    print(f"📊 Total Profiles:  {len(profiles)}")
    print(f"💾 File Size:       {file_size_mb:.2f} MB ({file_size:,} bytes)")
    print(f"🔬 CODIS Loci:      {len(CODIS_LOCI)} markers per profile")
    print(f"🌍 Regions:         {len(REGIONS)} ({', '.join(REGIONS)})")
    print(f"📅 Created:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}")
    print(f"\n✓ Database is ready!")
    print(f"✓ Now run: python app.py")
    print(f"✓ Your website will automatically load all {num_profiles} profiles!")
    print(f"\n")
    
    # Show sample profile
    print(f"📋 Sample Profile (first profile):")
    print(f"{'=' * 70}")
    sample = profiles[0]
    print(f"ID:           {sample['id']}")
    print(f"Name:         {sample['name']}")
    print(f"Age:          {sample['age']}")
    print(f"Gender:       {sample['gender']}")
    print(f"Region:       {sample['region']}")
    print(f"Case Type:    {sample['case_type']}")
    print(f"Arrest Date:  {sample['arrest_date']}")
    print(f"Status:       {sample['status']}")
    print(f"Quality:      {sample['quality_score']}")
    print(f"\nDNA Markers (sample - first 5):")
    for i, (locus, alleles) in enumerate(sample['markers'].items()):
        if i < 5:
            print(f"  {locus}: {alleles}")
    print(f"  ... (15 more loci)")
    print(f"{'=' * 70}\n")

if __name__ == '__main__':
    # Create database with 1000 profiles
    create_database(1000)
    
    print("🎉 READY TO USE!")
    print("Next steps:")
    print("  1. Run: python app.py")
    print("  2. Open: http://127.0.0.1:5000")
    print("  3. Dashboard will show: 'Total Profiles: 1000'")
    print("  4. Click 'Go to Crime Matching' to test!\n")
