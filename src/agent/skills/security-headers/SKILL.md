---
name: security-headers
description: Use for the QA check security_headers_are_set, or any finding about missing HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Content-Security-Policy).
---
Source: OWASP HTTP Security Response Headers Cheat Sheet. Explain in words only, no code.

What it is: the server did not send one or more headers that tell the browser to apply protections.
Why each matters: X-Frame-Options (or the frame-ancestors rule of a Content Security Policy) stops other sites from showing the page inside a frame, which is how clickjacking works. X-Content-Type-Options stops the browser from guessing a file's type, which can turn harmless files into executable ones. Referrer-Policy limits how much of the page address is sent to other sites. A Content Security Policy limits where scripts may load from, which reduces cross-site scripting.
Direction of the fix: set these headers for all responses, in one central place in the application or in the web server, so no page is missed. Use the values the cheat sheet recommends, then check again in the browser.
Name exactly which headers the check found missing, using the finding's detail text.
