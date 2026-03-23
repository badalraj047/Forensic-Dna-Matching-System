"""
Forensic DNA Matching Engine
─────────────────────────────
• Tanabe similarity score with per-locus detail
• Kinship / familial relationship detection
• Random Match Probability (RMP) using population allele frequencies
"""

import math
from datetime import datetime

# ─────────────────────────────────────────────
# CODIS 20 Core STR Loci & allele ranges
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# Population allele frequency tables (simplified)
# Based on published forensic population genetics data.
# Frequencies are approximate for demonstration;
# real labs use NIST 1036 or similar validated tables.
# ─────────────────────────────────────────────
_MINIMUM_FREQ = 0.01  # Floor for unseen alleles (5/2N rule)

ALLELE_FREQUENCIES = {
    'General': {
        'CSF1PO':   {7: 0.03, 8: 0.04, 9: 0.06, 10: 0.27, 11: 0.28, 12: 0.33, 13: 0.06, 14: 0.02},
        'D3S1358':  {12: 0.01, 13: 0.02, 14: 0.12, 15: 0.28, 16: 0.25, 17: 0.20, 18: 0.10, 19: 0.02},
        'D5S818':   {7: 0.02, 8: 0.03, 9: 0.06, 10: 0.08, 11: 0.34, 12: 0.30, 13: 0.15, 14: 0.02},
        'D7S820':   {7: 0.02, 8: 0.15, 9: 0.10, 10: 0.26, 11: 0.22, 12: 0.18, 13: 0.05, 14: 0.02},
        'D8S1179':  {8: 0.02, 9: 0.03, 10: 0.08, 11: 0.07, 12: 0.14, 13: 0.30, 14: 0.18, 15: 0.12, 16: 0.04, 17: 0.02},
        'D13S317':  {8: 0.12, 9: 0.08, 10: 0.06, 11: 0.28, 12: 0.30, 13: 0.10, 14: 0.05, 15: 0.01},
        'D16S539':  {8: 0.02, 9: 0.12, 10: 0.08, 11: 0.28, 12: 0.22, 13: 0.18, 14: 0.08, 15: 0.02},
        'D18S51':   {10: 0.02, 11: 0.03, 12: 0.08, 13: 0.10, 14: 0.16, 15: 0.14, 16: 0.12, 17: 0.12, 18: 0.10, 19: 0.06, 20: 0.04, 21: 0.02, 22: 0.01},
        'D21S11':   {24: 0.01, 25: 0.02, 27: 0.05, 28: 0.14, 29: 0.20, 30: 0.24, 31: 0.14, 32: 0.10, 33: 0.06, 34: 0.03, 35: 0.01},
        'FGA':      {18: 0.03, 19: 0.07, 20: 0.10, 21: 0.16, 22: 0.18, 23: 0.16, 24: 0.14, 25: 0.10, 26: 0.04, 27: 0.02},
        'TH01':     {5: 0.02, 6: 0.22, 7: 0.18, 8: 0.12, 9: 0.24, 10: 0.18, 11: 0.04},
        'TPOX':     {6: 0.02, 7: 0.04, 8: 0.50, 9: 0.12, 10: 0.08, 11: 0.22, 12: 0.02},
        'vWA':      {13: 0.02, 14: 0.08, 15: 0.10, 16: 0.20, 17: 0.26, 18: 0.20, 19: 0.10, 20: 0.04},
        'D1S1656':  {10: 0.02, 11: 0.06, 12: 0.10, 13: 0.14, 14: 0.16, 15: 0.18, 16: 0.14, 17: 0.12, 18: 0.06, 19: 0.02},
        'D2S441':   {9: 0.03, 10: 0.15, 11: 0.30, 12: 0.16, 13: 0.08, 14: 0.18, 15: 0.08, 16: 0.02},
        'D2S1338':  {16: 0.04, 17: 0.12, 18: 0.08, 19: 0.14, 20: 0.14, 21: 0.06, 22: 0.08, 23: 0.14, 24: 0.10, 25: 0.06, 26: 0.04},
        'D10S1248': {10: 0.04, 11: 0.06, 12: 0.10, 13: 0.26, 14: 0.24, 15: 0.16, 16: 0.08, 17: 0.04, 18: 0.02},
        'D12S391':  {15: 0.02, 16: 0.04, 17: 0.08, 18: 0.18, 19: 0.20, 20: 0.16, 21: 0.14, 22: 0.10, 23: 0.06, 24: 0.02},
        'D19S433':  {10: 0.04, 11: 0.06, 12: 0.10, 13: 0.22, 14: 0.24, 15: 0.18, 16: 0.12, 17: 0.04},
        'D22S1045': {10: 0.04, 11: 0.14, 12: 0.08, 13: 0.06, 14: 0.10, 15: 0.18, 16: 0.22, 17: 0.14, 18: 0.04},
    }
}

_REGION_MAP = {
    'USA': 'General', 'India': 'General', 'Europe': 'General',
    'Canada': 'General', 'Australia': 'General', 'UK': 'General',
    'Japan': 'General', 'China': 'General',
}


def _get_freq(locus: str, allele: int, region: str = 'General') -> float:
    table_key = _REGION_MAP.get(region, 'General')
    table = ALLELE_FREQUENCIES.get(table_key, ALLELE_FREQUENCIES['General'])
    locus_freqs = table.get(locus, {})
    return locus_freqs.get(allele, _MINIMUM_FREQ)


# ═══════════════════════════════════════════════
# 1.  TANABE SIMILARITY SCORE (with locus detail)
# ═══════════════════════════════════════════════

def calculate_tanabe_score(profile1: dict, profile2: dict) -> dict:
    """
    Tanabe score with per-locus breakdown.
    Formula: Score = (2 x shared_alleles) / (total_alleles_in_both)
    """
    markers1 = profile1.get('markers', {})
    markers2 = profile2.get('markers', {})

    shared_alleles = 0
    total_alleles = 0
    loci_details = []

    for locus in CODIS_LOCI:
        a1 = markers1.get(locus)
        a2 = markers2.get(locus)
        if a1 is None or a2 is None:
            continue

        set1 = set(a1)
        set2 = set(a2)
        shared = len(set1 & set2)
        shared_alleles += shared
        total_alleles += len(set1) + len(set2)

        if shared == 2:
            locus_status = 'full'
        elif shared == 1:
            locus_status = 'partial'
        else:
            locus_status = 'mismatch'

        loci_details.append({
            'locus': locus,
            'alleles1': sorted(a1),
            'alleles2': sorted(a2),
            'shared': shared,
            'status': locus_status,
        })

    score = round((2 * shared_alleles) / total_alleles, 4) if total_alleles > 0 else 0.0

    if score >= 0.95:
        status = 'DEFINITE MATCH'
    elif score >= 0.80:
        status = 'PROBABLE MATCH'
    elif score >= 0.50:
        status = 'PARTIAL MATCH'
    else:
        status = 'NO MATCH'

    return {
        'score': score,
        'status': status,
        'loci_compared': len(loci_details),
        'shared_alleles': shared_alleles,
        'total_alleles': total_alleles,
        'loci_details': loci_details,
    }


def calculate_tanabe_score_simple(profile1: dict, profile2: dict) -> float:
    """Lightweight version returning just the float score (for bulk scans)."""
    markers1 = profile1.get('markers', {})
    markers2 = profile2.get('markers', {})
    shared = 0
    total = 0
    for locus in markers1:
        if locus in markers2:
            s1, s2 = set(markers1[locus]), set(markers2[locus])
            shared += len(s1 & s2)
            total += len(s1) + len(s2)
    return round((2 * shared) / total, 4) if total > 0 else 0.0


# ═══════════════════════════════════════════════
# 2.  KINSHIP / FAMILIAL MATCHING
# ═══════════════════════════════════════════════

def calculate_kinship_score(profile1: dict, profile2: dict) -> dict:
    """
    Detect familial relationships via IBS (Identity By State).
    Parent-child: share >= 1 allele at every locus (obligate allele).
    Siblings: avg IBS ~ 1.5.   Unrelated: avg IBS ~ 0.9-1.0.
    """
    markers1 = profile1.get('markers', {})
    markers2 = profile2.get('markers', {})

    loci_ibs = []
    loci_with_share = 0
    total_loci = 0

    for locus in CODIS_LOCI:
        a1, a2 = markers1.get(locus), markers2.get(locus)
        if a1 is None or a2 is None:
            continue
        total_loci += 1
        ibs = len(set(a1) & set(a2))
        loci_ibs.append({'locus': locus, 'ibs': ibs})
        if ibs >= 1:
            loci_with_share += 1

    if total_loci == 0:
        return {'relationship': 'Unrelated', 'ibs_mean': 0.0,
                'obligate_share': 0.0, 'confidence': 'LOW', 'loci_ibs': []}

    obligate_share = round(loci_with_share / total_loci, 4)
    ibs_mean = round(sum(l['ibs'] for l in loci_ibs) / total_loci, 4)

    if obligate_share >= 0.98 and ibs_mean >= 1.0:
        relationship = 'Parent-Child'
        confidence = 'HIGH' if obligate_share == 1.0 else 'MEDIUM'
    elif ibs_mean >= 1.30 and obligate_share >= 0.85:
        relationship = 'Sibling'
        confidence = 'HIGH' if ibs_mean >= 1.45 else 'MEDIUM'
    elif ibs_mean >= 1.10 and obligate_share >= 0.75:
        relationship = 'Possible Relative'
        confidence = 'LOW'
    else:
        relationship = 'Unrelated'
        confidence = 'HIGH' if ibs_mean < 0.90 else 'MEDIUM'

    return {
        'relationship': relationship,
        'ibs_mean': ibs_mean,
        'obligate_share': obligate_share,
        'confidence': confidence,
        'loci_ibs': loci_ibs,
    }


# ═══════════════════════════════════════════════
# 3.  RANDOM MATCH PROBABILITY (RMP)
# ═══════════════════════════════════════════════

def calculate_rmp(profile: dict, region: str = 'General') -> dict:
    """
    Random Match Probability using Hardy-Weinberg equilibrium.
    Heterozygous: P = 2 x freq(a) x freq(b)
    Homozygous:   P = freq(a)^2
    Product rule:  multiply across all loci.
    """
    markers = profile.get('markers', {})
    log_sum = 0.0
    loci_probs = []

    for locus in CODIS_LOCI:
        alleles = markers.get(locus)
        if alleles is None or len(alleles) != 2:
            continue

        a1, a2 = alleles[0], alleles[1]
        f1 = _get_freq(locus, a1, region)
        f2 = _get_freq(locus, a2, region)

        prob = (f1 * f1) if a1 == a2 else (2.0 * f1 * f2)
        prob = max(prob, 1e-20)
        log_sum += math.log10(prob)

        loci_probs.append({
            'locus': locus,
            'alleles': sorted([a1, a2]),
            'freq1': round(f1, 4),
            'freq2': round(f2, 4),
            'genotype_prob': round(prob, 8),
            'is_homozygous': a1 == a2,
        })

    rmp = 10 ** log_sum if log_sum > -300 else 0.0

    if rmp > 0:
        one_in = 1.0 / rmp
        if one_in >= 1e12:
            rmp_formatted = f"1 in {one_in:.1e} (trillion+)"
        elif one_in >= 1e9:
            rmp_formatted = f"1 in {one_in / 1e9:.1f} billion"
        elif one_in >= 1e6:
            rmp_formatted = f"1 in {one_in / 1e6:.1f} million"
        elif one_in >= 1e3:
            rmp_formatted = f"1 in {one_in / 1e3:.1f} thousand"
        else:
            rmp_formatted = f"1 in {one_in:.0f}"
    else:
        rmp_formatted = "Extremely rare (< 1e-300)"

    return {
        'rmp': rmp,
        'rmp_formatted': rmp_formatted,
        'log10_rmp': round(log_sum, 2),
        'loci_counted': len(loci_probs),
        'region': region,
        'loci_probs': loci_probs,
    }


# ═══════════════════════════════════════════════
# 4.  FULL ANALYSIS (convenience wrapper)
# ═══════════════════════════════════════════════

def full_match_analysis(query: dict, target: dict, region: str = 'General') -> dict:
    return {
        'tanabe': calculate_tanabe_score(query, target),
        'kinship': calculate_kinship_score(query, target),
        'rmp': calculate_rmp(target, region=region),
    }


# ═══════════════════════════════════════════════
# 5.  MATCHER CLASS (for import by app.py)
# ═══════════════════════════════════════════════

class DNAMatcher:
    def __init__(self, threshold=0.80):
        self.threshold = threshold
        self.match_history = []

    def match_against_database(self, query, database, top_n=10):
        results = []
        for target in database:
            if target.get('id') == query.get('id'):
                continue
            score = calculate_tanabe_score_simple(query, target)
            if score >= self.threshold:
                results.append({'target': target, 'score': score})
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]


if __name__ == '__main__':
    import json
    p1 = {'id': 'TEST_001', 'markers': {l: [ALLELE_RANGES[l][0], ALLELE_RANGES[l][1]] for l in CODIS_LOCI}}
    print("RMP:", calculate_rmp(p1)['rmp_formatted'])
