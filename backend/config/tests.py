from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class SessionApiTests(TestCase):
    def test_session_requires_csrf_and_ends_on_logout(self):
        get_user_model().objects.create_user(username="tester", password="Test-password-62")
        client = Client(enforce_csrf_checks=True)
        credentials = {"username": "tester", "password": "Test-password-62"}
        login_url = reverse("login")
        current_user_url = reverse("current-user")

        self.assertEqual(client.get(reverse("health")).json(), {"status": "ok"})
        self.assertEqual(client.get(current_user_url).status_code, 403)
        self.assertEqual(client.post(login_url, credentials, content_type="application/json").status_code, 403)

        csrf_token = client.get(reverse("csrf")).json()["csrfToken"]
        response = client.post(
            login_url,
            credentials,
            content_type="application/json",
            headers={"X-CSRFToken": csrf_token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get(current_user_url).json()["username"], "tester")

        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        response = client.post(
            reverse("logout"),
            headers={"X-CSRFToken": response.json()["csrfToken"]},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(client.get(current_user_url).status_code, 403)
