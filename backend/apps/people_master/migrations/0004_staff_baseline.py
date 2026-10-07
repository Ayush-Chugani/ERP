from django.db import migrations

DATA = [
    (
        "StaffType",
        "type_code",
        None,
        [
            {
                "description": "Academic and teaching personnel",
                "type_code": "TEACHING",
                "type_name": "Teaching",
            },
            {
                "description": "Administrative, technical, support and service personnel",
                "type_code": "NON_TEACHING",
                "type_name": "Non-Teaching",
            },
        ],
    ),
    (
        "StaffCategory",
        "category_code",
        ("staff_type_id", "StaffType", "type_code"),
        [
            {
                "category_code": "TEACHING_STAFF",
                "category_name": "Teaching Staff",
                "description": "Faculty and other personnel engaged in teaching",
                "staff_type_id": "TEACHING",
            },
            {
                "category_code": "OFFICE_STAFF",
                "category_name": "Office Staff",
                "description": "Administrative and office personnel",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "EXAM_SECTION_STAFF",
                "category_name": "Examination Section Staff",
                "description": "Personnel working in the examination section",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "LIBRARY_STAFF",
                "category_name": "Library Staff",
                "description": "Library professional and support personnel",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "MENIAL_STAFF",
                "category_name": "Menial Staff",
                "description": "Institutional support and menial personnel",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "INTERNAL_SECURITY",
                "category_name": "Internal Security Staff",
                "description": "Security personnel directly engaged by the institution",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "AGENCY_SECURITY",
                "category_name": "Security Staff - External Agency",
                "description": "Security personnel supplied by an external agency",
                "staff_type_id": "NON_TEACHING",
            },
            {
                "category_code": "AGENCY_HOUSEKEEPING",
                "category_name": "Housekeeping Staff - External Agency",
                "description": "Housekeeping personnel supplied by an external agency",
                "staff_type_id": "NON_TEACHING",
            },
        ],
    ),
    (
        "EmploymentSource",
        "source_code",
        None,
        [
            {
                "description": "Person directly engaged by the institution",
                "is_external": False,
                "source_code": "INSTITUTION",
                "source_name": "Institution Employee",
            },
            {
                "description": "Person supplied by a contracted external agency",
                "is_external": True,
                "source_code": "EXTERNAL_AGENCY",
                "source_name": "External Agency",
            },
        ],
    ),
    (
        "Designation",
        "designation_code",
        ("staff_category_id", "StaffCategory", "category_code"),
        [
            {
                "designation_code": "PROFESSOR",
                "designation_name": "Professor",
                "staff_category_id": "TEACHING_STAFF",
            },
            {
                "designation_code": "ASSOC_PROFESSOR",
                "designation_name": "Associate Professor",
                "staff_category_id": "TEACHING_STAFF",
            },
            {
                "designation_code": "ASST_PROFESSOR",
                "designation_name": "Assistant Professor",
                "staff_category_id": "TEACHING_STAFF",
            },
            {
                "designation_code": "OFFICE_SUPERINTENDENT",
                "designation_name": "Office Superintendent",
                "staff_category_id": "OFFICE_STAFF",
            },
            {
                "designation_code": "OFFICE_ASSISTANT",
                "designation_name": "Office Assistant",
                "staff_category_id": "OFFICE_STAFF",
            },
            {
                "designation_code": "EXAM_SUPERINTENDENT",
                "designation_name": "Examination Superintendent",
                "staff_category_id": "EXAM_SECTION_STAFF",
            },
            {
                "designation_code": "EXAM_ASSISTANT",
                "designation_name": "Examination Assistant",
                "staff_category_id": "EXAM_SECTION_STAFF",
            },
            {
                "designation_code": "LIBRARIAN",
                "designation_name": "Librarian",
                "staff_category_id": "LIBRARY_STAFF",
            },
            {
                "designation_code": "ASST_LIBRARIAN",
                "designation_name": "Assistant Librarian",
                "staff_category_id": "LIBRARY_STAFF",
            },
            {
                "designation_code": "ATTENDER",
                "designation_name": "Attender",
                "staff_category_id": "MENIAL_STAFF",
            },
            {
                "designation_code": "INTERNAL_SECURITY_GUARD",
                "designation_name": "Security Guard",
                "staff_category_id": "INTERNAL_SECURITY",
            },
            {
                "designation_code": "AGENCY_SECURITY_GUARD",
                "designation_name": "Security Guard",
                "staff_category_id": "AGENCY_SECURITY",
            },
            {
                "designation_code": "HOUSEKEEPING_STAFF",
                "designation_name": "Housekeeping Staff",
                "staff_category_id": "AGENCY_HOUSEKEEPING",
            },
        ],
    ),
]


def seed(apps, schema_editor):
    for model_name, key, parent, rows in DATA:
        model = apps.get_model("people_master", model_name)
        for original in rows:
            values = dict(original)
            if parent:
                field, parent_model, parent_key = parent
                values[field] = (
                    apps.get_model("people_master", parent_model)
                    .objects.using(schema_editor.connection.alias)
                    .get(**{parent_key: values[field]})
                    .pk
                )
            natural = {key: values.pop(key)}
            model.objects.using(schema_editor.connection.alias).get_or_create(
                **natural, defaults=values
            )


# Existing administrator data cannot be distinguished safely on reversal.
# Preserve reference seeds; their schema is reversed only with the table migrations.
class Migration(migrations.Migration):
    dependencies = [("people_master", "0003_assignment_ownership")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
