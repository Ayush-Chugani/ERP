from typing import ClassVar

from django import forms

from .models import StaffProfessionalContribution
from .selectors import REFERENCES, reference_rows, validate_references


class ContributionForm(forms.ModelForm):
    class Meta:
        model = StaffProfessionalContribution
        exclude = ("staff_activity",)
        widgets: ClassVar[dict] = {
            **{
                name: forms.DateInput(attrs={"type": "date"})
                for name in ("contribution_date", "start_date", "end_date")
            },
            **{
                name: forms.NumberInput(attrs={"min": 0, "max": 65535, "step": 1})
                for name in ("number_of_reviews", "number_of_candidates")
            },
        }

    def __init__(self, *args, actor, parent, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.instance.staff_activity = parent
        for name in REFERENCES:
            field = self.fields[name]
            field.queryset = reference_rows(actor, name, parent.institution_id)
            field.widget = forms.TextInput(
                attrs={"data-autocomplete": name, "aria-label": field.label}
            )
            field.help_text = (
                "Choose an authorized reference using the searchable selector."
            )
        self.fields["professional_contribution_type"].queryset = self.fields[
            "professional_contribution_type"
        ].queryset.filter(is_active=True)

    def _update_errors(self, errors):
        from django.core.exceptions import ValidationError

        if hasattr(errors, "error_dict"):
            errors = ValidationError(
                {
                    k[:-3] if k.endswith("_id") and k[:-3] in self.fields else k: v
                    for k, v in errors.error_dict.items()
                }
            )
        super()._update_errors(errors)

    def _post_clean(self):
        super()._post_clean()
        if not self.errors:
            from django.core.exceptions import ValidationError

            try:
                validate_references(self.actor, self.instance)
            except ValidationError as error:
                self.add_error(None, "; ".join(error.messages))

    def save(self, commit=True):
        raise ValueError("Persist through the transactional contribution service.")
