---
name: access-control-login
description: Use for QA checks about who may see what, and about logging in: cart_requires_login (a page that should need a login) and wrong_password_is_rejected (a wrong password must not log in).
---
Sources: OWASP Authorization Cheat Sheet and Authentication Cheat Sheet. Explain in words only, no code.

cart_requires_login: the check opens a page that belongs to a signed-in user without being signed in. If it fails, the page opened for an anonymous visitor. Why it matters: broken access control is among the most serious web problems; anyone could see or change data meant for one user. Direction: the server must check permission on every request and deny by default, not only hide the link in the interface.
wrong_password_is_rejected: the check tries to sign in with a wrong password. If it fails, the app accepted it. Why it matters: it means accounts can be entered without knowing the password. Direction: verify the password on the server against a safely stored hash, and show the same generic message whether the user or the password was wrong. Limiting repeated attempts also helps.
Say what the check did and what it saw, using the finding's detail text.
