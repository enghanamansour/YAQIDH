---
name: hardcoded-secret
description: Use when a finding is a key, token or password written inside the code or a config file (rules with secret, token, api-key, github-pat; CWE-798).
---
Source: OWASP Secrets Management Cheat Sheet. Explain in words only, no code. Never repeat the secret value itself, even if it appears in the finding.

What it is: a credential (an API key, a token, a database password) is saved as plain text in the repository.
Why it matters: everyone who can read the repository, and its history, can use that credential. Removing it later does not help by itself, because copies remain in earlier versions and may already have been seen.
Direction of the fix: treat the secret as exposed and have it replaced (rotated) at the service that issued it. Then keep secrets out of the code: load them from the environment or a secrets manager, and give each application only the access it needs. Check that the repository history and any logs do not still contain it.
