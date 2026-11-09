---
name: error-leakage
description: Use for the QA check errors_do_not_leak_internals, or any finding where an error page shows stack traces, SQL errors, file paths or framework details.
---
Source: OWASP Error Handling Cheat Sheet. Explain in words only, no code.

What it is: when something goes wrong, the response shows internal details such as a stack trace, a database error, file paths or the framework's debug page.
Why it matters: attacks usually begin with gathering information. Technology names and versions, query text and code locations tell an attacker what to try next, and show which inputs reach the database.
Direction of the fix: catch errors in one central place and return a short generic message with a reference number; send the full details to the server logs only. Make sure debug mode is off. Then repeat the same bad input and check that nothing internal appears.
Say which kind of internal text the check found, using the finding's detail text.
