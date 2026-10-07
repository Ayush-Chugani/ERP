from typing import ClassVar

from django import forms

from .models import EvidenceDocument
from .services import METADATA


class EvidenceMetadataForm(forms.ModelForm):
    class Meta:
        model = EvidenceDocument
        fields = tuple(name.removesuffix("_id") for name in METADATA)
        widgets: ClassVar[dict] = {
            name: forms.DateInput(attrs={"type": "date"})
            for name in ("document_issue_date", "expiry_date")
        }

    def save(self, commit=True):
        raise ValueError("Use the authorized transactional evidence service.")
