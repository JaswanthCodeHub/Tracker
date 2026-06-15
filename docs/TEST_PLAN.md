# Test Plan

| ID | Scenario | Expected result |
|---|---|---|
| T01 | Open health endpoint | HTTP 200 and `status: ok` |
| T02 | Create return with valid fields | HTTP 201, status `due`, history created |
| T03 | Omit required fields | HTTP 400 with field-level errors |
| T04 | Submit negative deposit | HTTP 400 |
| T05 | List records | JSON array ordered by due date |
| T06 | Search by customer/equipment/code | Only matching records returned |
| T07 | Open return detail | Full record and history returned |
| T08 | Process good return | Status becomes `closed`, deduction is zero |
| T09 | Process damaged return | Status becomes `claim_pending` |
| T10 | Repair exceeds deposit | Deduction is capped at deposit amount |
| T11 | Process lost equipment | Full deposit deducted and claim opened |
| T12 | Change to invalid status | HTTP 400 with allowed statuses |
| T13 | View overdue record | Overdue alert badge displayed |
| T14 | Dashboard with no records | Zero metrics and empty state |
| T15 | Export CSV | Download contains report headers and records |
| T16 | Mobile viewport | Dashboard and forms remain usable |
| T17 | User login | User portal opens with user navigation only |
| T18 | Admin login | Admin portal opens with admin navigation only |
| T19 | Customer calls admin API | HTTP 403 permission error |
| T20 | Book available equipment | Pending booking is created with calculated amount |
| T21 | Admin approves booking | Equipment available stock decreases once |
| T22 | User requests return | Return record and action history are created |
| T23 | Admin processes clean return | Booking closes and stock is released |
| T24 | Admin processes damaged return | Claim and proposed deduction are created |
| T25 | Admin reviews deduction | Approval/rejection is recorded |
| T26 | Update profile | Name and phone are saved |

Run automated coverage with `python -m unittest discover -s tests -v`.
