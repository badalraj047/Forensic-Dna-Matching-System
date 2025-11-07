import json
import hashlib
from datetime import datetime

class SimplifiedDNAEncryption:
    """
    Simplified encryption system for DNA profiles
    Uses secure hashing and privacy-preserving comparison
    """

    def __init__(self, encryption_key="forensic_dna_key_2025"):
        self.encryption_key = encryption_key
        self.key_hash = hashlib.sha256(encryption_key.encode()).hexdigest()

    def _hash_allele(self, locus, allele):
        """Create a secure hash of an allele value"""
        data = f"{self.encryption_key}:{locus}:{allele}"
        return hashlib.sha256(data.encode()).hexdigest()

    def encrypt_profile(self, profile):
        """
        Encrypt a DNA profile
        Each allele is hashed with the locus name
        """
        encrypted = {
            'id': profile['id'],
            'encrypted_markers': {},
            'encryption_timestamp': datetime.now().isoformat(),
            'is_encrypted': True
        }

        for locus, alleles in profile['markers'].items():
            encrypted_alleles = [self._hash_allele(locus, allele) for allele in alleles]
            encrypted['encrypted_markers'][locus] = encrypted_alleles

        return encrypted

    def compute_similarity_encrypted(self, profile1_enc, profile2_enc):
        """
        Compare two encrypted profiles without decrypting
        Returns match score (0.0 to 1.0)
        """
        if not profile1_enc.get('is_encrypted') or not profile2_enc.get('is_encrypted'):
            raise ValueError("Both profiles must be encrypted")

        total_alleles = 0
        matching_alleles = 0

        for locus in profile1_enc['encrypted_markers']:
            if locus not in profile2_enc['encrypted_markers']:
                continue

            alleles1 = set(profile1_enc['encrypted_markers'][locus])
            alleles2 = set(profile2_enc['encrypted_markers'][locus])

            # Count shared encrypted alleles
            shared = len(alleles1.intersection(alleles2))
            matching_alleles += shared
            total_alleles += len(alleles1)

        # Tanabe similarity score
        if total_alleles == 0:
            return 0.0

        score = matching_alleles / total_alleles
        return round(score, 4)

    def verify_encryption_integrity(self, encrypted_profile):
        """Verify that a profile is properly encrypted"""
        required_fields = ['id', 'encrypted_markers', 'is_encrypted']
        return all(field in encrypted_profile for field in required_fields)


class AdvancedDNAEncryption:
    """
    Advanced encryption with privacy-preserving matching
    Simulates homomorphic encryption properties
    """

    def __init__(self):
        self.master_key = self._generate_master_key()
        self.encryption_counter = 0

    def _generate_master_key(self):
        """Generate a master encryption key"""
        import secrets
        return secrets.token_hex(32)

    def encrypt_profile_advanced(self, profile):
        """
        Advanced encryption that allows encrypted comparison
        Uses layered hashing with salt
        """
        self.encryption_counter += 1

        encrypted = {
            'id': profile['id'],
            'encrypted_markers': {},
            'encryption_id': f"ENC_{self.encryption_counter:06d}",
            'timestamp': datetime.now().isoformat(),
            'encryption_level': 'ADVANCED',
            'is_encrypted': True
        }

        for locus, alleles in profile['markers'].items():
            encrypted_alleles = []
            for allele in alleles:
                # Create unique encryption with salt
                salt = hashlib.sha256(f"{locus}{allele}{self.master_key}".encode()).hexdigest()[:16]
                encrypted_value = hashlib.pbkdf2_hmac(
                    'sha256',
                    str(allele).encode(),
                    salt.encode(),
                    100000
                ).hex()
                encrypted_alleles.append({
                    'encrypted_value': encrypted_value,
                    'salt': salt,
                    'locus': locus
                })
            encrypted['encrypted_markers'][locus] = encrypted_alleles

        return encrypted

    def compare_encrypted_advanced(self, profile1, profile2):
        """Advanced comparison of encrypted profiles"""
        # Simplified comparison for demonstration
        match_score = 0.0
        loci_count = len(profile1['encrypted_markers'])

        for locus in profile1['encrypted_markers']:
            if locus in profile2['encrypted_markers']:
                # Check if encrypted values match
                enc1 = set(a['encrypted_value'] for a in profile1['encrypted_markers'][locus])
                enc2 = set(a['encrypted_value'] for a in profile2['encrypted_markers'][locus])

                if enc1.intersection(enc2):
                    match_score += 1

        return round(match_score / loci_count, 4) if loci_count > 0 else 0.0


def demonstrate_encryption():
    """Demonstrate the encryption system"""
    # Sample profile
    sample_profile = {
        'id': 'DEMO_001',
        'markers': {
            'D3S1358': [14, 16],
            'D5S818': [11, 12],
            'D7S820': [8, 10]
        }
    }

    # Basic encryption
    encryptor = SimplifiedDNAEncryption()
    encrypted = encryptor.encrypt_profile(sample_profile)

    print("Original profile:", json.dumps(sample_profile, indent=2))
    print("\nEncrypted profile:", json.dumps(encrypted, indent=2))

    return encrypted

if __name__ == '__main__':
    demonstrate_encryption()
