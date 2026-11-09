# Free live deployment

ProjectTrack runs as one Render Docker web service with a separate Neon
PostgreSQL database. React, the API and the administration console share
the HTTPS origin. The Docker build installs dependencies and builds React.
At runtime the container applies migrations, creates missing company role
groups, collects static assets and starts Gunicorn.

## Prepare the repository

Push the source to a private GitHub repository. Keep the root `Dockerfile`
and both application directories in the same repository. The ignore files
exclude virtual environments, local databases, secrets and build output.

## Configure Render and Neon

1. Create a Neon Free project and copy its PostgreSQL connection string from
   **Connect**. Keep the TLS query options in the URL.
2. In Render, choose **New → Web Service**, connect the repository, choose
   **Docker**, and select the **Free** instance. Use the repository root as
   the Docker build context and the root `Dockerfile`.
3. Add these environment variables under **Environment**.

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | Neon PostgreSQL connection string, including its TLS options |
   | `DJANGO_SECRET_KEY` | New random secret for this deployment |
   | `DJANGO_DEBUG` | `0` |
   | `DJANGO_ALLOWED_HOSTS` | Exact Render hostname, without `https://` or a trailing slash |

4. Set the health check path to `/api/v1/health/` and deploy. Use the
   supplied Render HTTPS URL for the app and its `/admin/` console.

Keep the Render-provided `PORT` setting. The service binds to port 10000
when no port is supplied. Use Render's TLS proxy in front of the container.

## Create the first live administrator

Run this once in PowerShell 7 from the project root. The local Python
environment needs the dependencies listed in `backend/requirements.txt`.
Enter the **same Neon URL** used on Render when prompted. This writes the
new admin to Neon and keeps the URL out of shell history.

```powershell
$env:DATABASE_URL = Read-Host 'Neon connection string' -MaskInput
try {
    .\backend\.venv\Scripts\python.exe .\backend\manage.py createsuperuser
} finally {
    Remove-Item Env:DATABASE_URL
}
```

Use new live credentials. The hosted database starts empty, and local demo
accounts are separate. Sign in and create one account per tester in
**Administration → Users**. Then assign the appropriate group and test
project access from separate browser sessions.

## Verify the live service

- Open the HTTPS URL and `/api/v1/health/`.
- Sign in and confirm the Administration link opens the styled Admin console.
- Create a test project, assign its manager and check both PDF and Excel downloads.
- Test two officers with different tasks and confirm that revoking access
  blocks the removed employee.

The free role test can use the inbox to generate deadline reminders.
The `send_deadline_reminders` management command is available for a host
scheduler when recurring execution is needed.
