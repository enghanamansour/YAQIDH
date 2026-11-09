---
name: sql-injection
description: Use when a finding is about SQL built from user input (rules with sql, tainted-sql, injection; CWE-89), or a QA check that sends SQL-like text to a search or form.
---
Source: OWASP SQL Injection Prevention Cheat Sheet. Explain in words only, no code.

What it is: untrusted data (a search box, a form field, a URL parameter) becomes part of the SQL text, so it can change what the query does.
Why it matters: an attacker may read data they should not see, change or delete data, or in the worst case run administration actions on the database. The harm depends on the database permissions.
Direction of the fix: keep the SQL structure separate from the values and pass the values through the database's parameter mechanism (parameterized queries) instead of joining strings. Names of tables, columns or sort order cannot be parameters, so they must come from a fixed list owned by the application. Do not rely on trying to clean the input alone.
When explaining a QA check: say what text was sent, what the page did with it (more results than expected, an error), and why that shows the input reached the query.
