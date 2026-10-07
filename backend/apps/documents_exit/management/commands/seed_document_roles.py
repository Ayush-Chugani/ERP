from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create capability groups only. No user assignment, activation or certificate type seeding."

    def handle(self, *args, **options):
        roles = {
            "Document Student": [
                "view_own_document",
                "upload_own_document",
                "request_certificate",
                "access_restricted_file",
            ],
            "Document Verifier": [
                "view_documents",
                "verify_document",
                "access_restricted_file",
            ],
            "Certificate Officer": [
                "view_certificates",
                "review_certificate",
                "approve_certificate",
                "issue_certificate",
                "access_restricted_file",
            ],
            "Exit Officer": ["view_exit", "finalize_exit"],
        }
        for name, caps in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="documents_exit", codename__in=caps
                )
            )
        self.stdout.write(
            "Document capability groups ready; exit officers also require owning enrolment lifecycle authorization."
        )
