from django.contrib import admin
from django.urls import path
from projects.team import assign_manager, manager_directory, project_team

from projects.notifications import (
    NotificationListView, mark_notification_read, notification_count, sync_deadline_notifications,
)

from projects.analytics import analytics
from projects.finance import ExpenditureView
from projects.reporting import dashboard, report, risk_response
from projects.statuses import project_statuses
from projects.tracking_views import (
    ProgressEvidenceView,
    ProgressResubmitView,
    ProgressReviewView,
    ProgressUpdateListCreateView,
    WorkItemDetailView,
    WorkItemListCreateView,
)
from projects.views import ProjectArchiveView, ProjectAuditListView, ProjectDetailView, ProjectListCreateView

from . import views

urlpatterns = [
    path("api/v1/project-statuses/", project_statuses, name="project-statuses"),
    path("api/v1/projects/<uuid:project_id>/risk-response/", risk_response, name="risk-response"),
    path("api/v1/manager-directory/", manager_directory, name="manager-directory"),
    path("api/v1/projects/<uuid:project_id>/manager/", assign_manager, name="assign-manager"),
    path("api/v1/projects/<uuid:project_id>/team/", project_team, name="project-team"),
    path("api/v1/notifications/", NotificationListView.as_view(), name="notifications"),
    path("api/v1/notifications/count/", notification_count, name="notification-count"),
    path("api/v1/notifications/sync/", sync_deadline_notifications, name="notification-sync"),
    path("api/v1/notifications/<int:pk>/read/", mark_notification_read, name="notification-read"),
    path("api/v1/dashboard/", dashboard, name="dashboard"),
    path("api/v1/reports/", report, name="report"),
    path("api/v1/projects/<uuid:project_id>/expenditure/", ExpenditureView.as_view(), name="expenditure"),
    path("api/v1/projects/<uuid:project_id>/analytics/", analytics, name="analytics"),
    path("admin/", admin.site.urls),
    path("api/v1/health/", views.health, name="health"),
    path("api/v1/auth/csrf/", views.csrf_token, name="csrf"),
    path("api/v1/auth/login/", views.sign_in, name="login"),
    path("api/v1/auth/logout/", views.sign_out, name="logout"),
    path("api/v1/auth/me/", views.current_user, name="current-user"),
    path("api/v1/projects/", ProjectListCreateView.as_view(), name="project-list"),
    path("api/v1/projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("api/v1/projects/<uuid:pk>/audit/", ProjectAuditListView.as_view(), name="project-audit"),
    path("api/v1/projects/<uuid:pk>/archive/", ProjectArchiveView.as_view(), name="project-archive"),
    path(
        "api/v1/projects/<uuid:project_id>/work-items/",
        WorkItemListCreateView.as_view(),
        name="work-item-list",
    ),
    path(
        "api/v1/projects/<uuid:project_id>/work-items/<int:pk>/",
        WorkItemDetailView.as_view(),
        name="work-item-detail",
    ),
    path(
        "api/v1/projects/<uuid:project_id>/progress-updates/",
        ProgressUpdateListCreateView.as_view(),
        name="progress-update-list",
    ),
    path(
        "api/v1/projects/<uuid:project_id>/progress-updates/<int:pk>/review/",
        ProgressReviewView.as_view(), name="progress-review",
    ),
    path(
        "api/v1/projects/<uuid:project_id>/progress-updates/<int:pk>/resubmit/",
        ProgressResubmitView.as_view(), name="progress-resubmit",
    ),
    path(
        "api/v1/projects/<uuid:project_id>/progress-updates/<int:pk>/evidence/",
        ProgressEvidenceView.as_view(), name="progress-evidence",
    ),
]
