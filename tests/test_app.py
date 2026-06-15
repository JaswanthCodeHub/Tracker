import tempfile
import unittest
from pathlib import Path

from backend.app import create_app


class TrackerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.temp_dir.name) / "test.db"), "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, role="user"):
        credentials = {
            "user": ("user@sd-digitals.com", "User@123"),
            "admin": ("admin@sd-digitals.com", "Admin@123"),
        }
        email, password = credentials[role]
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def logout(self):
        return self.client.post("/api/auth/logout")

    def create_booking(self):
        equipment = self.client.get("/api/equipment").get_json()[0]
        response = self.client.post("/api/bookings", json={
            "equipment_id": equipment["id"], "start_date": "2026-06-12", "end_date": "2026-06-14", "purpose": "Test shoot"
        })
        return response.get_json()["id"]

    def approve_booking(self, booking_id):
        self.logout(); self.login("admin")
        response = self.client.patch(f"/api/bookings/{booking_id}/status", json={"status": "approved"})
        self.logout(); self.login("user")
        return response

    def test_health_and_authentication(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)
        response = self.login("user")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["role"], "user")

    def test_invalid_login_is_rejected(self):
        response = self.client.post("/api/auth/login", json={"email": "user@sd-digitals.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_create_account_logs_in_new_user(self):
        response = self.client.post("/api/auth/register", json={
            "name": "New Customer", "email": "new.customer@example.com", "phone": "9876543210", "password": "Secret123"
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["user"]["role"], "user")
        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.get_json()["role"], "user")

    def test_duplicate_account_is_rejected(self):
        payload = {"name": "New Customer", "email": "duplicate@example.com", "password": "Secret123"}
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 201)
        self.logout()
        response = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(response.status_code, 409)

    def test_short_registration_password_is_rejected(self):
        response = self.client.post("/api/auth/register", json={"name": "Short", "email": "short@example.com", "password": "123"})
        self.assertEqual(response.status_code, 400)

    def test_user_can_view_equipment_and_book(self):
        self.login("user")
        equipment = self.client.get("/api/equipment").get_json()
        self.assertGreaterEqual(len(equipment), 6)
        booking_id = self.create_booking()
        bookings = self.client.get("/api/bookings").get_json()
        self.assertEqual(bookings[0]["id"], booking_id)
        self.assertEqual(bookings[0]["status"], "pending")
        self.assertGreater(bookings[0]["total_amount"], 0)

    def test_admin_can_add_equipment(self):
        self.login("admin")
        response = self.client.post("/api/equipment", json={
            "code": "TST-001", "name": "Test Light", "category": "Lighting", "daily_rate": 500,
            "deposit_amount": 5000, "stock_total": 2, "description": "Testing inventory"
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["stock_available"], 2)

    def test_user_cannot_access_admin_customer_data(self):
        self.login("user")
        self.assertEqual(self.client.get("/api/customers").status_code, 403)
        self.assertEqual(self.client.post("/api/equipment", json={}).status_code, 403)

    def test_admin_approves_booking_and_stock_decreases(self):
        self.login("user")
        equipment = self.client.get("/api/equipment").get_json()[0]
        booking_id = self.create_booking()
        response = self.approve_booking(booking_id)
        self.assertEqual(response.status_code, 200)
        self.logout(); self.login("admin")
        updated = next(x for x in self.client.get("/api/equipment").get_json() if x["id"] == equipment["id"])
        self.assertEqual(updated["stock_available"], equipment["stock_available"] - 1)

    def test_complete_clean_return_workflow(self):
        self.login("user")
        booking_id = self.create_booking()
        self.approve_booking(booking_id)
        response = self.client.post("/api/returns/request", json={"booking_id": booking_id, "actual_return_date": "2026-06-14"})
        self.assertEqual(response.status_code, 201)
        return_id = response.get_json()["id"]
        self.logout(); self.login("admin")
        processed = self.client.post(f"/api/returns/{return_id}/process", json={"condition": "good", "repair_cost": 0}).get_json()
        self.assertEqual(processed["status"], "closed")
        self.assertEqual(processed["deposit_deduction"], 0)
        self.assertGreaterEqual(len(processed["history"]), 2)

    def test_damage_claim_and_deduction_decision(self):
        self.login("user")
        booking_id = self.create_booking()
        self.approve_booking(booking_id)
        return_id = self.client.post("/api/returns/request", json={"booking_id": booking_id}).get_json()["id"]
        self.logout(); self.login("admin")
        processed = self.client.post(f"/api/returns/{return_id}/process", json={
            "condition": "damaged", "repair_cost": 50000, "damage_remarks": "Body and sensor damage"
        }).get_json()
        self.assertEqual(processed["status"], "claim_pending")
        self.assertEqual(processed["deposit_deduction"], processed["deposit_amount"])
        decision = self.client.patch(f"/api/returns/{return_id}/deduction", json={"decision": "approved"})
        self.assertEqual(decision.status_code, 200)

    def test_user_profile_update(self):
        self.login("user")
        response = self.client.patch("/api/profile", json={"name": "Updated Customer", "phone": "1234567890"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], "Updated Customer")

    def test_admin_can_disable_customer_account(self):
        self.login("admin")
        customer_id = self.client.get("/api/customers").get_json()[0]["id"]
        response = self.client.patch(f"/api/customers/{customer_id}", json={"active": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["active"])

    def test_admin_can_close_claim_from_status_updates(self):
        self.login("user")
        booking_id = self.create_booking()
        self.approve_booking(booking_id)
        return_id = self.client.post("/api/returns/request", json={"booking_id": booking_id}).get_json()["id"]
        self.logout(); self.login("admin")
        self.client.post(f"/api/returns/{return_id}/process", json={"condition": "damaged", "repair_cost": 1000})
        response = self.client.patch(f"/api/returns/{return_id}/status", json={"status": "closed", "note": "Claim settled"})
        self.assertEqual(response.status_code, 200)
        self.logout(); self.login("user")
        booking = self.client.get("/api/bookings").get_json()[0]
        self.assertEqual(booking["status"], "returned")

    def test_role_specific_dashboards_and_report(self):
        self.login("user")
        self.assertEqual(self.client.get("/api/dashboard").get_json()["role"], "user")
        self.assertEqual(self.client.get("/api/reports/returns.csv").status_code, 403)
        self.logout(); self.login("admin")
        dashboard = self.client.get("/api/dashboard").get_json()
        self.assertEqual(dashboard["role"], "admin")
        self.assertIn("customers", dashboard)
        self.assertEqual(self.client.get("/api/reports/returns.csv").status_code, 200)


if __name__ == "__main__":
    unittest.main()
