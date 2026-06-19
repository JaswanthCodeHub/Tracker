# Equipment Return & Damage Tracker

A role-based rental operations application for SD Digitals. Customers can book and return equipment while administrators manage inventory, customers, inspections, damage claims, deposit deductions, workflow statuses, and reports.

## Login details

| Portal | Email | Password |
|---|---|---|
| User | `user@sd-digitals.com` | `User@123` |
| Admin | `admin@sd-digitals.com` | `Admin@123` |

Both roles use the same login page. The application opens the correct portal after authentication.

## User side

- Login / Register / Forgot Password
- Dashboard with rental totals and recent activity
- Book Equipment catalogue with rate, deposit, and availability
- Return Equipment request workflow
- My Rentals history and status tracking
- Profile editing

## Admin side

- Login
- Operations dashboard
- Equipment Management: add, edit, stock, condition, and availability
- Customer Management: rental totals and enable/disable accounts
- Return Requests: inspect condition and record damage
- Damage Reports: damaged/lost equipment and repair costs
- Deposit Deduction: approve or reject proposed deductions
- Status Updates: booking and return workflow control
- Reports: operational totals, financial summary, and CSV export

## Technology

- Frontend: responsive HTML, CSS, and vanilla JavaScript
- Backend: Python Flask REST API
- Database: SQLite with relational users, equipment, bookings, returns, and history
- Authentication: password hashing and secure HTTP-only Flask sessions

## Quick start

```powershell
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The automated suite covers login, registration, password reset, permissions, inventory, bookings, approval, stock updates, return requests, clean inspections, damage claims, deductions, profiles, dashboards, and reports.

## Main API groups

- `/api/auth/*` — login, register, forgot password, OTP verification, reset password, logout, and current account
- `/api/profile` — user/admin profile
- `/api/equipment` — catalogue and inventory management
- `/api/bookings` — booking requests and status management
- `/api/returns/*` — return requests, inspections, deductions, and statuses
- `/api/customers` — admin customer management
- `/api/dashboard` — role-specific dashboard data
- `/api/reports/returns.csv` — admin CSV report

## Project structure

```
Equipment_Return_Damage_Tracker/
│
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (SMTP, secret key)
├── .gitignore                # Git ignore rules
├── README.md                 # This file
│
├── backend/                  # Flask API layer
│   ├── __init__.py           # Package marker
│   ├── app.py                # Application factory, routes, and business logic
│   └── schema.sql            # SQLite table definitions and indexes
│
├── frontend/                 # Client-side UI
│   ├── templates/
│   │   └── index.html        # Single-page app shell
│   └── static/
│       ├── app.js            # UI logic, rendering, and API calls
│       └── styles.css        # Responsive styles
│
├── data/                     # SQLite database (auto-created at runtime)
│   └── equipment_tracker.db
│
├── tests/                    # Automated test suite
│   └── test_app.py           # End-to-end workflow tests
│
└── docs/                     # Project documentation
    ├── PROJECT_REPORT.md     # Detailed project report
    ├── TEST_PLAN.md          # Testing strategy and plan
    └── DEPLOYMENT.md         # Deployment instructions
```
