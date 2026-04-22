from django.db import models
from django.contrib.auth.models import User


class Player(models.Model):

    POSITION_CHOICES = [
        ("GK", "Goalkeeper"),
        ("RB", "Right Back"),
        ("LB", "Left Back"),
        ("CB", "Centre Back"),
        ("DM", "Defensive Midfielder"),
        ("CM", "Central Midfielder"),
        ("AM", "Attacking Midfielder"),
        ("RW", "Right Winger"),
        ("LW", "Left Winger"),
        ("ST", "Striker"),
    ]

    FOOT_CHOICES = [
        ("L", "Left"),
        ("R", "Right"),
        ("B", "Both"),
    ]

    EXPERIENCE_CHOICES = [
        ("YTH", "Youth / Academy"),
        ("AM", "Amateur"),
        ("SEMI", "Semi-Professional"),
        ("PRO", "Professional"),
    ]

    AVAILABILITY_CHOICES = [
        ("WKD", "Weekends"),
        ("WK", "Weekdays"),
        ("EVE", "Evenings"),
        ("ANY", "Any availability"),
    ]

    LONDON_AREA_CHOICES = [
        ("N", "North London"),
        ("NE", "North-East London"),
        ("NW", "North-West London"),
        ("E", "East London"),
        ("SE", "South-East London"),
        ("SW", "South-West London"),
        ("W", "West London"),
        ("S", "South London"),
        ("C", "Central London"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    primary_position = models.CharField(max_length=3, choices=POSITION_CHOICES)
    secondary_position = models.CharField(max_length=3, choices=POSITION_CHOICES, blank=True)
    preferred_foot = models.CharField(max_length=1, choices=FOOT_CHOICES)
    height_cm = models.IntegerField(null=True, blank=True)
    experience_level = models.CharField(max_length=4, choices=EXPERIENCE_CHOICES)
    availability_window = models.CharField(max_length=4, choices=AVAILABILITY_CHOICES)
    locality_area = models.CharField(max_length=2, choices=LONDON_AREA_CHOICES)

    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    bio = models.TextField(blank=True)
    visibility = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username


class Club(models.Model):

    CLUB_DIVISIONS = [
        ("sunday_league", "Sunday League"),
        ("amateur", "Amateur"),
        ("semi_pro", "Semi-Professional"),
        ("academy", "Academy"),
        ("grassroots", "Grassroots"),
    ]

    CONTACT_PREFERENCES = [
        ("email", "Email"),
        ("phone", "Phone"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    division = models.CharField(max_length=30, choices=CLUB_DIVISIONS)
    home_ground = models.CharField(max_length=100)

    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_pref = models.CharField(max_length=20, choices=CONTACT_PREFERENCES)

    last_search_config = models.JSONField(null=True, blank=True)
    last_search_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class ShortlistEntry(models.Model):
    club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name="shortlist_entries")
    player = models.ForeignKey("Player", on_delete=models.CASCADE, related_name="shortlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "player"],
                name="unique_club_player_shortlist"
            )
        ]

    def __str__(self):
        return f"{self.club.name} shortlisted {self.player.user.username}"


class TrialRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("completed", "Completed"),
    ]

    OUTCOME_CHOICES = [
        ("", "Not recorded"),
        ("offered", "Offered a place"),
        ("not_offered", "Not offered a place"),
        ("no_show", "Did not attend"),
    ]

    club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name="trial_requests_sent")
    player = models.ForeignKey("Player", on_delete=models.CASCADE, related_name="trial_requests_received")

    trial_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    attendance = models.BooleanField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, default="")

    def __str__(self):
        return f"Trial: {self.club.name} → {self.player.user.username}"


class TrialFeedback(models.Model):
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

    trial = models.OneToOneField(
        TrialRequest,
        on_delete=models.CASCADE,
        related_name="feedback"
    )

    positional_suitability = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, blank=True)
    work_rate = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, blank=True)
    decision_making = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, blank=True)
    teammate_understanding = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, blank=True)
    physicality = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, blank=True)

    offer_decision = models.CharField(max_length=3, choices=OFFER_CHOICES, blank=True)

    club_comment = models.TextField(blank=True)
    generated_summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.trial.player.user.username} from {self.trial.club.name}"


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ("trial_invitation", "Trial Invitation"),
        ("feedback", "Feedback"),
        ("player_profile", "Player Profile"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
    ]

    REASON_CHOICES = [
        ("suspicious_invitation", "Suspicious invitation"),
        ("inappropriate_trial_details", "Inappropriate trial details"),
        ("suspected_fake_club", "Suspected fake club"),
        ("abusive_communication", "Abusive or unprofessional communication"),
        ("unfair_feedback", "Feedback appears misleading or unfair"),
        ("inappropriate_language", "Inappropriate language"),
        ("suspected_fake_profile", "Suspected fake profile"),
        ("misleading_profile", "Misleading player information"),
        ("inappropriate_profile_content", "Inappropriate profile content"),
        ("abusive_behaviour", "Abusive behaviour"),
        ("other", "Other"),
    ]

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_reports"
    )

    resolver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_reports"
    )

    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    reason = models.CharField(max_length=40, choices=REASON_CHOICES)
    details = models.TextField(blank=True)

    trial_request = models.ForeignKey(
        TrialRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports"
    )

    feedback = models.ForeignKey(
        TrialFeedback,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports"
    )

    reported_player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_against"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_report_type_display()} report by {self.reporter.username}"