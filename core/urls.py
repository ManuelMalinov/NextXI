from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("player/profile/", views.player_profile, name="player_profile"),
    path("player/dashboard/", views.player_dashboard, name="player_dashboard"),
    path("player/trials/", views.player_trials, name="player_trials"),
    path("player/trial/<int:trial_id>/", views.trial_detail, name="trial_detail"),
    path("player/feedback/", views.player_feedback_history, name="player_feedback_history"),
    path("player/trial/<int:trial_id>/report/", views.report_trial_invitation, name="report_trial_invitation"),
    path("player/feedback/<int:feedback_id>/report/", views.report_feedback, name="report_feedback"),
    path("my-reports/", views.my_reports, name="my_reports"),
    path("club/profile/", views.club_profile, name="club_profile"),
    path("club/dashboard/", views.club_dashboard, name="club_dashboard"),
    path("club/search/", views.club_search_players, name="club_search_players"),
    path("club/shortlist/", views.club_shortlist, name="club_shortlist"),
    path("club/shortlist/add/<int:player_id>/", views.add_to_shortlist, name="add_to_shortlist"),
    path("club/shortlist/remove/<int:player_id>/", views.remove_from_shortlist, name="remove_from_shortlist"),
    path("club/player/<int:player_id>/", views.club_view_player, name="club_view_player"),
    path("club/player/<int:player_id>/report/", views.report_player_profile, name="report_player_profile"),
    path("club/invite/<int:player_id>/", views.invite_to_trial, name="invite_to_trial"),
    path("club/trials/", views.club_trial_requests, name="club_trial_requests"),
    path("club/trials/<int:trial_id>/record/", views.record_trial_outcome, name="record_trial_outcome"),
]