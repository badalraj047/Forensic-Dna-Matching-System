"""
Forensic DNA Encryption Module
───────────────────────────────
Hash-based privacy-preserving comparison (HE-inspired demo).
Uses SHA-256 keyed hashing so raw allele values are never exposed.
"""

import hashlib
import os
from datetime import datetime


class DNAEncryption:
    """
    Encrypt DNA profiles and compare them without decryption.
    Uses deterministic SHA-256 hashing keyed per locus+allele.
    NOTE: This is a demonstration of privacy-preserving design.
          Production systems would use true HE (e.g. Microsoft SEAL / Paillier).
    """

    def __init__(self, key: str = None):
        self.key = key or os.environ.get('DNA_ENCRYPTION_KEY', 'forensic_key_2025')

    def _hash_allele(self, locus: str, allele) -> str:
        data = f"{self.key}:{locus}:{allele}"
        return hashlib.sha256(data.encode()).hexdigest()

    def encrypt_profile(self, profile: dict) -> dict:
        """Encrypt all markers in a profile."""
        encrypted = {
            'id': profile['id'],
            'encrypted_markers': {},
            'is_encrypted': True,
            'timestamp': datetime.now().isoformat(),
            'region': profile.get('region', 'USA'),
        }
        for locus, alleles in profile.get('markers', {}).items():
            encrypted['encrypted_markers'][locus] = [
                self._hash_allele(locus, a) for a in alleles
            ]
        return encrypted

    def compute_similarity_encrypted(self, enc1: dict, enc2: dict) -> float:
        """
        Tanabe similarity score on encrypted profiles.
        Formula: (2 x shared_hashes) / (total_hashes_in_both)
        Consistent with the plaintext Tanabe formula.
        """
        shared = 0
        total = 0
        for locus, hashes1 in enc1.get('encrypted_markers', {}).items():
            hashes2 = enc2.get('encrypted_markers', {}).get(locus)
            if not hashes2:
                continue
            s1, s2 = set(hashes1), set(hashes2)
            shared += len(s1 & s2)
            total += len(s1) + len(s2)
        if total == 0:
            return 0.0
        return round((2 * shared) / total, 4)

    def verify_integrity(self, encrypted_profile: dict) -> bool:
        """Check that encrypted profile has the required fields."""
        return all(
            k in encrypted_profile
            for k in ('id', 'encrypted_markers', 'is_encrypted')
        )
