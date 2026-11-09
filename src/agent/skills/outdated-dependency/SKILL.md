---
name: outdated-dependency
description: Use when a finding is a known vulnerability (CVE) in a library the project depends on, reported by the dependency scanner.
---
Source: OWASP Vulnerable Dependency Management Cheat Sheet. Explain in words only, no code.

What it is: the project uses a version of a third-party library that has a publicly known security problem (a CVE).
Why it matters: the project's security also depends on that library. Known problems are easy for attackers to look up and reuse. How serious it is depends on whether the project actually uses the affected part.
Direction of the fix: if the finding names a fixed version, say that exact version and recommend upgrading to it, then re-running the checks and the tests. If no fixed version exists, say so, and suggest looking for another version, another library, or a way to avoid the affected feature until a fix appears. Mention the CVE number and the CWE when they are given. Do not say the project is certainly exploitable; say it uses a version with a known problem.
