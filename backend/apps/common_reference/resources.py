from . import models as m
# Explicit API contract: model, path, writable fields, direct parent, parent label.
RESOURCES = (
 (m.Country,"countries",("iso_code","country_name","is_active"),None,None),
 (m.State,"states",("country_id","state_code","state_name","is_active"),"country","country_name"),
 (m.Gender,"genders",("gender_code","gender_name","is_active"),None,None),
 (m.BloodGroup,"blood-groups",("blood_group_code","is_active"),None,None),
 (m.Religion,"religions",("religion_code","religion_name","is_active"),None,None),
 (m.SocialCategory,"social-categories",("category_code","category_name","is_active"),None,None),
 (m.Caste,"castes",("social_category_id","caste_code","caste_name","is_active"),"social_category","category_name"),
 (m.SubCaste,"sub-castes",("caste_id","sub_caste_code","sub_caste_name","is_active"),"caste","caste_name"),
 (m.AdmissionCategory,"admission-categories",("category_code","category_name","description","is_active"),None,None),
 (m.DocumentType,"document-types",("document_code","document_name","requires_verification","is_active"),None,None),
)
