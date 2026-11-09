---
name: debug-enabled
description: Use when a finding says the app runs in debug mode (rules with debug-enabled, flask debug=True; CWE-489 or CWE-94 style) .
---
Source: OWASP Error Handling Cheat Sheet, and the framework's own warning about debug mode. Explain in words only, no code.

What it is: the application is started with debug mode on. On an error it shows a detailed page, and with some frameworks it also offers an interactive console in the browser.
Why it matters: error details tell an attacker the technology, versions, file paths and sometimes code. That helps them plan the next step. An interactive debugger that is reachable from outside can allow running commands on the server.
Direction of the fix: debug mode must be off outside a developer's own machine. Control it from configuration or an environment setting that differs between development and production, never from a value written in the code. Users should see a short generic error, and the details should go to the server logs.
