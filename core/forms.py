from django import forms


class TrialOutcomeFeedbackForm(forms.Form):
    ATTENDANCE_CHOICES = [
        ("attended", "Attended"),
        ("did_not_attend", "Did not attend"),
    ]

    PERFORMANCE_CHOICES = [
        ("strong", "Strong"),
        ("satisfactory", "Satisfactory"),
        ("needs_improvement", "Needs improvement"),
        ("not_good", "Not good"),
    ]

    OFFER_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
    ]

    attendance = forms.ChoiceField(
        choices=ATTENDANCE_CHOICES,
        widget=forms.RadioSelect
    )

    positional_suitability = forms.ChoiceField(choices=PERFORMANCE_CHOICES, required=False)
    work_rate = forms.ChoiceField(choices=PERFORMANCE_CHOICES, required=False)
    decision_making = forms.ChoiceField(choices=PERFORMANCE_CHOICES, required=False)
    teammate_understanding = forms.ChoiceField(choices=PERFORMANCE_CHOICES, required=False)
    physicality = forms.ChoiceField(choices=PERFORMANCE_CHOICES, required=False)

    offer_decision = forms.ChoiceField(
        choices=OFFER_CHOICES,
        required=False,
        widget=forms.RadioSelect
    )

    club_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4})
    )

    def clean(self):
        cleaned_data = super().clean()
        attendance = cleaned_data.get("attendance")

        if attendance == "attended":
            required_fields = [
                "positional_suitability",
                "work_rate",
                "decision_making",
                "teammate_understanding",
                "physicality",
                "offer_decision",
            ]

            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required if the player attended the trial.")

        return cleaned_data


class ReportForm(forms.Form):
    reason = forms.ChoiceField(choices=[])
    details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args, reason_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].choices = reason_choices or []