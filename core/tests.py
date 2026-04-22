from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Club,
    Player,
    Report,
    ShortlistEntry,
    TrialFeedback,
    TrialRequest,
)


def aware_dt(year=2026, month=4, day=25, hour=18, minute=0):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


def create_player(username, password="testpass123", **overrides):
    user = User.objects.create_user(username=username, password=password)

    defaults = {
        "primary_position": "CM",
        "secondary_position": "AM",
        "preferred_foot": "R",
        "height_cm": 180,
        "experience_level": "AM",
        "availability_window": "ANY",
        "locality_area": "C",
        "contact_email": f"{username}@example.com",
        "contact_phone": "",
        "bio": f"{username} bio",
        "visibility": True,
    }
    defaults.update(overrides)

    player = Player.objects.create(user=user, **defaults)
    return user, player


def create_club(username, name=None, password="testpass123", **overrides):
    user = User.objects.create_user(username=username, password=password)

    defaults = {
        "name": name or username,
        "division": "amateur",
        "home_ground": "Test Ground",
        "contact_email": f"{username}@club.com",
        "contact_phone": "07111111111",
        "contact_pref": "email",
    }
    defaults.update(overrides)

    club = Club.objects.create(user=user, **defaults)
    return user, club


class AuthenticationAndValidationTests(TestCase):
    """Tests for early system behaviour: registration, validation, and role access."""

    def setUp(self):
        self.player_user, self.player = create_player("playerauth")
        self.club_user, self.club = create_club("clubauth", name="Club Auth")

    def test_registration_rejects_duplicate_username(self):
        User.objects.create_user(username="takenuser", password="testpass123")

        response = self.client.post(
            reverse("register"),
            {
                "username": "takenuser",
                "password": "testpass123",
                "role": "player",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username already exists")

    def test_player_profile_requires_private_email(self):
        self.client.login(username="playerauth", password="testpass123")

        response = self.client.post(
            reverse("player_profile"),
            {
                "primary_position": "CM",
                "secondary_position": "AM",
                "preferred_foot": "R",
                "height_cm": 180,
                "experience_level": "AM",
                "availability_window": "ANY",
                "locality_area": "C",
                "contact_email": "",
                "contact_phone": "",
                "bio": "Updated bio",
                "visibility": "on",
            },
            follow=True,
        )

        self.player.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private email is required.")
        self.assertEqual(self.player.contact_email, "playerauth@example.com")

    def test_club_profile_requires_phone_number(self):
        self.client.login(username="clubauth", password="testpass123")

        response = self.client.post(
            reverse("club_profile"),
            {
                "name": "Club Auth",
                "division": "amateur",
                "home_ground": "Test Ground",
                "contact_email": "clubauth@club.com",
                "contact_phone": "",
                "contact_pref": "email",
            },
            follow=True,
        )

        self.club.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Club phone number is required.")
        self.assertEqual(self.club.contact_phone, "07111111111")

    def test_player_cannot_use_existing_club_email(self):
        self.client.login(username="playerauth", password="testpass123")

        response = self.client.post(
            reverse("player_profile"),
            {
                "primary_position": "CM",
                "secondary_position": "AM",
                "preferred_foot": "R",
                "height_cm": 180,
                "experience_level": "AM",
                "availability_window": "ANY",
                "locality_area": "C",
                "contact_email": self.club.contact_email,
                "contact_phone": "",
                "bio": "Updated bio",
                "visibility": "on",
            },
            follow=True,
        )

        self.player.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That email address is already being used by another account.")
        self.assertEqual(self.player.contact_email, "playerauth@example.com")

    def test_club_cannot_use_existing_player_email(self):
        self.client.login(username="clubauth", password="testpass123")

        response = self.client.post(
            reverse("club_profile"),
            {
                "name": "Club Auth",
                "division": "amateur",
                "home_ground": "Test Ground",
                "contact_email": self.player.contact_email,
                "contact_phone": "07111111111",
                "contact_pref": "email",
            },
            follow=True,
        )

        self.club.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That email address is already being used by another account.")
        self.assertEqual(self.club.contact_email, "clubauth@club.com")

    def test_player_cannot_access_club_shortlist(self):
        self.client.login(username="playerauth", password="testpass123")

        response = self.client.get(reverse("club_shortlist"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("home"))


class SearchRankingAndShortlistTests(TestCase):
    """Tests for ranked search, shortlist behaviour, and suggestion logic."""

    def setUp(self):
        self.club_user, self.club = create_club("rankclub", name="Ranking Club")
        self.trial_dt_1 = aware_dt(2026, 4, 15, 18, 0)
        self.trial_dt_2 = aware_dt(2026, 4, 20, 18, 0)

        self.gk1_user, self.gk1 = create_player(
            "gk_west",
            primary_position="GK",
            secondary_position="CB",
            preferred_foot="R",
            height_cm=185,
            experience_level="YTH",
            availability_window="ANY",
            locality_area="W",
            bio="West London goalkeeper",
        )

        self.gk2_user, self.gk2 = create_player(
            "gk_nw",
            primary_position="GK",
            secondary_position="CB",
            preferred_foot="R",
            height_cm=183,
            experience_level="YTH",
            availability_window="ANY",
            locality_area="NW",
            bio="North West London goalkeeper",
        )

        self.am_user, self.am = create_player(
            "am_central",
            primary_position="AM",
            secondary_position="CM",
            preferred_foot="L",
            height_cm=178,
            experience_level="AM",
            availability_window="EVE",
            locality_area="C",
            bio="Central London attacking midfielder",
        )

        self.hidden_user, self.hidden_player = create_player(
            "hiddenplayer",
            primary_position="CM",
            secondary_position="AM",
            preferred_foot="L",
            height_cm=175,
            experience_level="AM",
            availability_window="ANY",
            locality_area="E",
            bio="Hidden player",
            visibility=False,
        )

    def test_ranked_search_returns_players_with_same_primary_position_only(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "YTH",
                "availability": "ANY",
                "locality": "W",
                "experience_priority": "medium",
                "availability_priority": "high",
                "locality_priority": "high",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gk_west")
        self.assertContains(response, "gk_nw")
        self.assertNotContains(response, "am_central")

    def test_ranked_search_orders_better_locality_match_first(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "YTH",
                "availability": "ANY",
                "locality": "W",
                "experience_priority": "medium",
                "availability_priority": "high",
                "locality_priority": "high",
            },
        )

        content = response.content.decode()

        self.assertLess(content.index("gk_west"), content.index("gk_nw"))

    def test_search_results_include_match_score_and_rationale(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "YTH",
                "availability": "ANY",
                "locality": "W",
                "experience_priority": "medium",
                "availability_priority": "high",
                "locality_priority": "high",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Match Score")
        self.assertContains(response, "Rationale")

    def test_club_can_add_visible_player_to_shortlist(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.post(
            reverse("add_to_shortlist", args=[self.gk1.id]),
            {"next": reverse("club_search_players")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ShortlistEntry.objects.filter(club=self.club, player=self.gk1).exists()
        )

    def test_duplicate_shortlist_entry_is_not_created(self):
        self.client.login(username="rankclub", password="testpass123")

        ShortlistEntry.objects.create(club=self.club, player=self.gk1)

        self.client.post(
            reverse("add_to_shortlist", args=[self.gk1.id]),
            {"next": reverse("club_search_players")},
            follow=True,
        )

        self.assertEqual(
            ShortlistEntry.objects.filter(club=self.club, player=self.gk1).count(),
            1,
        )

    def test_club_can_remove_player_from_shortlist(self):
        self.client.login(username="rankclub", password="testpass123")

        ShortlistEntry.objects.create(club=self.club, player=self.gk1)

        response = self.client.post(
            reverse("remove_from_shortlist", args=[self.gk1.id]),
            {"next": reverse("club_shortlist")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ShortlistEntry.objects.filter(club=self.club, player=self.gk1).exists()
        )

    def test_hidden_player_cannot_be_added_to_shortlist(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.post(
            reverse("add_to_shortlist", args=[self.hidden_player.id]),
            {"next": reverse("club_search_players")},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ShortlistEntry.objects.filter(club=self.club, player=self.hidden_player).exists()
        )

    def test_successful_shortlist_updates_last_search_config(self):
        self.client.login(username="rankclub", password="testpass123")

        self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "YTH",
                "availability": "ANY",
                "locality": "W",
                "experience_priority": "medium",
                "availability_priority": "high",
                "locality_priority": "high",
            },
        )

        self.client.post(
            reverse("add_to_shortlist", args=[self.gk1.id]),
            {"next": reverse("club_search_players")},
            follow=True,
        )

        self.club.refresh_from_db()

        self.assertIsNotNone(self.club.last_search_config)
        self.assertEqual(self.club.last_search_config["position"], "GK")

    def test_successful_invite_updates_last_search_config(self):
        self.client.login(username="rankclub", password="testpass123")

        self.client.get(
            reverse("club_search_players"),
            {
                "position": "AM",
                "experience": "AM",
                "availability": "EVE",
                "locality": "C",
                "experience_priority": "high",
                "availability_priority": "medium",
                "locality_priority": "medium",
            },
        )

        self.client.post(
            reverse("invite_to_trial", args=[self.am.id]),
            {
                "trial_datetime": self.trial_dt_1.strftime("%Y-%m-%dT%H:%M"),
                "location": "Training Ground",
                "notes": "Be on time",
            },
            follow=True,
        )

        self.club.refresh_from_db()

        self.assertIsNotNone(self.club.last_search_config)
        self.assertEqual(self.club.last_search_config["position"], "AM")

    def test_suggested_players_exclude_shortlisted_and_invited_players(self):
        self.client.login(username="rankclub", password="testpass123")

        self.club.last_search_config = {
            "position": "GK",
            "experience": "YTH",
            "availability": "ANY",
            "locality": "W",
            "priorities": {
                "availability": "high",
                "experience": "medium",
                "locality": "high",
            },
        }
        self.club.save()

        ShortlistEntry.objects.create(club=self.club, player=self.gk1)
        TrialRequest.objects.create(
            club=self.club,
            player=self.gk2,
            trial_datetime=self.trial_dt_2,
            location="Ground",
            notes="",
            status="pending",
        )

        response = self.client.get(reverse("club_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "gk_west")
        self.assertNotContains(response, "gk_nw")

    def test_rationale_reflects_highest_contributing_factor(self):
        self.client.login(username="rankclub", password="testpass123")

        response = self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "YTH",
                "availability": "ANY",
                "locality": "W",
                "experience_priority": "medium",
                "availability_priority": "low",
                "locality_priority": "high",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nearby locality")

class TrialLifecycleAndFeedbackTests(TestCase):
    """Tests for invitation response, outcome recording, and private feedback rules."""

    def setUp(self):
        self.club_user, self.club = create_club("cluboutcome", name="Outcome Club")
        self.player_user, self.player = create_player(
            "playeroutcome",
            primary_position="ST",
            secondary_position="AM",
            preferred_foot="R",
            height_cm=181,
            experience_level="AM",
            availability_window="ANY",
            locality_area="C",
            bio="Outcome player",
        )
        self.other_user, self.other_player = create_player(
            "otherplayer",
            primary_position="CM",
            secondary_position="DM",
            preferred_foot="L",
            height_cm=177,
            experience_level="AM",
            availability_window="EVE",
            locality_area="E",
            bio="Other player",
        )

        self.trial_dt = aware_dt()

    def test_player_can_accept_trial(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="pending",
        )

        self.client.login(username="playeroutcome", password="testpass123")

        response = self.client.post(
            reverse("trial_detail", args=[trial.id]),
            {"action": "accept"},
            follow=True,
        )

        trial.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(trial.status, "accepted")
        self.assertIsNotNone(trial.responded_at)

    def test_player_can_decline_trial(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="pending",
        )

        self.client.login(username="playeroutcome", password="testpass123")

        response = self.client.post(
            reverse("trial_detail", args=[trial.id]),
            {"action": "decline"},
            follow=True,
        )

        trial.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(trial.status, "declined")
        self.assertIsNotNone(trial.responded_at)

    def test_club_cannot_record_outcome_for_pending_trial(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="pending",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.get(
            reverse("record_trial_outcome", args=[trial.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrialFeedback.objects.filter(trial=trial).exists())
        self.assertContains(response, "Outcome can only be recorded for accepted trials.")

    def test_record_attended_trial_creates_feedback_and_completes_trial(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="accepted",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.post(
            reverse("record_trial_outcome", args=[trial.id]),
            {
                "attendance": "attended",
                "positional_suitability": "strong",
                "work_rate": "satisfactory",
                "decision_making": "strong",
                "teammate_understanding": "satisfactory",
                "physicality": "needs_improvement",
                "offer_decision": "yes",
                "club_comment": "Promising overall performance.",
            },
            follow=True,
        )

        trial.refresh_from_db()
        feedback = TrialFeedback.objects.get(trial=trial)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(trial.status, "completed")
        self.assertTrue(trial.attendance)
        self.assertEqual(trial.outcome, "offered")
        self.assertEqual(feedback.offer_decision, "yes")
        self.assertIn("offer you a place in the team", feedback.generated_summary)
        self.assertIn("Promising overall performance.", feedback.generated_summary)

    def test_record_no_show_creates_no_show_outcome_and_no_offer_feedback(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="accepted",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.post(
            reverse("record_trial_outcome", args=[trial.id]),
            {
                "attendance": "did_not_attend",
                "club_comment": "Player did not arrive.",
            },
            follow=True,
        )

        trial.refresh_from_db()
        feedback = TrialFeedback.objects.get(trial=trial)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(trial.status, "completed")
        self.assertFalse(trial.attendance)
        self.assertEqual(trial.outcome, "no_show")
        self.assertEqual(feedback.offer_decision, "no")
        self.assertIn("did not attend the scheduled trial session", feedback.generated_summary)
        self.assertIn("will not be offering you a place", feedback.generated_summary)

    def test_second_feedback_submission_is_blocked(self):
        trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="accepted",
        )

        TrialFeedback.objects.create(
            trial=trial,
            positional_suitability="strong",
            work_rate="strong",
            decision_making="strong",
            teammate_understanding="strong",
            physicality="strong",
            offer_decision="yes",
            club_comment="Already recorded.",
            generated_summary="Already recorded summary.",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.get(
            reverse("record_trial_outcome", args=[trial.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TrialFeedback.objects.filter(trial=trial).count(), 1)
        self.assertContains(response, "Feedback has already been recorded for this trial.")

    def test_duplicate_reinvite_after_declined_trial_is_blocked(self):
        TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="declined",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.get(reverse("invite_to_trial", args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "previously declined a trial invitation")

    def test_duplicate_reinvite_after_completed_trial_is_blocked(self):
        TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="completed",
            attendance=True,
            outcome="offered",
        )

        self.client.login(username="cluboutcome", password="testpass123")

        response = self.client.get(reverse("invite_to_trial", args=[self.player.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already completed a trial with your club")

    def test_player_feedback_history_shows_only_own_feedback(self):
        trial_1 = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="completed",
            attendance=True,
            outcome="offered",
        )

        trial_2 = TrialRequest.objects.create(
            club=self.club,
            player=self.other_player,
            trial_datetime=self.trial_dt,
            location="Bridge",
            notes="",
            status="completed",
            attendance=True,
            outcome="not_offered",
        )

        TrialFeedback.objects.create(
            trial=trial_1,
            positional_suitability="strong",
            work_rate="strong",
            decision_making="strong",
            teammate_understanding="strong",
            physicality="strong",
            offer_decision="yes",
            club_comment="Good trial.",
            generated_summary="Player one summary.",
        )

        TrialFeedback.objects.create(
            trial=trial_2,
            positional_suitability="satisfactory",
            work_rate="satisfactory",
            decision_making="needs_improvement",
            teammate_understanding="satisfactory",
            physicality="not_good",
            offer_decision="no",
            club_comment="Other player trial.",
            generated_summary="Player two summary.",
        )

        self.client.login(username="playeroutcome", password="testpass123")

        response = self.client.get(reverse("player_feedback_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Player one summary.")
        self.assertNotContains(response, "Player two summary.")


class ReportingAndModerationTests(TestCase):
    """Tests for dispute handling, reporting workflow, and user-visible moderation outcomes."""

    def setUp(self):
        self.club_user, self.club = create_club("clubreport", name="Report Club")
        self.player_user, self.player = create_player("playerreport")
        self.other_user, self.other_player = create_player("otherreport")

        self.pending_trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=aware_dt(),
            location="Bridge",
            notes="Pending trial",
            status="pending",
        )

        self.completed_trial = TrialRequest.objects.create(
            club=self.club,
            player=self.player,
            trial_datetime=aware_dt(2026, 4, 26, 18, 0),
            location="Bridge",
            notes="Completed trial",
            status="completed",
            attendance=True,
            outcome="offered",
        )

        self.feedback = TrialFeedback.objects.create(
            trial=self.completed_trial,
            positional_suitability="strong",
            work_rate="strong",
            decision_making="satisfactory",
            teammate_understanding="satisfactory",
            physicality="strong",
            offer_decision="yes",
            club_comment="Well done.",
            generated_summary="Feedback summary for reporting tests.",
        )

    def test_player_can_report_trial_invitation(self):
        self.client.login(username="playerreport", password="testpass123")

        response = self.client.post(
            reverse("report_trial_invitation", args=[self.pending_trial.id]),
            {
                "reason": "suspicious_invitation",
                "details": "This invitation looks suspicious.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Report.objects.filter(
                reporter=self.player_user,
                report_type="trial_invitation",
                trial_request=self.pending_trial,
            ).exists()
        )

    def test_duplicate_open_trial_invitation_report_is_blocked(self):
        Report.objects.create(
            reporter=self.player_user,
            report_type="trial_invitation",
            reason="suspicious_invitation",
            details="Existing open report.",
            trial_request=self.pending_trial,
            status="open",
        )

        self.client.login(username="playerreport", password="testpass123")

        response = self.client.post(
            reverse("report_trial_invitation", args=[self.pending_trial.id]),
            {
                "reason": "other",
                "details": "Trying to submit again.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Report.objects.filter(
                reporter=self.player_user,
                report_type="trial_invitation",
                trial_request=self.pending_trial,
            ).count(),
            1,
        )
        self.assertContains(response, "already submitted an open report")

    def test_player_can_report_feedback(self):
        self.client.login(username="playerreport", password="testpass123")

        response = self.client.post(
            reverse("report_feedback", args=[self.feedback.id]),
            {
                "reason": "unfair_feedback",
                "details": "I believe this feedback is misleading.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Report.objects.filter(
                reporter=self.player_user,
                report_type="feedback",
                feedback=self.feedback,
            ).exists()
        )

    def test_club_can_report_player_profile(self):
        self.client.login(username="clubreport", password="testpass123")

        response = self.client.post(
            reverse("report_player_profile", args=[self.player.id]),
            {
                "reason": "misleading_profile",
                "details": "This profile appears misleading.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Report.objects.filter(
                reporter=self.club_user,
                report_type="player_profile",
                reported_player=self.player,
            ).exists()
        )

    def test_my_reports_shows_only_current_user_reports(self):
        Report.objects.create(
            reporter=self.player_user,
            report_type="trial_invitation",
            reason="suspicious_invitation",
            details="Player report should be visible.",
            trial_request=self.pending_trial,
            status="open",
        )

        Report.objects.create(
            reporter=self.other_user,
            report_type="player_profile",
            reason="other",
            details="Other user report should not be visible.",
            reported_player=self.player,
            status="open",
        )

        self.client.login(username="playerreport", password="testpass123")

        response = self.client.get(reverse("my_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Player report should be visible.")
        self.assertNotContains(response, "Other user report should not be visible.")

    def test_my_reports_displays_resolved_status_and_admin_note(self):
        admin_user = User.objects.create_user(username="adminnote", password="testpass123")

        Report.objects.create(
            reporter=self.player_user,
            resolver=admin_user,
            report_type="feedback",
            reason="unfair_feedback",
            details="Please review this feedback.",
            feedback=self.feedback,
            status="resolved",
            admin_notes="Reviewed and handled appropriately.",
            resolved_at=aware_dt(2026, 4, 27, 10, 30),
        )

        self.client.login(username="playerreport", password="testpass123")

        response = self.client.get(reverse("my_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resolved")
        self.assertContains(response, "Reviewed and handled appropriately.")


class PaginationTests(TestCase):
    """Tests for required server-side pagination of search results and suggestions."""

    def setUp(self):
        self.club_user, self.club = create_club("pageclub", name="Pagination Club")

        self.goalkeepers = []
        for i in range(1, 12):
            username = f"gk_{i:02d}"
            user, player = create_player(
                username,
                primary_position="GK",
                secondary_position="CB",
                preferred_foot="R",
                height_cm=180 + i,
                experience_level="AM",
                availability_window="ANY",
                locality_area="C",
                bio=f"{username} bio",
            )
            self.goalkeepers.append(player)

        self.club.last_search_config = {
            "position": "GK",
            "experience": "AM",
            "availability": "ANY",
            "locality": "C",
            "priorities": {
                "availability": "medium",
                "experience": "medium",
                "locality": "medium",
            },
        }
        self.club.save()

    def test_ranked_search_paginates_after_ten_results(self):
        self.client.login(username="pageclub", password="testpass123")

        response = self.client.get(
            reverse("club_search_players"),
            {
                "position": "GK",
                "experience": "AM",
                "availability": "ANY",
                "locality": "C",
                "experience_priority": "medium",
                "availability_priority": "medium",
                "locality_priority": "medium",
                "page": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        self.assertContains(response, "gk_01")

    def test_suggested_players_paginate_after_five_results(self):
        self.client.login(username="pageclub", password="testpass123")

        response = self.client.get(
            reverse("club_dashboard"),
            {"suggestions_page": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 3 of 3")
        self.assertContains(response, "gk_01")