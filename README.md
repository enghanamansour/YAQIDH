# الجاهزية الأمنية | Security Readiness

[العربية](#العربية) | [English](#english)

---

## العربية

### الفكرة

الجاهزية الأمنية هي مسار يمر فيه كل تغيير في الكود على فحوصات منظمة قبل ما يوصل للنسخة النهائية.

الوكيل (AI) يشتغل كمختبِر: يشغّل فحوصات الفريق، ويعلّق على النتائج ويشرحها، ولا يعدّل الكود. المطوّر هو اللي يصلح، والإنسان هو اللي يوافق على الإطلاق.

القاعدة الثابتة:

- الوكيل يفهم ويشرح.
- النظام يفحص ويقرر بقواعد ثابتة، فنفس المدخلات تعطي نفس القرار.
- الإنسان يوافق على الإطلاق.

### مسار الكود

البرنشات في الريبو:

- `main`: النسخة النهائية المعتمدة.
- `staging`: مرحلة وسط، تنفحص فيها النسخة المجمّعة قبل الإطلاق.
- برنش لكل عضو في الفريق باسمه: كل شخص يرفع شغله على برنشه فقط.

الخطوات:

1. العضو يشتغل على برنشه ويفتح Pull Request إلى `staging`.
2. **المرحلة الأولى (الجودة):** الوكيل يشغّل أدوات فريق الجودة ويعلّق على الـ PR بالمشاكل. لا يصلح شي، والدمج ممنوع لين تنتهي المشاكل، ثم تُعاد الفحوصات.
3. فريق الجودة البشري يوافق أو يرفض.
4. عند الموافقة يُدمج التغيير في `staging`.
5. **المرحلة الثانية (الأمن):** الوكيل يشغّل أدوات الأمن ويعلّق بالثغرات. لا يصلح شي، والدمج إلى `main` ممنوع لين تنتهي الثغرات، ثم تُعاد الفحوصات.
6. فريق الأمن البشري يوافق أو يرفض.
7. عند الموافقة يُدمج التغيير في `main`.
8. عند الرفض يرجع التغيير للمطوّر بسبب محدد، ويصلح بنفسه.

### سجل الأدلة

كل مرحلة تسجّل في سجل أدلة ما انفحص، وما وُجد، وما انصلح، ومن وافق ومتى وعلى أي commit. السجل يتزامن مع لوحة المتابعة. وكل ثغرة تأخذ بصمة، عشان نتأكد لاحقاً إنها انقفلت فعلاً.

### الاستثناءات

إذا تعذّر إصلاح ثغرة، يقدر المطوّر يطلب استثناء بمبرر وتاريخ انتهاء، ويراجعه الإنسان.

### حالة المشروع

المشروع في مرحلة التخطيط. أدوات الفحص لسا ما تحدّدت.

---

## English

### The idea

Security Readiness is a path that every code change goes through, with structured checks, before it reaches the final version.

An AI agent works as a tester: it runs the team's checks, comments on the results and explains them, and never edits the code. The developer does the fixing, and a human approves the release.

The fixed rule:

- The agent understands and explains.
- The system checks and decides with fixed rules, so the same input always gives the same decision.
- A human approves the release.

### Code path

Branches in this repository:

- `main`: the final, approved version.
- `staging`: an in-between stage where the combined work is checked before release.
- One branch per team member, named after them: everyone pushes their work to their own branch only.

Steps:

1. A member works on their branch and opens a Pull Request into `staging`.
2. **Phase 1 (quality):** the agent runs the QA team's tools and comments on the PR with any issues. It fixes nothing, merging stays blocked until the issues are gone, and then the checks run again.
3. The human QA team approves or rejects.
4. On approval the change is merged into `staging`.
5. **Phase 2 (security):** the agent runs the security tools and comments with any vulnerabilities. It fixes nothing, merging into `main` stays blocked until they are gone, and then the checks run again.
6. The human security team approves or rejects.
7. On approval the change is merged into `main`.
8. On rejection the change goes back to the developer with a specific reason, and they fix it themselves.

### Evidence log

Each phase records in an evidence log what was checked, what was found, what was fixed, and who approved it, when, and on which commit. The log syncs with the tracking dashboard. Every vulnerability gets a fingerprint, so we can confirm later that it was really closed.

### Exceptions

If a vulnerability cannot be fixed, the developer can request an exception with a justification and an expiry date, which a human reviews.

### Project status

The project is in the planning stage. The checking tools have not been chosen yet.
