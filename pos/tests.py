import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from pos.models import Branch, PosProfile, Product, ProductStock, Tenant

User = get_user_model()


class SignupLoginTests(APITestCase):
    def test_signup_creates_tenant_and_admin_profile(self):
        url = reverse("pos-signup")
        response = self.client.post(url, {
            "business_name": "Casper's Shop",
            "name": "Casper Moyo",
            "email": "casper@example.com",
            "password": "a-strong-password-123",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "admin")
        self.assertIn("access", response.data["tokens"])

        user = User.objects.get(email="casper@example.com")
        self.assertTrue(hasattr(user, "posprofile"))
        self.assertEqual(Tenant.objects.count(), 1)

    def test_signup_rejects_duplicate_email(self):
        url = reverse("pos-signup")
        payload = {
            "business_name": "Shop A", "name": "A", "email": "dup@example.com", "password": "a-strong-password-123",
        }
        self.client.post(url, payload, format="json")
        response = self.client.post(url, {**payload, "business_name": "Shop B"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Tenant.objects.count(), 1)  # second signup must not create an orphan tenant

    def test_login_correct_and_incorrect_password(self):
        self.client.post(reverse("pos-signup"), {
            "business_name": "Shop", "name": "A", "email": "a@example.com", "password": "a-strong-password-123",
        }, format="json")

        ok = self.client.post(reverse("pos-login"), {"email": "a@example.com", "password": "a-strong-password-123"}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        bad = self.client.post(reverse("pos-login"), {"email": "a@example.com", "password": "wrong"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rejects_user_with_no_pos_profile(self):
        # e.g. an existing app/news account that never signed up for POS
        User.objects.create_user(username="other@example.com", email="other@example.com", password="whatever123")
        response = self.client.post(reverse("pos-login"), {"email": "other@example.com", "password": "whatever123"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GoogleAuthTests(APITestCase):
    @patch("pos.auth.google_id_token.verify_oauth2_token")
    def test_first_time_google_signin_creates_tenant(self, mock_verify):
        mock_verify.return_value = {
            "sub": "google-sub-123", "email": "g@example.com", "email_verified": True, "name": "G User",
        }
        response = self.client.post(reverse("pos-google-auth"), {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PosProfile.objects.filter(google_sub="google-sub-123").count(), 1)

    @patch("pos.auth.google_id_token.verify_oauth2_token")
    def test_repeat_google_signin_logs_in_same_profile(self, mock_verify):
        mock_verify.return_value = {
            "sub": "google-sub-456", "email": "g2@example.com", "email_verified": True, "name": "G2 User",
        }
        first = self.client.post(reverse("pos-google-auth"), {"credential": "fake-token"}, format="json")
        second = self.client.post(reverse("pos-google-auth"), {"credential": "fake-token"}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)  # login, not another signup
        self.assertEqual(Tenant.objects.filter(name__icontains="G2").count(), 1)

    @patch("pos.auth.google_id_token.verify_oauth2_token")
    def test_unverified_google_email_rejected(self, mock_verify):
        mock_verify.return_value = {
            "sub": "google-sub-789", "email": "g3@example.com", "email_verified": False, "name": "G3",
        }
        response = self.client.post(reverse("pos-google-auth"), {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SyncTests(APITestCase):
    def setUp(self):
        signup = self.client.post(reverse("pos-signup"), {
            "business_name": "Sync Test Biz", "name": "Owner", "email": "owner@example.com", "password": "a-strong-password-123",
        }, format="json")
        self.access_token = signup.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        self.user = User.objects.get(email="owner@example.com")
        self.tenant = self.user.posprofile.tenant
        self.branch = Branch.objects.create(id=uuid.uuid4(), tenant=self.tenant, name="Harare CBD")

    def test_push_product_and_sale_applies_stock_delta(self):
        product_id = uuid.uuid4()
        sale_id = uuid.uuid4()
        item_id = uuid.uuid4()
        now = timezone.now().isoformat()

        body = {"changes": {
            "products": [{
                "id": str(product_id), "name": "Bread Loaf", "sku": "BR-1", "category": "Bakery",
                "price": "1.10", "cost": "0.75", "unlimited": False, "updated_at": now,
            }],
            "sales": [{
                "id": str(sale_id), "branch": str(self.branch.id), "customer": None,
                "customer_name_snapshot": "Walk-in", "total": "2.20", "occurred_at": now,
                "items": [{"id": str(item_id), "product": str(product_id), "name_snapshot": "Bread Loaf", "price_snapshot": "1.10", "qty": 2}],
            }],
        }}

        response = self.client.post(reverse("pos-sync-push"), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        stock = ProductStock.objects.get(product_id=product_id, branch=self.branch)
        self.assertEqual(stock.quantity, -2)  # sold before any purchase — correctly negative

    def test_duplicate_sale_push_is_idempotent(self):
        product_id, sale_id, item_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        now = timezone.now().isoformat()
        body = {"changes": {
            "products": [{"id": str(product_id), "name": "Rice 5kg", "price": "6.00", "cost": "4.40", "updated_at": now}],
            "sales": [{
                "id": str(sale_id), "branch": str(self.branch.id), "customer": None,
                "customer_name_snapshot": "Walk-in", "total": "6.00", "occurred_at": now,
                "items": [{"id": str(item_id), "product": str(product_id), "name_snapshot": "Rice 5kg", "price_snapshot": "6.00", "qty": 1}],
            }],
        }}

        self.client.post(reverse("pos-sync-push"), body, format="json")
        second = self.client.post(reverse("pos-sync-push"), body, format="json")

        self.assertEqual(second.data["applied"]["sales"], [])  # already synced — skipped
        stock = ProductStock.objects.get(product_id=product_id, branch=self.branch)
        self.assertEqual(stock.quantity, -1)  # not -2 — duplicate push must not double-decrement

    def test_purchase_then_sale_nets_correctly_and_pull_returns_everything(self):
        product_id = uuid.uuid4()
        now = timezone.now().isoformat()
        self.client.post(reverse("pos-sync-push"), {"changes": {
            "products": [{"id": str(product_id), "name": "Sugar 2kg", "price": "2.80", "cost": "2.00", "updated_at": now}],
        }}, format="json")
        self.client.post(reverse("pos-sync-push"), {"changes": {
            "purchases": [{
                "id": str(uuid.uuid4()), "branch": str(self.branch.id), "product": str(product_id),
                "product_name_snapshot": "Sugar 2kg", "qty": 10, "cost": "2.00", "total": "20.00", "occurred_at": now,
            }],
        }}, format="json")
        self.client.post(reverse("pos-sync-push"), {"changes": {
            "sales": [{
                "id": str(uuid.uuid4()), "branch": str(self.branch.id), "customer": None,
                "customer_name_snapshot": "Walk-in", "total": "5.60", "occurred_at": now,
                "items": [{"id": str(uuid.uuid4()), "product": str(product_id), "name_snapshot": "Sugar 2kg", "price_snapshot": "2.80", "qty": 2}],
            }],
        }}, format="json")

        stock = ProductStock.objects.get(product_id=product_id, branch=self.branch)
        self.assertEqual(stock.quantity, 8)  # 10 purchased - 2 sold

        pull = self.client.get(reverse("pos-sync-pull"))
        self.assertEqual(pull.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pull.data["resources"]["products"]), 1)
        self.assertEqual(len(pull.data["resources"]["purchases"]), 1)
        self.assertEqual(len(pull.data["resources"]["sales"]), 1)

    def test_stale_product_update_is_rejected_as_conflict(self):
        product_id = uuid.uuid4()
        now = timezone.now().isoformat()
        self.client.post(reverse("pos-sync-push"), {"changes": {
            "products": [{"id": str(product_id), "name": "Original Name", "price": "1.00", "cost": "0.50", "updated_at": now}],
        }}, format="json")

        older = (timezone.now() - timezone.timedelta(days=1)).isoformat()
        response = self.client.post(reverse("pos-sync-push"), {"changes": {
            "products": [{"id": str(product_id), "name": "Stale Name", "price": "1.00", "cost": "0.50", "updated_at": older}],
        }}, format="json")

        self.assertEqual(response.data["applied"]["products"], [])
        self.assertEqual(len(response.data["conflicts"]["products"]), 1)
        self.assertEqual(Product.objects.get(id=product_id).name, "Original Name")

    def test_pull_and_push_require_authentication(self):
        self.client.credentials()  # drop the auth header
        response = self.client.get(reverse("pos-sync-pull"))
        # With both SessionAuthentication and JWTAuthentication registered,
        # DRF returns 403 (not 401) for missing credentials — only
        # SessionAuthentication would trigger the 401 + WWW-Authenticate
        # challenge, and it's not the one in play for an API-only client.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
