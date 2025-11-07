import json
from datetime import datetime

class DNAMatcher:
    """
    DNA Profile Matching System
    Implements Tanabe similarity score for STR profile comparison
    """

    def __init__(self, threshold=0.80):
        """
        Initialize matcher
        threshold: minimum score for match (0.80 = 80% similarity)
        """
        self.threshold = threshold
        self.match_history = []

    def calculate_tanabe_score(self, profile1, profile2):
        """
        Calculate Tanabe similarity score between two profiles
        Formula: (2 × shared alleles) / (total alleles in both profiles)
        Returns score between 0.0 and 1.0
        """
        if 'markers' not in profile1 or 'markers' not in profile2:
            raise ValueError("Profiles must have 'markers' field")

        shared_alleles = 0
        total_alleles = 0
        loci_matches = {}

        for locus in profile1['markers']:
            if locus not in profile2['markers']:
                continue

            alleles1 = set(profile1['markers'][locus])
            alleles2 = set(profile2['markers'][locus])

            # Count shared alleles at this locus
            shared = len(alleles1.intersection(alleles2))
            shared_alleles += shared
            total_alleles += len(alleles1) + len(alleles2)

            # Track per-locus match
            loci_matches[locus] = {
                'alleles1': list(alleles1),
                'alleles2': list(alleles2),
                'shared': shared,
                'match': shared > 0
            }

        # Calculate overall score
        if total_alleles == 0:
            return 0.0, loci_matches

        score = (2 * shared_alleles) / total_alleles
        return round(score, 4), loci_matches

    def match_single_profile(self, query_profile, target_profile):
        """
        Match a single query profile against a target profile
        Returns detailed match result
        """
        score, loci_details = self.calculate_tanabe_score(query_profile, target_profile)

        # Determine match classification
        if score >= 0.95:
            match_status = "DEFINITE MATCH"
            confidence = "VERY HIGH"
        elif score >= self.threshold:
            match_status = "PROBABLE MATCH"
            confidence = "HIGH"
        elif score >= 0.50:
            match_status = "PARTIAL MATCH"
            confidence = "MEDIUM"
        else:
            match_status = "NO MATCH"
            confidence = "LOW"

        result = {
            'query_id': query_profile['id'],
            'target_id': target_profile['id'],
            'similarity_score': score,
            'match_status': match_status,
            'confidence': confidence,
            'threshold': self.threshold,
            'loci_count': len(loci_details),
            'timestamp': datetime.now().isoformat()
        }

        return result

    def match_against_database(self, query_profile, database_profiles, top_n=10):
        """
        Match a query profile against a database of profiles
        Returns top N matches sorted by similarity score
        """
        results = []

        for db_profile in database_profiles:
            result = self.match_single_profile(query_profile, db_profile)
            results.append(result)

        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Record match in history
        self.match_history.append({
            'query_id': query_profile['id'],
            'timestamp': datetime.now().isoformat(),
            'database_size': len(database_profiles),
            'top_score': results[0]['similarity_score'] if results else 0.0
        })

        # Return only matches above threshold
        matches = [r for r in results if r['similarity_score'] >= self.threshold]

        return matches[:top_n] if matches else []

    def get_statistics(self):
        """Get matching statistics"""
        if not self.match_history:
            return {"message": "No matches performed yet"}

        return {
            'total_matches': len(self.match_history),
            'threshold': self.threshold,
            'last_match': self.match_history[-1]
        }


class EncryptedDNAMatcher:
    """
    Matcher for encrypted DNA profiles
    Performs comparison without decryption
    """

    def __init__(self, encryption_handler, threshold=0.80):
        self.encryption_handler = encryption_handler
        self.threshold = threshold

    def match_encrypted_profiles(self, query_encrypted, database_encrypted):
        """
        Match encrypted query against encrypted database
        Privacy-preserving - raw DNA never exposed
        """
        results = []

        for db_profile in database_encrypted:
            # Compare using encryption handler
            score = self.encryption_handler.compute_similarity_encrypted(
                query_encrypted, 
                db_profile
            )

            if score >= self.threshold:
                results.append({
                    'query_id': query_encrypted['id'],
                    'target_id': db_profile['id'],
                    'encrypted_score': score,
                    'match_status': 'ENCRYPTED MATCH' if score >= 0.95 else 'ENCRYPTED PARTIAL',
                    'privacy_preserved': True,
                    'timestamp': datetime.now().isoformat()
                })

        results.sort(key=lambda x: x['encrypted_score'], reverse=True)
        return results


def demonstrate_matching():
    """Demonstrate the matching system"""
    # Create sample profiles
    profile1 = {
        'id': 'SUSPECT_001',
        'markers': {
            'D3S1358': [14, 16],
            'D5S818': [11, 12],
            'D7S820': [8, 10],
            'vWA': [16, 18]
        }
    }

    profile2 = {
        'id': 'CRIME_SCENE_001',
        'markers': {
            'D3S1358': [14, 16],  # Perfect match
            'D5S818': [11, 13],   # Partial match
            'D7S820': [8, 10],    # Perfect match
            'vWA': [16, 19]       # Partial match
        }
    }

    matcher = DNAMatcher(threshold=0.70)
    result = matcher.match_single_profile(profile1, profile2)

    print("Match Result:")
    print(json.dumps(result, indent=2))

    return result

if __name__ == '__main__':
    demonstrate_matching()
