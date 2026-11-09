from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Project, ProjectAccess, ProgressUpdate


class ProgressReviewTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.officer = users.create_user(username="officer")
        self.reviewer = users.create_user(username="reviewer")
        self.outsider = users.create_user(username="outsider")
        for user, permissions in (
            (self.officer, ["add_progressupdate", "add_progressreview"]),
            (self.reviewer, ["view_project", "add_progressreview"]),
            (self.outsider, ["view_project", "add_progressreview"]),
        ):
            user.user_permissions.add(*Permission.objects.filter(
                content_type__app_label="projects", codename__in=permissions
            ))
        self.project = Project.objects.create(
            title="Road works", department="Public Works", owner=self.officer,
            planned_start="2026-11-10", planned_end="2027-01-15",
            approved_budget="1000.00", currency="NGN",
        )
        ProjectAccess.objects.create(project=self.project, user=self.reviewer)
        self.updates = reverse("progress-update-list", args=[self.project.pk])
        self.payload = {
            "reporting_date": "2026-11-14", "percent_complete": 40,
            "summary": "Site inspected.",
        }

    def test_upload_correction_resubmission_and_approval(self):
        self.client.force_login(self.officer)
        evidence = b"%PDF-1.7\nDemo evidence"
        created = self.client.post(self.updates, {
            **self.payload, "evidence_url": "https://example.com/inspection",
            "evidence_file": SimpleUploadedFile("inspection.pdf", evidence),
        }, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        original = created.data["id"]
        self.assertEqual(created.data["evidence_name"], "inspection.pdf")
        review_url = reverse("progress-review", args=[self.project.pk, original])
        evidence_url = reverse("progress-evidence", args=[self.project.pk, original])
        resubmit_url = reverse("progress-resubmit", args=[self.project.pk, original])
        self.assertEqual(self.client.post(review_url, {"decision": "approved"}).status_code, 403)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(evidence_url).status_code, 404)
        self.assertEqual(self.client.post(review_url, {"decision": "approved"}).status_code, 404)

        self.client.force_login(self.reviewer)
        download = self.client.get(evidence_url)
        self.assertEqual(download.content, evidence)
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(self.client.get(self.updates, {"review": "pending"}).data["count"], 1)
        self.assertEqual(self.client.post(review_url, {"decision": "correction_requested"}).status_code, 400)
        correction = {"decision": "correction_requested", "comment": "Add the inspection date."}
        self.assertEqual(self.client.post(review_url, correction).status_code, 201)
        self.assertEqual(self.client.post(review_url, correction).status_code, 400)
        self.assertEqual(self.client.get(self.updates, {"review": "pending"}).data["count"], 0)

        self.client.force_login(self.officer)
        revision = self.client.post(resubmit_url, {**self.payload, "summary": "Inspected 14 Nov."})
        self.assertEqual(revision.status_code, 201)
        self.assertEqual(revision.data["replaces"], original)
        self.assertEqual(self.client.post(resubmit_url, self.payload).status_code, 400)
        self.assertEqual(ProgressUpdate.objects.get(pk=original).summary, self.payload["summary"])

        self.client.force_login(self.reviewer)
        new_review = reverse("progress-review", args=[self.project.pk, revision.data["id"]])
        self.assertEqual(self.client.post(new_review, {"decision": "approved"}).status_code, 201)
        updates = self.client.get(self.updates).data["results"]
        self.assertEqual(updates[0]["review"]["decision"], "approved")
        self.assertEqual(updates[1]["review"]["comment"], correction["comment"])
        self.assertTrue(updates[1]["replaced"])

    def test_rejects_unsupported_evidence(self):
        self.client.force_login(self.officer)
        response = self.client.post(self.updates, {
            **self.payload, "evidence_file": SimpleUploadedFile("fake.pdf", b"<html>"),
        }, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("evidence_file", response.data)
        response = self.client.post(
            self.updates, {**self.payload, "evidence_url": "ftp://example.com/file"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("evidence_url", response.data)
