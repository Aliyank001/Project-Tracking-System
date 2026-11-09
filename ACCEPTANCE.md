# ProjectTrack SRS acceptance checklist

Verification used an isolated SQLite test database and temporary company
accounts. The Django suite passed 26 tests. The React production build
passed. The results below are engineering checks for local acceptance.

| SRS ID | Acceptance check | Result and evidence |
| --- | --- | --- |
| AT-01 | Create a valid project and find it in the authorized register | Pass. The project API created a unique ID and returned the saved project. Edge verified admin creation and manager assignment. |
| AT-02 | Reject a missing title or an invalid planned date range | Pass. The project validation test confirmed rejected input and field errors. |
| AT-03 | Deny access to a restricted project | Pass. Project and work-item tests rejected direct access by unauthorized users. Edge verified project revocation for an employee. |
| AT-04 | Reject completion outside 0–100 | Pass. The tracking API rejected invalid progress. |
| AT-05 | Calculate recorded expenditure, remaining budget and variance | Pass. The delivery tests used known amounts and checked the returned totals and variance. |
| AT-06 | Flag an incomplete overdue milestone with a reason | Pass. The dashboard risk test produced an overdue flag for an incomplete milestone. |
| AT-07 | Record who changed a material project field and when | Pass. Tests checked the project audit event, actor, previous value, revised value and budget revision reason. |
| AT-08 | Apply report filters and respect access scope | Pass. Delivery tests checked filtered rows, CSV, Excel, PDF and chart scope. Edge verified report access as the assigned auditor. |
| AT-09 | Keep project registration, progress and reports working when the forecast is unavailable | Pass. The test simulated a missing forecast model and confirmed that Analytics showed insufficient data while all three core workflows completed. |
| AT-10 | Show the risk or insight method, reason, timestamp and limitations | Pass. The schedule flag returned its rule, planned and actual percentages and timestamp. The dashboard identifies the even-progress assumption. Synthetic forecast output shows its method, reporting date and data limitation. |

## Role walkthrough in Edge

- Admin created a project and appointed a manager.
- Manager granted access, assigned separate tasks and revoked access after handover.
- Officer saw only their own task, completed it and submitted progress.
- Reviewer approved the officer's progress in the review queue.
- Auditor viewed project history and reports with no project edit action.

## Deployment checks

The deadline command was run twice in tests and generated only one reminder
per eligible event. Recurring execution requires configuring the deployment
host scheduler. The test results cover the local SQLite environment.
