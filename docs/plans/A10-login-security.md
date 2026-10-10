# A10 — Login security

> **Summary:** Ridanshi asked for proper authentication on the login. The login already stored passwords with bcrypt and kept a signed session in an httpOnly cookie. This plan closes the gaps around that: limiting password guessing, hiding which usernames exist, rules for new passwords, a change-password screen, sessions that end when the password changes, and protective response headers.
> **Last updated:** 2026-10-10 19:52 IST
> **Status:** built and tested on branch `a/web-textile`.

**Touches Hritwik's files** (small, listed so he can review): `app/core/auth.py` (work factor from one place, a password fingerprint in the session, checked in `current_user`), `app/modules/auth/router.py` (login uses the guard and the dummy hash, new `POST /auth/change-password`), `app/main.py` (one line adding the headers), `tests/conftest.py` (an autouse fixture that clears the guess counters between tests), and `contracts/` regenerated. All new logic is in new files: `app/core/passwords.py`, `app/core/login_guard.py`, `app/core/security_headers.py`.

## What was already right (kept)

- Passwords are hashed with **bcrypt** (salted, slow on purpose); the password is never stored, logged or returned.
- The session is a signed token in an **httpOnly, SameSite=Lax** cookie, so scripts on a page cannot read it and other sites cannot make the browser send it on a form post. `Secure` is switched on with `COOKIE_SECURE=true` for HTTPS.
- A wrong username and a wrong password get the same answer, and passwords longer than bcrypt can use (72 bytes) are refused instead of silently cut.

## What was added

| Gap | What was done |
|---|---|
| **Unlimited guessing** | Five wrong passwords for one username in 15 minutes lock that username for 15 minutes (`TOO_MANY_ATTEMPTS`, 429, with the minutes left). The lock is the same for a name that does not exist, so it reveals nothing, and it refuses even the right password while it lasts. A higher limit per address (100) stops one machine trying many names. State is in memory (resets on restart, per process); tune with `LOGIN_MAX_FAILURES` and `LOGIN_LOCK_MINUTES`. Memory is bounded (5,000 names). |
| **Timing leak** | A username that does not exist used to return faster than a wrong password. Now one bcrypt check always runs, against a dummy hash when the user is missing. |
| **Old, weaker hashes** | The work factor is one setting (12). A stored hash made with a lower factor is replaced on that user's next successful login. |
| **No way to change a password** | `POST /auth/change-password` for the logged-in user. It needs the current password (guessing it from a stolen session is limited by the same guard), then enforces the rules below, and refuses the same password again. |
| **Password rules** | At least 8 characters, letters and a number, at most 72 bytes, not on a short list of the most common passwords, not containing the username. The web app checks the same rules before sending. |
| **Sessions outlive a password change** | The session carries a short fingerprint of the password hash. After a change, every other session of that user stops working; the session that changed it gets a fresh one. An owner resetting someone's password in master data ends that person's sessions too. |
| **Headers** | Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: same-origin`; login and `/me` answers are `Cache-Control: no-store`. Plain ASGI, so the live event stream is untouched. |

## Web app

- The login password box has a **show/hide** button and a quiet **Caps Lock** warning; a lock-out shows the server's message with the minutes left.
- A **key icon** in the header opens **Change your password** (current, new, new again, with the same rules).

## Known limits (said plainly)

- The guess counters are per server process and in memory. For several server processes they would need to live in the database (a table, so a migration).
- Behind a reverse proxy every request can look like it comes from one address, so the per-address limit is kept high; the per-username lock does the real work.
- A stolen session cookie works until it expires (12 hours) or the password changes. There is no server-side "log out everywhere" button yet.
- Old sessions made before this change carry no fingerprint and keep working until they expire.
- The live event stream checks the session signature but not the password fingerprint; it carries change notices only, never data.

## Tests

`tests/test_auth_security.py` (44) and the web tests for the password box, the dialog, the rules and the login form. Whole suite: 961 backend and 447 web tests pass. Checked once against the running server with a throwaway user (since removed): headers present, a weak password refused, a change accepted, the old password rejected, a lock after five wrong attempts.
