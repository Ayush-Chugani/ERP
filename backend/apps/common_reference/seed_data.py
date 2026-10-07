"""Small application baseline, not a comprehensive official catalogue."""
BASELINE = (
    ('countries', {'iso_code': 'IN'}, {'country_name': 'India'}),
    ('states', {'country_id': {'iso_code': 'IN'}, 'state_code': 'MH'}, {'state_name': 'Maharashtra'}),
    *(( 'blood-groups', {'blood_group_code': code}, {}) for code in ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
)
# Explicitly synthetic and opt-in; never loaded by the baseline command alone.
DEMONSTRATION = (
    ('document-types', {'document_code': 'DEMO_DOCUMENT'}, {'document_name': 'Demonstration document', 'requires_verification': False}),
)

# Local application codes; names sourced from Census C-01 Karnataka and the
# Karnataka Directorate of Minorities. These rows confer no reservation status.
KARNATAKA_SOCIAL_CATEGORIES = (
    ('KA_CAT1', 'Karnataka Category 1'),
    ('KA_2A', 'Karnataka Category 2A'),
    ('KA_2B', 'Karnataka Category 2B'),
    ('KA_3A', 'Karnataka Category 3A'),
    ('KA_3B', 'Karnataka Category 3B'),
    ('KA_SC', 'Karnataka Scheduled Caste'),
    ('KA_ST', 'Karnataka Scheduled Tribe'),
)
# KEA UGCET-2026 bulletin, 16 January 2026, pp. 6, 8 and 51.
# KA_* are local, jurisdiction-qualified keys, not KEA seat-matrix codes.
# General Merit is an admission category, not a caste. Internal SC categories
# are certificate claims; this catalogue does not assign castes to them.
KARNATAKA_ADMISSION_CATEGORIES = KARNATAKA_SOCIAL_CATEGORIES + (
    ('KA_GM', 'Karnataka General Merit'),
    ('KA_SCA', 'Karnataka Scheduled Caste - Internal Category A'),
    ('KA_SCB', 'Karnataka Scheduled Caste - Internal Category B'),
    ('KA_SCC', 'Karnataka Scheduled Caste - Internal Category C'),
)
KARNATAKA = (
    ('states', {'country_id': {'iso_code': 'IN'}, 'state_code': 'KA'}, {'state_name': 'Karnataka'}),
    *(( 'religions', {'religion_name': name}, {'religion_code': code}) for code, name in (
        ('HINDU', 'Hindu'), ('MUSLIM', 'Muslim'), ('CHRISTIAN', 'Christian'),
        ('SIKH', 'Sikh'), ('BUDDHIST', 'Buddhist'), ('JAIN', 'Jain'), ('PARSI', 'Parsi'),
    )),
    *(('social-categories', {'category_code': code}, {'category_name': name})
      for code, name in KARNATAKA_SOCIAL_CATEGORIES),
    *(('admission-categories', {'category_code': code}, {
        'category_name': name,
        'description': 'Karnataka education/admission reference label (KEA UGCET-2026 bulletin). '
                       'Eligibility requires applicable rules and verified certificates; no automatic entitlement.',
    }) for code, name in KARNATAKA_ADMISSION_CATEGORIES),
)
