from datetime import datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Player, Club, ShortlistEntry, TrialRequest, TrialFeedback, Report
from .forms import TrialOutcomeFeedbackForm, ReportForm
from .services import rank_players, generate_feedback_summary
from django.urls import reverse
from django.core.paginator import Paginator

TRIAL_INVITATION_REPORT_REASONS = [
    ("suspicious_invitation", "Suspicious invitation"),
    ("inappropriate_trial_details", "Inappropriate trial details"),
    ("suspected_fake_club", "Suspected fake club"),
    ("abusive_communication", "Abusive or unprofessional communication"),
    ("other", "Other"),
]

FEEDBACK_REPORT_REASONS = [
    ("unfair_feedback", "Feedback appears misleading or unfair"),
    ("inappropriate_language", "Inappropriate language"),
    ("abusive_communication", "Abusive or unprofessional communication"),
    ("other", "Other"),
]

PLAYER_PROFILE_REPORT_REASONS = [
    ("suspected_fake_profile", "Suspected fake profile"),
    ("misleading_profile", "Misleading player information"),
    ("inappropriate_profile_content", "Inappropriate profile content"),
    ("abusive_behaviour", "Abusive behaviour"),
    ("other", "Other"),
]

def build_search_config(position, experience, availability, locality, priorities):
    return {
        "position": position,
        "experience": experience,
        "availability": availability,
        "locality": locality,
        "priorities": priorities,
    }


def build_search_config_from_player(player, priorities=None):
    if priorities is None:
        priorities = {
            "availability": "medium",
            "experience": "medium",
            "locality": "medium",
        }

    return {
        "position": player.primary_position,
        "experience": player.experience_level,
        "availability": player.availability_window,
        "locality": player.locality_area,
        "priorities": priorities,
    }


def persist_last_successful_search(request, club, player=None):
    pending_config = request.session.get("pending_search_config")
    config_to_save = None

    if pending_config and pending_config.get("position"):
        if player is None or pending_config.get("position") == player.primary_position:
            config_to_save = pending_config

    if config_to_save is None and player is not None:
        priorities = (
            pending_config.get("priorities")
            if pending_config and pending_config.get("priorities")
            else {
                "availability": "medium",
                "experience": "medium",
                "locality": "medium",
            }
        )
        config_to_save = build_search_config_from_player(player, priorities)

    if config_to_save:
        club.last_search_config = config_to_save
        club.last_search_at = timezone.now()
        club.save(update_fields=["last_search_config", "last_search_at"])


def get_players_from_search_config(config):
    players = Player.objects.filter(
        visibility=True,
        primary_position=config.get("position")
    )
    return players


def home(request):
    return render(request, "core/home.html")


def login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'player'):
            return redirect('player_dashboard')
        elif hasattr(request.user, 'club'):
            return redirect('club_dashboard')
        else:
            return redirect('home')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if hasattr(user, 'player'):
                return redirect('player_dashboard')
            elif hasattr(user, 'club'):
                return redirect('club_dashboard')
            else:
                return redirect('home')

        else:
            messages.error(request, "Invalid username or password")

    return render(request, "core/login.html")


def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")

        if User.objects.filter(username=username).exists():
            return render(request, "core/register.html", {
                "error": "Username already exists"
            })

        user = User.objects.create_user(
            username=username,
            password=password
        )

        if role == "player":
            Player.objects.create(user=user)
            login(request, user)
            return redirect("player_dashboard")

        elif role == "club":
            Club.objects.create(user=user, name=username)
            login(request, user)
            return redirect("club_dashboard")

        else:
            return render(request, "core/register.html", {
                "error": "Invalid role selected"
            })

    return render(request, "core/register.html")


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def dashboard(request):
    if hasattr(request.user, "player"):
        return redirect("player_dashboard")

    if hasattr(request.user, "club"):
        return redirect("club_dashboard")

    return redirect("home")

def email_in_use_by_other_account(email, current_user):
    email = (email or "").strip().lower()

    if not email:
        return False

    player_exists = Player.objects.exclude(user=current_user).filter(
        contact_email__iexact=email
    ).exists()

    club_exists = Club.objects.exclude(user=current_user).filter(
        contact_email__iexact=email
    ).exists()

    return player_exists or club_exists

@login_required
def player_profile(request):
    player, created = Player.objects.get_or_create(user=request.user)

    if request.method == "POST":
        player.primary_position = request.POST.get("primary_position")
        player.secondary_position = request.POST.get("secondary_position")
        player.preferred_foot = request.POST.get("preferred_foot")
        player.height_cm = request.POST.get("height_cm") or None
        player.experience_level = request.POST.get("experience_level")
        player.availability_window = request.POST.get("availability_window")
        player.locality_area = request.POST.get("locality_area")
        player.contact_email = (request.POST.get("contact_email") or "").strip().lower()
        player.contact_phone = (request.POST.get("contact_phone") or "").strip()
        player.bio = request.POST.get("bio")
        player.visibility = request.POST.get("visibility") == "on"

        if not player.contact_email:
            messages.error(request, "Private email is required.")
            return render(request, "core/player_profile.html", {
                "player": player
            })

        if email_in_use_by_other_account(player.contact_email, request.user):
            messages.error(request, "That email address is already being used by another account.")
            return render(request, "core/player_profile.html", {
                "player": player
            })

        player.save()
        messages.success(request, "Profile saved successfully.")
        return redirect("player_dashboard")

    return render(request, "core/player_profile.html", {
        "player": player
    })

@login_required
def club_profile(request):
    club = Club.objects.get(user=request.user)

    if request.method == "POST":
        club.name = request.POST.get("name")
        club.division = request.POST.get("division")
        club.home_ground = request.POST.get("home_ground")
        club.contact_email = (request.POST.get("contact_email") or "").strip().lower()
        club.contact_phone = (request.POST.get("contact_phone") or "").strip()
        club.contact_pref = request.POST.get("contact_pref")

        if not club.contact_email:
            messages.error(request, "Club email is required.")
            return render(request, "core/club_profile.html", {
                "club": club,
                "divisions": Club.CLUB_DIVISIONS,
                "contact_prefs": Club.CONTACT_PREFERENCES,
            })

        if not club.contact_phone:
            messages.error(request, "Club phone number is required.")
            return render(request, "core/club_profile.html", {
                "club": club,
                "divisions": Club.CLUB_DIVISIONS,
                "contact_prefs": Club.CONTACT_PREFERENCES,
            })

        if email_in_use_by_other_account(club.contact_email, request.user):
            messages.error(request, "That email address is already being used by another account.")
            return render(request, "core/club_profile.html", {
                "club": club,
                "divisions": Club.CLUB_DIVISIONS,
                "contact_prefs": Club.CONTACT_PREFERENCES,
            })

        club.save()
        messages.success(request, "Club profile saved successfully.")
        return redirect("club_dashboard")

    return render(request, "core/club_profile.html", {
        "club": club,
        "divisions": Club.CLUB_DIVISIONS,
        "contact_prefs": Club.CONTACT_PREFERENCES,
    })

@login_required
def player_dashboard(request):
    player = Player.objects.get(user=request.user)

    profile_complete = bool(
        player.primary_position and
        player.height_cm and
        player.experience_level and
        player.contact_email
    )

    return render(request, "core/player_dashboard.html", {
        "player": player,
        "profile_complete": profile_complete
    })

@login_required
def club_dashboard(request):
    club = Club.objects.get(user=request.user)

    profile_complete = all([
        club.name,
        club.division,
        club.home_ground,
        club.contact_email,
        club.contact_phone,
        club.contact_pref,
    ])

    shortlist_count = ShortlistEntry.objects.filter(club=club).count()
    suggested_players_page_obj = None

    if club.last_search_config:
        config = club.last_search_config

        players = get_players_from_search_config(config)

        shortlisted_ids = ShortlistEntry.objects.filter(
            club=club
        ).values_list("player_id", flat=True)

        invited_ids = TrialRequest.objects.filter(
            club=club
        ).values_list("player_id", flat=True)

        players = players.exclude(id__in=shortlisted_ids).exclude(id__in=invited_ids)

        ranked_suggested_players = rank_players(
            players,
            {
                "experience": config.get("experience"),
                "availability": config.get("availability"),
                "locality": config.get("locality"),
            },
            config.get("priorities", {})
        )

        paginator = Paginator(ranked_suggested_players, 5)
        suggestions_page_number = request.GET.get("suggestions_page")
        suggested_players_page_obj = paginator.get_page(suggestions_page_number)

    return render(request, "core/club_dashboard.html", {
        "club": club,
        "profile_complete": profile_complete,
        "shortlist_count": shortlist_count,
        "suggested_players_page_obj": suggested_players_page_obj,
    })

@login_required
def club_search_players(request):
    if not hasattr(request.user, "club"):
        return redirect("home")

    club = Club.objects.get(user=request.user)

    players_page_obj = None
    searched = False

    position = request.GET.get("position", "")
    experience = request.GET.get("experience", "")
    availability = request.GET.get("availability", "")
    locality = request.GET.get("locality", "")

    experience_priority = request.GET.get("experience_priority", "medium")
    availability_priority = request.GET.get("availability_priority", "medium")
    locality_priority = request.GET.get("locality_priority", "medium")

    priorities = {
        "availability": availability_priority,
        "experience": experience_priority,
        "locality": locality_priority,
    }

    if request.GET:
        searched = True

        if not position:
            messages.warning(request, "Please select a primary position to run ranked search.")
        else:
            players_qs = Player.objects.filter(
                visibility=True,
                primary_position=position
            )

            ranked_players = rank_players(
                players_qs,
                {
                    "experience": experience,
                    "availability": availability,
                    "locality": locality,
                },
                priorities
            )

            paginator = Paginator(ranked_players, 10)
            page_number = request.GET.get("page")
            players_page_obj = paginator.get_page(page_number)

            request.session["pending_search_config"] = build_search_config(
                position,
                experience,
                availability,
                locality,
                priorities
            )

    shortlisted_player_ids = list(
        ShortlistEntry.objects.filter(club=club).values_list("player_id", flat=True)
    )

    current_search_query = request.GET.urlencode()

    search_query_params = request.GET.copy()
    if "page" in search_query_params:
        search_query_params.pop("page")
    search_query_without_page = search_query_params.urlencode()

    return render(request, "core/club_search_players.html", {
        "players_page_obj": players_page_obj,
        "positions": Player.POSITION_CHOICES,
        "experiences": Player.EXPERIENCE_CHOICES,
        "availabilities": Player.AVAILABILITY_CHOICES,
        "localities": Player.LONDON_AREA_CHOICES,
        "shortlisted_player_ids": shortlisted_player_ids,
        "searched": searched,
        "selected_position": position,
        "selected_experience": experience,
        "selected_availability": availability,
        "selected_locality": locality,
        "experience_priority": experience_priority,
        "availability_priority": availability_priority,
        "locality_priority": locality_priority,
        "current_search_query": current_search_query,
        "search_query_without_page": search_query_without_page,
    })

@login_required
def club_view_player(request, player_id):
    if not hasattr(request.user, "club"):
        return redirect("home")

    club = Club.objects.get(user=request.user)
    player = get_object_or_404(Player, id=player_id, visibility=True)

    is_shortlisted = ShortlistEntry.objects.filter(
        club=club,
        player=player
    ).exists()

    latest_player_report = Report.objects.filter(
        reporter=request.user,
        report_type="player_profile",
        reported_player=player
    ).order_by("-created_at").first()

    next_url = request.GET.get("next_url")
    next_query = request.GET.get("next_query", "")

    if next_url:
        back_url = next_url
        back_label = "Back"
        if next_url == reverse("club_shortlist"):
            back_label = "Back to Shortlist"
        elif next_url == reverse("club_dashboard"):
            back_label = "Back to Dashboard"
        elif next_url.startswith(reverse("club_search_players")):
            back_label = "Back to Search"
    elif next_query:
        back_url = f"{reverse('club_search_players')}?{next_query}"
        back_label = "Back to Search"
    else:
        back_url = reverse("club_search_players")
        back_label = "Back to Search"

    return render(request, "core/club_view_player.html", {
        "player": player,
        "is_shortlisted": is_shortlisted,
        "latest_player_report": latest_player_report,
        "back_url": back_url,
        "back_label": back_label,
    })

@login_required
def club_shortlist(request):
    if not hasattr(request.user, "club"):
        return redirect("home")

    club = Club.objects.get(user=request.user)

    shortlist_entries = ShortlistEntry.objects.filter(
        club=club
    ).select_related("player__user").order_by("-added_at")

    return render(request, "core/club_shortlist.html", {
        "shortlist_entries": shortlist_entries
    })


@login_required
def add_to_shortlist(request, player_id):
    if not hasattr(request.user, "club"):
        return redirect("home")

    if request.method != "POST":
        return redirect("club_search_players")

    club = Club.objects.get(user=request.user)
    player = get_object_or_404(Player, id=player_id, visibility=True)

    shortlist_entry, created = ShortlistEntry.objects.get_or_create(
        club=club,
        player=player
    )

    if created:
        persist_last_successful_search(request, club, player=player)
        messages.success(request, f"{player.user.username} added to shortlist.")
    else:
        messages.warning(request, f"{player.user.username} is already in your shortlist.")

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)

    return redirect("club_shortlist")


@login_required
def remove_from_shortlist(request, player_id):
    if not hasattr(request.user, "club"):
        return redirect("home")

    if request.method != "POST":
        return redirect("club_shortlist")

    club = Club.objects.get(user=request.user)

    deleted_count, _ = ShortlistEntry.objects.filter(
        club=club,
        player_id=player_id
    ).delete()

    if deleted_count:
        messages.success(request, "Player removed from shortlist.")
    else:
        messages.warning(request, "That player was not in your shortlist.")

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)

    return redirect("club_shortlist")


@login_required
def invite_to_trial(request, player_id):
    club = Club.objects.get(user=request.user)
    player = get_object_or_404(Player, id=player_id, visibility=True)

    existing_trial = TrialRequest.objects.filter(
        club=club,
        player=player
    ).order_by("-created_at").first()

    if existing_trial:
        return render(request, "core/trial_already_exists.html", {
            "player": player,
            "trial": existing_trial
        })

    if request.method == "POST":
        raw_trial_datetime = request.POST.get("trial_datetime")

        trial_datetime = None
        if raw_trial_datetime:
            parsed_datetime = datetime.strptime(raw_trial_datetime, "%Y-%m-%dT%H:%M")
            trial_datetime = timezone.make_aware(
                parsed_datetime,
                timezone.get_default_timezone()
            )

        TrialRequest.objects.create(
            club=club,
            player=player,
            trial_datetime=trial_datetime,
            location=request.POST.get("location"),
            notes=request.POST.get("notes"),
            status="pending"
        )

        persist_last_successful_search(request, club, player=player)

        return render(request, "core/trial_sent.html", {
            "player": player
        })

    return render(request, "core/invite_to_trial.html", {
        "player": player
    })

@login_required
def player_trials(request):
    if not hasattr(request.user, "player"):
        return redirect("home")

    player = Player.objects.get(user=request.user)

    trials = TrialRequest.objects.filter(
        player=player
    ).select_related("club").order_by("-created_at")

    return render(request, "core/player_trials.html", {
        "trials": trials
    })


@login_required
def trial_detail(request, trial_id):
    if not hasattr(request.user, "player"):
        return redirect("home")

    trial = get_object_or_404(
        TrialRequest,
        id=trial_id,
        player__user=request.user
    )

    if request.method == "POST" and trial.status == "pending":
        action = request.POST.get("action")

        if action == "accept":
            trial.status = "accepted"
            trial.responded_at = timezone.now()
            trial.save()

        elif action == "decline":
            trial.status = "declined"
            trial.responded_at = timezone.now()
            trial.save()

        return redirect("player_trials")

    latest_trial_report = Report.objects.filter(
        reporter=request.user,
        report_type="trial_invitation",
        trial_request=trial
    ).order_by("-created_at").first()

    return render(request, "core/trial_detail.html", {
        "trial": trial,
        "latest_trial_report": latest_trial_report,
    })


@login_required
def club_trial_requests(request):
    if not hasattr(request.user, "club"):
        return redirect("home")

    club = Club.objects.get(user=request.user)

    trials = TrialRequest.objects.filter(
        club=club
    ).select_related("player__user").order_by("-created_at")

    return render(request, "core/club_trial_requests.html", {
        "trials": trials
    })


@login_required
def record_trial_outcome(request, trial_id):
    if not hasattr(request.user, "club"):
        return redirect("home")

    trial = get_object_or_404(
        TrialRequest,
        id=trial_id,
        club__user=request.user
    )

    if trial.status != "accepted":
        messages.warning(request, "Outcome can only be recorded for accepted trials.")
        return redirect("club_trial_requests")

    if hasattr(trial, "feedback"):
        messages.warning(request, "Feedback has already been recorded for this trial.")
        return redirect("club_trial_requests")

    if request.method == "POST":
        form = TrialOutcomeFeedbackForm(request.POST)

        if form.is_valid():
            attendance = form.cleaned_data["attendance"]
            positional_suitability = form.cleaned_data.get("positional_suitability", "")
            work_rate = form.cleaned_data.get("work_rate", "")
            decision_making = form.cleaned_data.get("decision_making", "")
            teammate_understanding = form.cleaned_data.get("teammate_understanding", "")
            physicality = form.cleaned_data.get("physicality", "")
            offer_decision = form.cleaned_data.get("offer_decision", "")
            club_comment = form.cleaned_data.get("club_comment", "")

            if attendance == "attended":
                trial.attendance = True
                trial.outcome = "offered" if offer_decision == "yes" else "not_offered"
            else:
                trial.attendance = False
                trial.outcome = "no_show"
                offer_decision = "no"
                positional_suitability = ""
                work_rate = ""
                decision_making = ""
                teammate_understanding = ""
                physicality = ""

            trial.status = "completed"
            trial.save(update_fields=["attendance", "outcome", "status"])

            generated_summary = generate_feedback_summary(
                attendance=attendance,
                positional_suitability=positional_suitability,
                work_rate=work_rate,
                decision_making=decision_making,
                teammate_understanding=teammate_understanding,
                physicality=physicality,
                offer_decision=offer_decision,
                club_comment=club_comment
            )

            TrialFeedback.objects.create(
                trial=trial,
                positional_suitability=positional_suitability,
                work_rate=work_rate,
                decision_making=decision_making,
                teammate_understanding=teammate_understanding,
                physicality=physicality,
                offer_decision=offer_decision,
                club_comment=club_comment,
                generated_summary=generated_summary
            )

            messages.success(request, "Trial outcome and feedback recorded successfully.")
            return redirect("club_trial_requests")
    else:
        form = TrialOutcomeFeedbackForm()

    return render(request, "core/record_trial_outcome.html", {
        "trial": trial,
        "form": form
    })


@login_required
def player_feedback_history(request):
    if not hasattr(request.user, "player"):
        return redirect("home")

    feedback_entries = list(
        TrialFeedback.objects.filter(
            trial__player__user=request.user
        ).select_related("trial__club").order_by("-created_at")
    )

    for feedback in feedback_entries:
        feedback.latest_user_report = Report.objects.filter(
            reporter=request.user,
            report_type="feedback",
            feedback=feedback
        ).order_by("-created_at").first()

    return render(request, "core/player_feedback_history.html", {
        "feedback_entries": feedback_entries
    })

@login_required
def report_trial_invitation(request, trial_id):
    if not hasattr(request.user, "player"):
        return redirect("home")

    trial = get_object_or_404(
        TrialRequest,
        id=trial_id,
        player__user=request.user
    )

    existing_open_report = Report.objects.filter(
        reporter=request.user,
        report_type="trial_invitation",
        trial_request=trial,
        status="open"
    ).exists()

    if existing_open_report:
        messages.warning(request, "You have already submitted an open report for this trial invitation.")
        return redirect("trial_detail", trial_id=trial.id)

    if request.method == "POST":
        form = ReportForm(request.POST, reason_choices=TRIAL_INVITATION_REPORT_REASONS)
        if form.is_valid():
            Report.objects.create(
                reporter=request.user,
                report_type="trial_invitation",
                reason=form.cleaned_data["reason"],
                details=form.cleaned_data["details"],
                trial_request=trial
            )
            messages.success(request, "Your report has been submitted for administrative review.")
            return redirect("trial_detail", trial_id=trial.id)
    else:
        form = ReportForm(reason_choices=TRIAL_INVITATION_REPORT_REASONS)

    return render(request, "core/report_form.html", {
        "title": "Report Trial Invitation",
        "target_name": f"{trial.club.name} invitation",
        "form": form,
        "cancel_url": reverse("trial_detail", args=[trial.id]),
    })


@login_required
def report_feedback(request, feedback_id):
    if not hasattr(request.user, "player"):
        return redirect("home")

    feedback = get_object_or_404(
        TrialFeedback,
        id=feedback_id,
        trial__player__user=request.user
    )

    existing_open_report = Report.objects.filter(
        reporter=request.user,
        report_type="feedback",
        feedback=feedback,
        status="open"
    ).exists()

    if existing_open_report:
        messages.warning(request, "You have already submitted an open report for this feedback.")
        return redirect("player_feedback_history")

    if request.method == "POST":
        form = ReportForm(request.POST, reason_choices=FEEDBACK_REPORT_REASONS)
        if form.is_valid():
            Report.objects.create(
                reporter=request.user,
                report_type="feedback",
                reason=form.cleaned_data["reason"],
                details=form.cleaned_data["details"],
                feedback=feedback
            )
            messages.success(request, "Your report has been submitted for administrative review.")
            return redirect("player_feedback_history")
    else:
        form = ReportForm(reason_choices=FEEDBACK_REPORT_REASONS)

    return render(request, "core/report_form.html", {
        "title": "Report Feedback",
        "target_name": f"Feedback from {feedback.trial.club.name}",
        "form": form,
        "cancel_url": reverse("player_feedback_history"),
    })


@login_required
def report_player_profile(request, player_id):
    if not hasattr(request.user, "club"):
        return redirect("home")

    player = get_object_or_404(Player, id=player_id)

    existing_open_report = Report.objects.filter(
        reporter=request.user,
        report_type="player_profile",
        reported_player=player,
        status="open"
    ).exists()

    if existing_open_report:
        messages.warning(request, "You have already submitted an open report for this player profile.")
        return redirect("club_view_player", player_id=player.id)

    if request.method == "POST":
        form = ReportForm(request.POST, reason_choices=PLAYER_PROFILE_REPORT_REASONS)
        if form.is_valid():
            Report.objects.create(
                reporter=request.user,
                report_type="player_profile",
                reason=form.cleaned_data["reason"],
                details=form.cleaned_data["details"],
                reported_player=player
            )
            messages.success(request, "Your report has been submitted for administrative review.")
            return redirect("club_view_player", player_id=player.id)
    else:
        form = ReportForm(reason_choices=PLAYER_PROFILE_REPORT_REASONS)

    return render(request, "core/report_form.html", {
        "title": "Report Player Profile",
        "target_name": player.user.username,
        "form": form,
        "cancel_url": reverse("club_view_player", args=[player.id]),
    })
    
@login_required
def my_reports(request):
    reports = Report.objects.filter(
        reporter=request.user
    ).select_related(
        "trial_request__club",
        "feedback__trial__club",
        "reported_player__user",
        "resolver"
    ).order_by("-created_at")

    return render(request, "core/my_reports.html", {
        "reports": reports
    })