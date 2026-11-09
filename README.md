# ProjectTrack

ProjectTrack is a responsive React and Django website for the University of Sindh project management case study. The local demo uses fictional Imo State public project records.

## Start the website

For a hosted test, follow the [free deployment guide](DEPLOYMENT.md).

Run the following from the project folder in PowerShell. If the virtual environment and dependencies are already installed, start at the migration command.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_company_roles
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_demo YOUR_USERNAME
.\.venv\Scripts\python.exe manage.py runserver
```

In a second PowerShell terminal, from the project folder, run:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://localhost:5173** and sign in with the Django account you created. Vite proxies API requests to Django on port 8000. The default local database is SQLite. See the [backend guide](backend/README.md) for PostgreSQL configuration and project permissions.

## Demonstration

1. Sign in. The dashboard shows project totals, upcoming milestones, recorded spending by currency and risk reasons.
2. Open **Projects → Owerri Road Rehabilitation**. View the overdue checkpoint under **Tasks & milestones** and its dated status report under **Progress**.
3. Open **Budget**. Enter a dated expenditure with a reference. Compare the remaining balance and variance, then inspect the new entry in **History**.
4. Open **Analytics**. Inspect EVM indicators and the synthetic forecast. Set budget cut to 10%, additional delay to 5 days, price increase to 8% and resource loss to 15%. Compare the three scenarios.
5. Open **Reports**. Filter to Public Works and download CSV, Excel or PDF.

Run `seed_demo` on an existing user. It adds four fixed demo projects on the first run and preserves them on later runs. Sign in with the account created by `createsuperuser` and open **Administration** in the sidebar. In **Users**, create a staff member's account, then add the user to the appropriate group on their edit page. For roles that need access to an existing project, add a record in **Project access**. Only Django staff accounts see **Administration** in the sidebar. Project users can sign in with their assigned credentials.

## Company workflow

Set up a separate installation and database for each company. The default
groups come from `setup_company_roles`. Assign each employee the group
appropriate to their duties in **Administration → Users**.

1. An administrator opens **Projects → New project** and selects its manager.
   For an existing project, use **Team → Assign manager**.
2. The project manager opens **Team → Add employee** to grant access. In
   **Tasks & milestones**, the manager assigns work using the assignee list.
3. An officer starts at **My assigned work** and sees only their own tasks
   and submissions. A designated reviewer can review project submissions.
   An assigned auditor can view project financial and audit information.
4. After handover, the manager selects **Remove access** in **Team**.
   The employee loses access immediately. Their account and historical work
   stay available to authorized users. Reassign any unfinished work as needed.

## Calculations and model

- Budget remaining equals approved budget minus recorded expenditure. Variance uses the opposite sign, so a positive variance means spending exceeds the baseline. Expenditure is recorded in the project's currency. Audit history preserves baseline revisions.
- EVM allocates the baseline evenly across active milestones. Planned value uses milestones due as of today, earned value uses recorded milestone completion and actual cost uses dated expenditure through today. Ratios show as unavailable where a denominator is zero.
- The demo trains a logistic model for delay classification and linear models for days late and final cost as a share of budget. The included dataset contains 700 synthetic snapshots, one per fictional project. The split is 560 train and 140 held out. Held-out results were 85.0% delay accuracy (60.7% majority baseline), 5.05 days mean absolute error and 3.95 percentage points mean absolute error for final cost as a share of approved budget. These measurements apply to the synthetic generator.
- Scenario comparisons apply 50%, 100% and 150% of the input shocks to best, base and worst cases. The simulator does not write project data.

Reproduce the dataset and metrics from the project folder with `python backend/projects/train_forecast.py`. The dataset and versioned model are in `backend/projects/forecast_data/`.

The Random Forest comparison uses the same holdout and is reproduced with
`python backend/projects/evaluate_forest.py`. It achieved 86.43% delay
accuracy, 5.59 days mean absolute delay error and 5.02 percentage points
mean absolute cost-ratio error. The live forecast keeps the original
models, which had lower error on the two numeric targets.

## Verification and scope

From `backend`, run `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` and `.\.venv\Scripts\python.exe manage.py test`. The automated suite covers session/CSRF checks, project access, work item dependencies, budget validation, risk rules, report isolation and scenario calculations. From `frontend`, run `npm.cmd run build`.

The local delivery check applied the migrations to SQLite, passed all 11 Django
tests, and built the React bundle. A Microsoft Edge smoke test verified sign-in,
dashboard and project navigation, expenditure entry, scenario recalculation,
filtered CSV, a 390 px report viewport, and sign-out.

The **Progress** tab supports evidence attachments and a reviewer queue.
See the [review permissions and workflow](backend/README.md#evidence-and-review)
to set up a separate contributor and reviewer. The coursework prototype uses
dashboard risk flags and dedicated report downloads. The **Notifications** inbox
shows task assignments, review decisions and upcoming or overdue milestones.

