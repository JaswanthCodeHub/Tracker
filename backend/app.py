from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parents[1]

# Vercel serverless has a read-only filesystem; only /tmp is writable.
_ON_VERCEL = bool(os.environ.get("VERCEL"))
DEFAULT_DB = Path("/tmp/equipment_tracker.db") if _ON_VERCEL else ROOT / "data" / "equipment_tracker.db"
VALID_CONDITIONS = {"excellent", "good", "fair", "damaged", "lost"}
RETURN_STATUSES = {"due", "overdue", "returned", "inspection", "claim_pending", "closed"}
BOOKING_STATUSES = {"pending", "approved", "active", "return_requested", "returned", "rejected", "cancelled"}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "frontend" / "templates"),
        static_folder=str(ROOT / "frontend" / "static"),
    )
    app.config.update(
        DATABASE=os.environ.get("TRACKER_DB", str(DEFAULT_DB)),
        SECRET_KEY=os.environ.get("SECRET_KEY", "sd-digitals-development-key"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    db_path = Path(app.config["DATABASE"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def add_missing_column(table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in get_db().execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            get_db().execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def init_db() -> None:
        db = get_db()
        db.executescript((ROOT / "backend" / "schema.sql").read_text(encoding="utf-8"))
        for column, definition in {
            "user_id": "INTEGER REFERENCES users(id)",
            "booking_id": "INTEGER REFERENCES bookings(id)",
            "return_request_status": "TEXT NOT NULL DEFAULT 'pending'",
            "deduction_status": "TEXT NOT NULL DEFAULT 'pending'",
        }.items():
            add_missing_column("equipment_returns", column, definition)
        seed_core_data()
        db.commit()

    def seed_core_data() -> None:
        db = get_db()
        accounts = [
            ("System Administrator", "admin@sd-digitals.com", "+91 90000 00001", "Admin@123", "admin"),
            ("Demo Customer", "user@sd-digitals.com", "+91 90000 00002", "User@123", "user"),
        ]
        for name, email, phone, password, role in accounts:
            db.execute(
                "INSERT OR IGNORE INTO users (name,email,phone,password_hash,role,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (name, email, phone, generate_password_hash(password), role, now(), now()),
            )
        if db.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
            inventory = [
                ("CAM-104", "Sony A7 IV", "Camera", "33 MP full-frame hybrid camera", 2500, 30000, 2, 2),
                ("CAM-210", "Canon EOS R6 Mark II", "Camera", "Full-frame mirrorless camera", 2800, 32000, 2, 2),
                ("LEN-208", "Canon RF 70-200mm", "Lens", "Professional telephoto zoom lens", 1400, 18000, 3, 3),
                ("GIM-312", "DJI RS 4 Pro", "Gimbal", "Cinema camera stabilizer", 1200, 15000, 2, 2),
                ("AUD-118", "Rode Wireless PRO", "Audio", "Dual-channel wireless microphone", 850, 10000, 4, 4),
                ("LGT-410", "Aputure 300D II", "Lighting", "Daylight LED studio light", 1100, 14000, 2, 2),
            ]
            db.executemany(
                "INSERT INTO equipment (code,name,category,description,daily_rate,deposit_amount,stock_total,stock_available,condition,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?, 'excellent','available',?,?)",
                [(*item, now(), now()) for item in inventory],
            )

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute("SELECT id,name,email,phone,role,active,created_at FROM users WHERE id=?", (user_id,)).fetchone()

    def auth_required(role: str | None = None):
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                user = current_user()
                if user is None or not user["active"]:
                    return jsonify(error="Authentication required"), 401
                if role and user["role"] != role:
                    return jsonify(error="Permission denied"), 403
                g.user = user
                return func(*args, **kwargs)
            return wrapped
        return decorator

    def parse_date(value: str, field: str) -> tuple[date | None, str | None]:
        try:
            return date.fromisoformat(value), None
        except (TypeError, ValueError):
            return None, f"{field} must be YYYY-MM-DD"

    def equipment_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def booking_dict(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["is_overdue"] = item["status"] in {"approved", "active", "return_requested"} and item["end_date"] < date.today().isoformat()
        return item

    def return_dict(row: sqlite3.Row, history: bool = False) -> dict:
        item = dict(row)
        item["is_overdue"] = item["status"] not in {"returned", "closed"} and item["return_due_date"] < date.today().isoformat()
        item["balance_refund"] = round(item["deposit_amount"] - item["deposit_deduction"], 2)
        if history:
            rows = get_db().execute("SELECT * FROM action_history WHERE return_id=? ORDER BY id DESC", (item["id"],)).fetchall()
            item["history"] = [dict(entry) for entry in rows]
        return item

    def add_history(return_id: int, action: str, from_status: str | None, to_status: str | None, note: str = "") -> None:
        get_db().execute(
            "INSERT INTO action_history (return_id,action,from_status,to_status,note) VALUES (?,?,?,?,?)",
            (return_id, action, from_status, to_status, note),
        )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="Equipment Return & Damage Tracker")

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", "")).strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        if user is None or not user["active"] or not check_password_hash(user["password_hash"], str(payload.get("password", ""))):
            return jsonify(error="Invalid email or password"), 401
        session.clear()
        session["user_id"] = user["id"]
        return jsonify(user={key: user[key] for key in ("id", "name", "email", "phone", "role")})

    @app.post("/api/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        phone = str(payload.get("phone", "")).strip()
        password = str(payload.get("password", ""))
        errors = []
        if not name:
            errors.append("Full name is required")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Valid email address is required")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters")
        if errors:
            return jsonify(error="Registration failed", details=errors), 400
        db = get_db()
        if db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone():
            return jsonify(error="An account with this email already exists"), 409
        cursor = db.execute(
            "INSERT INTO users (name,email,phone,password_hash,role,created_at,updated_at) VALUES (?,?,?,?, 'user',?,?)",
            (name, email, phone, generate_password_hash(password), now(), now()),
        )
        db.commit()
        session.clear()
        session["user_id"] = cursor.lastrowid
        user = db.execute("SELECT id,name,email,phone,role FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
        return jsonify(user=dict(user), message="Account created successfully"), 201

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify(message="Logged out")

    @app.get("/api/auth/me")
    @auth_required()
    def me():
        return jsonify(user=dict(g.user))

    @app.get("/api/profile")
    @auth_required()
    def get_profile():
        return jsonify(dict(g.user))

    @app.patch("/api/profile")
    @auth_required()
    def update_profile():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", g.user["name"])).strip()
        phone = str(payload.get("phone", g.user["phone"] or "")).strip()
        if not name:
            return jsonify(error="Name is required"), 400
        get_db().execute("UPDATE users SET name=?,phone=?,updated_at=? WHERE id=?", (name, phone, now(), g.user["id"]))
        get_db().commit()
        return jsonify(dict(get_db().execute("SELECT id,name,email,phone,role,active,created_at FROM users WHERE id=?", (g.user["id"],)).fetchone()))

    @app.get("/api/equipment")
    @auth_required()
    def list_equipment():
        rows = get_db().execute("SELECT * FROM equipment ORDER BY status, category, name").fetchall()
        return jsonify([equipment_dict(row) for row in rows])

    @app.post("/api/equipment")
    @auth_required("admin")
    def create_equipment():
        payload = request.get_json(silent=True) or {}
        required = ["code", "name", "category", "daily_rate", "deposit_amount", "stock_total"]
        missing = [field for field in required if payload.get(field) in (None, "")]
        if missing:
            return jsonify(error="Missing required fields", details=missing), 400
        try:
            stock = int(payload["stock_total"])
            rate = float(payload["daily_rate"])
            deposit = float(payload["deposit_amount"])
            if min(stock, rate, deposit) < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify(error="Stock and financial values must be non-negative numbers"), 400
        try:
            cursor = get_db().execute(
                "INSERT INTO equipment (code,name,category,description,daily_rate,deposit_amount,stock_total,stock_available,condition,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(payload["code"]).strip(), str(payload["name"]).strip(), payload["category"], payload.get("description", ""), rate, deposit, stock, stock, payload.get("condition", "excellent"), payload.get("status", "available"), now(), now()),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            return jsonify(error="Equipment code already exists"), 409
        return jsonify(equipment_dict(get_db().execute("SELECT * FROM equipment WHERE id=?", (cursor.lastrowid,)).fetchone())), 201

    @app.patch("/api/equipment/<int:equipment_id>")
    @auth_required("admin")
    def update_equipment(equipment_id: int):
        current = get_db().execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()
        if current is None:
            return jsonify(error="Equipment not found"), 404
        payload = request.get_json(silent=True) or {}
        total = int(payload.get("stock_total", current["stock_total"]))
        available = int(payload.get("stock_available", current["stock_available"]))
        if total < 0 or available < 0 or available > total:
            return jsonify(error="Available stock must be between zero and total stock"), 400
        get_db().execute(
            "UPDATE equipment SET name=?,category=?,description=?,daily_rate=?,deposit_amount=?,stock_total=?,stock_available=?,condition=?,status=?,updated_at=? WHERE id=?",
            (payload.get("name", current["name"]), payload.get("category", current["category"]), payload.get("description", current["description"]), float(payload.get("daily_rate", current["daily_rate"])), float(payload.get("deposit_amount", current["deposit_amount"])), total, available, payload.get("condition", current["condition"]), payload.get("status", current["status"]), now(), equipment_id),
        )
        get_db().commit()
        return jsonify(equipment_dict(get_db().execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()))

    @app.post("/api/bookings")
    @auth_required("user")
    def create_booking():
        payload = request.get_json(silent=True) or {}
        equipment = get_db().execute("SELECT * FROM equipment WHERE id=?", (payload.get("equipment_id"),)).fetchone()
        if equipment is None or equipment["status"] != "available" or equipment["stock_available"] < 1:
            return jsonify(error="Equipment is not available"), 400
        start, start_error = parse_date(payload.get("start_date"), "Start date")
        end, end_error = parse_date(payload.get("end_date"), "End date")
        if start_error or end_error:
            return jsonify(error=start_error or end_error), 400
        if end < start:
            return jsonify(error="End date cannot be before start date"), 400
        days = (end - start).days + 1
        cursor = get_db().execute(
            "INSERT INTO bookings (user_id,equipment_id,start_date,end_date,days,total_amount,deposit_amount,status,purpose,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'pending',?,?,?)",
            (g.user["id"], equipment["id"], start.isoformat(), end.isoformat(), days, days * equipment["daily_rate"], equipment["deposit_amount"], str(payload.get("purpose", "")).strip(), now(), now()),
        )
        get_db().commit()
        return jsonify(id=cursor.lastrowid, status="pending", message="Booking request submitted"), 201

    @app.get("/api/bookings")
    @auth_required()
    def list_bookings():
        sql = """SELECT b.*,u.name customer_name,u.email customer_email,e.name equipment_name,e.code equipment_code,e.category
                 FROM bookings b JOIN users u ON u.id=b.user_id JOIN equipment e ON e.id=b.equipment_id"""
        params = []
        if g.user["role"] == "user":
            sql += " WHERE b.user_id=?"
            params.append(g.user["id"])
        sql += " ORDER BY b.id DESC"
        return jsonify([booking_dict(row) for row in get_db().execute(sql, params).fetchall()])

    @app.patch("/api/bookings/<int:booking_id>/status")
    @auth_required("admin")
    def booking_status(booking_id: int):
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in BOOKING_STATUSES:
            return jsonify(error="Invalid booking status"), 400
        db = get_db()
        booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if booking is None:
            return jsonify(error="Booking not found"), 404
        old = booking["status"]
        if old == status:
            return jsonify(message="Status unchanged")
        if status in {"approved", "active"} and old == "pending":
            changed = db.execute("UPDATE equipment SET stock_available=stock_available-1,updated_at=? WHERE id=? AND stock_available>0", (now(), booking["equipment_id"]))
            if changed.rowcount == 0:
                return jsonify(error="No stock is available"), 400
        if status in {"rejected", "cancelled"} and old in {"approved", "active"}:
            db.execute("UPDATE equipment SET stock_available=MIN(stock_total,stock_available+1),updated_at=? WHERE id=?", (now(), booking["equipment_id"]))
        db.execute("UPDATE bookings SET status=?,updated_at=? WHERE id=?", (status, now(), booking_id))
        db.commit()
        return jsonify(message="Booking status updated", status=status)

    @app.post("/api/returns/request")
    @auth_required("user")
    def request_return():
        payload = request.get_json(silent=True) or {}
        booking = get_db().execute(
            """SELECT b.*,u.name customer_name,u.phone customer_phone,u.email customer_email,
                      e.name equipment_name,e.code equipment_code,e.category
               FROM bookings b JOIN users u ON u.id=b.user_id JOIN equipment e ON e.id=b.equipment_id
               WHERE b.id=? AND b.user_id=?""",
            (payload.get("booking_id"), g.user["id"]),
        ).fetchone()
        if booking is None or booking["status"] not in {"approved", "active"}:
            return jsonify(error="This rental is not eligible for return"), 400
        existing = get_db().execute("SELECT id FROM equipment_returns WHERE booking_id=?", (booking["id"],)).fetchone()
        if existing:
            return jsonify(error="A return request already exists"), 409
        requested_date = payload.get("actual_return_date") or date.today().isoformat()
        _, error = parse_date(requested_date, "Return date")
        if error:
            return jsonify(error=error), 400
        cursor = get_db().execute(
            """INSERT INTO equipment_returns
               (user_id,booking_id,customer_name,customer_phone,customer_email,equipment_name,equipment_code,category,
                rental_start_date,return_due_date,actual_return_date,deposit_amount,owner,notes,status,
                return_request_status,deduction_status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'inspection','pending','pending',?,?)""",
            (g.user["id"], booking["id"], booking["customer_name"], booking["customer_phone"] or "", booking["customer_email"], booking["equipment_name"], booking["equipment_code"], booking["category"], booking["start_date"], booking["end_date"], requested_date, booking["deposit_amount"], "Rental Admin", str(payload.get("notes", "")).strip(), now(), now()),
        )
        add_history(cursor.lastrowid, "Return requested", booking["status"], "inspection", payload.get("notes", ""))
        get_db().execute("UPDATE bookings SET status='return_requested',updated_at=? WHERE id=?", (now(), booking["id"]))
        get_db().commit()
        return jsonify(id=cursor.lastrowid, status="inspection", message="Return request submitted"), 201

    @app.get("/api/returns")
    @auth_required()
    def list_returns():
        clauses, params = [], []
        if g.user["role"] == "user":
            clauses.append("user_id=?")
            params.append(g.user["id"])
        status = request.args.get("status", "").strip()
        if status:
            clauses.append("status=?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = get_db().execute(f"SELECT * FROM equipment_returns{where} ORDER BY id DESC", params).fetchall()
        return jsonify([return_dict(row) for row in rows])

    @app.get("/api/returns/<int:return_id>")
    @auth_required()
    def get_return(return_id: int):
        row = get_db().execute("SELECT * FROM equipment_returns WHERE id=?", (return_id,)).fetchone()
        if row is None or (g.user["role"] == "user" and row["user_id"] != g.user["id"]):
            return jsonify(error="Return record not found"), 404
        return jsonify(return_dict(row, True))

    @app.post("/api/returns/<int:return_id>/process")
    @auth_required("admin")
    def process_return(return_id: int):
        payload = request.get_json(silent=True) or {}
        condition = payload.get("condition")
        if condition not in VALID_CONDITIONS:
            return jsonify(error="Invalid condition"), 400
        try:
            repair_cost = float(payload.get("repair_cost", 0))
            if repair_cost < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify(error="Repair cost must be non-negative"), 400
        db = get_db()
        current = db.execute("SELECT * FROM equipment_returns WHERE id=?", (return_id,)).fetchone()
        if current is None:
            return jsonify(error="Return record not found"), 404
        deduction = min(float(current["deposit_amount"]), repair_cost)
        if condition == "lost":
            deduction = float(current["deposit_amount"])
            status = "claim_pending"
            recommendation = "Escalate the lost equipment claim and deduct the held deposit."
        elif condition == "damaged" or repair_cost > 0:
            status = "claim_pending"
            recommendation = f"Repair claim requires review. Proposed deduction: INR {deduction:,.2f}."
        else:
            status = "closed"
            recommendation = "Inspection passed. Release the refundable deposit and close the rental."
        db.execute(
            """UPDATE equipment_returns SET actual_return_date=?,condition=?,damage_remarks=?,repair_cost=?,deposit_deduction=?,
               recommendation=?,status=?,return_request_status='processed',deduction_status=?,updated_at=? WHERE id=?""",
            (payload.get("actual_return_date") or current["actual_return_date"] or date.today().isoformat(), condition, str(payload.get("damage_remarks", "")).strip(), repair_cost, deduction, recommendation, status, "pending" if deduction else "not_required", now(), return_id),
        )
        add_history(return_id, "Inspection completed", current["status"], status, recommendation)
        if status == "closed" and current["booking_id"]:
            db.execute("UPDATE bookings SET status='returned',updated_at=? WHERE id=?", (now(), current["booking_id"]))
            booking = db.execute("SELECT equipment_id FROM bookings WHERE id=?", (current["booking_id"],)).fetchone()
            db.execute("UPDATE equipment SET stock_available=MIN(stock_total,stock_available+1),updated_at=? WHERE id=?", (now(), booking["equipment_id"]))
        db.commit()
        return jsonify(return_dict(db.execute("SELECT * FROM equipment_returns WHERE id=?", (return_id,)).fetchone(), True))

    @app.patch("/api/returns/<int:return_id>/deduction")
    @auth_required("admin")
    def update_deduction(return_id: int):
        payload = request.get_json(silent=True) or {}
        decision = payload.get("decision")
        if decision not in {"approved", "rejected"}:
            return jsonify(error="Decision must be approved or rejected"), 400
        db = get_db()
        current = db.execute("SELECT * FROM equipment_returns WHERE id=?", (return_id,)).fetchone()
        if current is None:
            return jsonify(error="Return record not found"), 404
        deduction = current["deposit_deduction"] if decision == "approved" else 0
        db.execute("UPDATE equipment_returns SET deposit_deduction=?,deduction_status=?,updated_at=? WHERE id=?", (deduction, decision, now(), return_id))
        add_history(return_id, "Deposit deduction reviewed", current["status"], current["status"], f"Deduction {decision}")
        db.commit()
        return jsonify(message=f"Deduction {decision}", deposit_deduction=deduction)

    @app.patch("/api/returns/<int:return_id>/status")
    @auth_required("admin")
    def update_return_status(return_id: int):
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in RETURN_STATUSES:
            return jsonify(error="Invalid return status"), 400
        db = get_db()
        current = db.execute("SELECT * FROM equipment_returns WHERE id=?", (return_id,)).fetchone()
        if current is None:
            return jsonify(error="Return record not found"), 404
        db.execute("UPDATE equipment_returns SET status=?,updated_at=? WHERE id=?", (status, now(), return_id))
        add_history(return_id, "Status updated", current["status"], status, str(payload.get("note", "")))
        if status == "closed" and current["status"] != "closed" and current["booking_id"]:
            booking = db.execute("SELECT equipment_id,status FROM bookings WHERE id=?", (current["booking_id"],)).fetchone()
            if booking and booking["status"] != "returned":
                db.execute("UPDATE bookings SET status='returned',updated_at=? WHERE id=?", (now(), current["booking_id"]))
                db.execute("UPDATE equipment SET stock_available=MIN(stock_total,stock_available+1),updated_at=? WHERE id=?", (now(), booking["equipment_id"]))
        db.commit()
        return jsonify(message="Return status updated", status=status)

    @app.get("/api/customers")
    @auth_required("admin")
    def customers():
        rows = get_db().execute(
            """SELECT u.id,u.name,u.email,u.phone,u.active,u.created_at,
                      COUNT(b.id) rental_count,COALESCE(SUM(b.total_amount),0) total_spend
               FROM users u LEFT JOIN bookings b ON b.user_id=u.id WHERE u.role='user'
               GROUP BY u.id ORDER BY u.id DESC"""
        ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.patch("/api/customers/<int:user_id>")
    @auth_required("admin")
    def update_customer(user_id: int):
        payload = request.get_json(silent=True) or {}
        active = payload.get("active")
        if active not in {True, False, 0, 1}:
            return jsonify(error="Active must be true or false"), 400
        customer = get_db().execute("SELECT id FROM users WHERE id=? AND role='user'", (user_id,)).fetchone()
        if customer is None:
            return jsonify(error="Customer not found"), 404
        get_db().execute("UPDATE users SET active=?,updated_at=? WHERE id=?", (1 if active else 0, now(), user_id))
        get_db().commit()
        return jsonify(message="Customer account updated", active=bool(active))

    @app.get("/api/dashboard")
    @auth_required()
    def dashboard():
        db = get_db()
        if g.user["role"] == "user":
            bookings = [booking_dict(row) for row in db.execute(
                """SELECT b.*,e.name equipment_name,e.code equipment_code,e.category,u.name customer_name,u.email customer_email
                   FROM bookings b JOIN equipment e ON e.id=b.equipment_id JOIN users u ON u.id=b.user_id
                   WHERE b.user_id=? ORDER BY b.id DESC""", (g.user["id"],)
            ).fetchall()]
            return jsonify(
                role="user", total_rentals=len(bookings), active=sum(x["status"] in {"approved", "active", "return_requested"} for x in bookings),
                pending=sum(x["status"] == "pending" for x in bookings), returned=sum(x["status"] == "returned" for x in bookings),
                overdue=sum(x["is_overdue"] for x in bookings), total_spend=round(sum(x["total_amount"] for x in bookings if x["status"] != "rejected"), 2), recent=bookings[:5],
            )
        returns = [return_dict(row) for row in db.execute("SELECT * FROM equipment_returns").fetchall()]
        return jsonify(
            role="admin", equipment=db.execute("SELECT COUNT(*) FROM equipment").fetchone()[0],
            available=db.execute("SELECT COALESCE(SUM(stock_available),0) FROM equipment WHERE status='available'").fetchone()[0],
            customers=db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
            bookings=db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], pending_bookings=db.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'").fetchone()[0],
            returns=len(returns), claims=sum(x["status"] == "claim_pending" for x in returns), overdue=sum(x["is_overdue"] for x in returns),
            repair_cost=round(sum(x["repair_cost"] for x in returns), 2), deductions=round(sum(x["deposit_deduction"] for x in returns), 2), recent=returns[:5],
        )

    @app.get("/api/reports/returns.csv")
    @auth_required("admin")
    def export_csv():
        fields = ["id", "customer_name", "equipment_name", "equipment_code", "return_due_date", "actual_return_date", "condition", "status", "repair_cost", "deposit_deduction", "deduction_status"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in get_db().execute("SELECT * FROM equipment_returns ORDER BY id"):
            writer.writerow({field: row[field] for field in fields})
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=equipment-returns.csv"})

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        print("Database initialized.")

    @app.cli.command("seed")
    def seed_command():
        init_db()
        print("Accounts and equipment are ready.")

    with app.app_context():
        init_db()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
