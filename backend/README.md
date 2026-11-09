# Project Tracking Backend

Run these PowerShell commands from the project root on first setup.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/api/v1/health/ to check the API or
http://127.0.0.1:8000/admin/ to sign in with the local admin account.

## Session API

Use these paths relative to the backend origin. In local React development,
proxy `/api` to Django so the browser can use same-origin session cookies.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health/` | Check that the API is responding |
| GET | `/api/v1/auth/csrf/` | Get a CSRF token before signing in |
| POST | `/api/v1/auth/login/` | Sign in with JSON fields `username` and `password` |
| GET | `/api/v1/auth/me/` | Get the signed-in user's identity |
| POST | `/api/v1/auth/logout/` | End the session |

Send the CSRF token in the `X-CSRFToken` header for POST requests. Login
rotates the token, so use the new `csrfToken` from the login response for
subsequent writes. Keep the session and CSRF cookies on requests.

## Project registration

`GET /api/v1/projects/` returns 20 projects per page. Use `?search=road` to
search by title or department, `?department=Public%20Works&status=proposed`
to filter, and `?page=2` to browse results. Signed-in users see their owned
projects and, with the **Can view project** permission, assigned projects.
Superusers can see all projects.

`POST /api/v1/projects/` requires the Django **Can add project** permission.
Assign it to a Project Manager group in Django admin and add the relevant users
to that group. Superusers already have the permission. The authenticated creator
becomes the owner. Send the current CSRF token with the request.

```json
{
  "title": "Road rehabilitation",
  "department": "Public Works",
  "planned_start": "2026-11-10",
  "planned_end": "2027-01-15",
  "approved_budget": "2500000.00",
  "currency": "NGN"
}
```

`description` is optional. `status` defaults to `proposed`. The server
generates the project ID. Apply the schema with `manage.py migrate` and run
the backend checks with `manage.py test`.

## Project details and history

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/projects/<id>/` | View a project within the user's access scope |
| PATCH | `/api/v1/projects/<id>/` | Edit selected fields with the current CSRF token |
| GET | `/api/v1/projects/<id>/audit/` | View paginated creation and edit events |

Set up role groups in Django admin. Project Managers need **Can add project**
and **Can change project** to create and edit projects they own. Project Officers
and Auditors need **Can view project** and a **Project access** record linking
them to each permitted project. Give Auditors **Can view project audit event**
to see history for their assigned projects. Owners can view their own history.
Superusers can edit and inspect all projects.

Edits record the actor, timestamp, and before/after values. Projects created
before the audit migration start recording history with their next edit.

## Tasks, milestones and progress

The following paths start at `/api/v1/projects/<project_id>/`.

| Method | Relative path | Purpose |
| --- | --- | --- |
| GET, POST | `work-items/` | List or create tasks and milestones. Filter with `?kind=milestone`. |
| GET, PATCH | `work-items/<id>/` | View or update a task or milestone. Set `is_active` to false to deactivate it. |
| GET, POST | `progress-updates/` | List or submit dated project progress reports. The latest reporting date appears first. |

Create a work item with `kind` (`task` or `milestone`), `title`,
`planned_start` and `planned_end`. Optional fields include `assignee`,
`predecessor`, `percent_complete` and `acceptance_note`. The server derives
the status from completion and activation. Predecessors must belong to the same
project and cannot create a cycle.

Submit progress with `reporting_date`, `percent_complete` (0 to 100) and
`summary`. `blockers` and `next_steps` are optional. Author and timestamp are
set by the server. Treat these percentages as self-reported.

Give project managers **Can add work item**, **Can change work item**, and
**Can add progress update**. An assigned officer can submit progress reports
with **Can add progress update** and can update completion on work items
assigned to them with **Can change work item**. Existing project visibility
rules apply to all tracking routes. Include the current CSRF token on writes.

### Evidence and review

Progress submissions and corrected revisions accept JSON for links, or multipart
form data with `evidence_file`. An update can include an HTTP(S) `evidence_url`
and one PDF, PNG or JPEG up to 5 MB. Download evidence through
`GET progress-updates/<id>/evidence/` within the same project path. Downloads
require project access.

Give designated reviewers **Can add progress review** and project access.
In React, open **Progress → Review queue**. A reviewer can approve or request
correction with a comment. Authors cannot review their own submissions.
Contributors can resubmit a correction request once, as a new linked revision.
Reattach evidence if it should appear on the new revision. The original
submission, its evidence, and its review remain available in **All updates**.

- `GET progress-updates/?review=pending` lists revisions awaiting the signed-in reviewer's decision.
- `POST progress-updates/<id>/review/` accepts `decision` (`approved` or `correction_requested`) and `comment`.
- `POST progress-updates/<id>/resubmit/` accepts the same fields as a new progress update.

## Archive and advanced project filters

The React project register has **Current** and **Archived** views. The
project list accepts `archived=true`, exact `project_id`, partial
`owner` username, and `start` / `end` dates. Date filters match projects
whose planned dates overlap the selected range.

Only the owner with **Can change project**, or a superuser, can archive a
completed or cancelled project. From project details, choose **Archive project**
or **Restore project**. The API uses `POST /api/v1/projects/<id>/archive/`
with `{"archived": true}` to archive or `{"archived": false}` to restore.
Archived projects remain readable, including their history, and stay
available in reports. Restore a project before editing it or adding records.

## Notification inbox

Active assignments notify the assignee. Approval and correction requests
notify the progress author. Opening or refreshing the inbox checks incomplete
milestones for the signed-in user. The assignee gets the deadline notice, or
the project owner if the milestone is unassigned. The upcoming window uses
`MILESTONE_LOOKAHEAD_DAYS`. Upcoming and overdue notices are generated once
per recipient, milestone and due date. The badge checks for unread notices
every 30 seconds while signed in.

- `GET /api/v1/notifications/` lists the user's notices. Add `unread=1` to filter.
- `GET /api/v1/notifications/count/` returns the unread count.
- `POST /api/v1/notifications/sync/` checks deadlines for the signed-in user.
- `POST /api/v1/notifications/<id>/read/` marks the user's notice as read.

Access is checked against current project visibility. These notices are
in-app. Deadline generation runs when the inbox opens or refreshes.

For browser-independent delivery, run `manage.py send_deadline_reminders`
from the backend environment on an hourly host schedule. The command uses
the same project permissions and duplicate protection as the inbox. The
deployment operator must register the schedule and use the site's database
configuration. Running the command twice does not duplicate reminders.

## Dashboard risk and status settings

An active project with reported or weighted progress gets a **schedule**
flag when it is at least `SCHEDULE_LAG_POINTS` percentage points behind the
planned percentage. The default is 10 points. Planned percentage assumes
even progress across the planned start and finish dates.

Managers and admins can save feedback or dismiss a flag from their own
dashboard, with a reason. The original snapshot, actor and response stay in
**Administration → Risk feedback**. A materially changed observation may
show again. Dismissing a flag does not change project or milestone status.

In **Administration → Project status settings**, add a setting for one of
the supported lifecycle codes to rename its on-screen label or disable it
for future assignments. Historical projects keep their status. Built-in
archive and reporting rules continue to use the original lifecycle code.

## Database

The local default is SQLite. To use a PostgreSQL database, set
`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` in the terminal
before running migrations. `POSTGRES_HOST` and `POSTGRES_PORT` default to
`localhost` and `5432`. Django migrations initialize the selected database.

The local server uses debug settings. With `DJANGO_DEBUG=0`, set a private
`DJANGO_SECRET_KEY` and the comma-separated `DJANGO_ALLOWED_HOSTS`.

## Budget, reports and analytics

- `GET /api/v1/projects/<id>/expenditure/` includes a paginated expenditure list and all-entry totals.
- `POST /api/v1/projects/<id>/expenditure/` requires **Can add expenditure** and project ownership (or superuser). Send `date`, `amount`, `category`, `reference` and optional `note`. Amounts use the project currency.
- `GET /api/v1/dashboard/` returns status counts, due milestones, spending and risk flags. Configure the date windows with `MILESTONE_LOOKAHEAD_DAYS` and `PROGRESS_STALE_DAYS`.
- `GET /api/v1/reports/` accepts `project_id`, `department`, `status`, `start` and `end`. Add `export=csv` for the full filtered CSV. Date filters select projects whose planned dates overlap the range.
- Use `export=xlsx` or `export=pdf` for dedicated downloads with the same filters and access checks.
- `GET /api/v1/projects/<id>/analytics/` returns EVM, the synthetic forecast and scenario results. Optional query parameters are `budget_cut`, `extra_days`, `price_increase` and `resource_loss`.

### Progress and audit controls

Managers can assign an optional integer weight from 1 to 1000 to each task
or milestone. Project progress is the weighted average when every active
work item has a weight. Otherwise the latest self-reported percentage is
used when available. The progress source appears in Overview and exports.

Changing approved budget or currency requires `budget_revision_reason` in
the project PATCH. The project history shows actor, timestamp, before/after
values and reason. Project access grants and revocations from Django admin
appear in project history. User and group role edits from Django admin appear
with before/after permissions in the relevant object's admin History.

To reproduce the Random Forest comparison, run
`python projects/evaluate_forest.py` from the backend folder. It uses 100
bootstrap trees per target and the same synthetic holdout split.
The live project forecast still uses the original logistic/linear models.
