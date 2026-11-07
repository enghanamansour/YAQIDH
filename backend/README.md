# Backend الوكيل | Agent backend

## العربية

الشريحة الأولى من الوكيل: يستلم نتيجة فحص، يشرح كل ثغرة مفتوحة بالكلمات فقط، ويبني تعليق الـ PR، ويقرر هل يمر الدمج بقاعدة ثابتة.

### القواعد اللي يفرضها الكود

- الدمج يمر فقط إذا يوجد فحص لنفس الـ commit اللي بيندمج، وما فيه أي ثغرة **عالية الخطورة (high)** مفتوحة. الثغرات المنخفضة (low) لا تمنع الدمج لكنها تظهر في التعليق وتُسجّل، وهي ليست بلا ضرر.
- فيه مستويين فقط: **low** هي الوحيدة اللي تمر، وأي اسم ثاني (critical أو medium أو info أو أي اسم غريب) يُعامل كـ **high**، عشان أي تصنيف ما توقعناه ما يمرّر ثغرة بالغلط.
- أي commit جديد ما انفحص يبقى ممنوع.
- إذا ما فيه فحص أصلاً، أو أعيد تشغيل الخادم، يبقى ممنوع (القاعدة تفشل بإغلاق).
- القرار ما يدخل فيه النموذج اللغوي أبداً.
- الوكيل يشرح ولا يكتب كود. وإذا حاول النموذج يكتب كود، تُرفض إجابته وتُعاد مرة، ثم يُستخدم قالب ثابت.
- كل ثغرة لها بصمة لا تتأثر برقم السطر، فتختفي فقط إذا انحلّت فعلاً.
- سجل الأدلة مرتبط بسلسلة هاش، وأي تعديل أو حذف في وسطه يكشفه `GET /evidence/verify`.
- كل الطلبات تحتاج رمز (`API_TOKEN`)، وبدونه الخادم يرفض.
- كود الثغرة (snippet) لا يُرسل للنموذج الخارجي إلا إذا فعّلتوا `SEND_SNIPPETS=1`.

### التشغيل

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set API_TOKEN=dev-token
uvicorn app.main:app --reload
pytest
```

بدون `LLM_API_KEY` يشتغل بقالب ثابت. ولتفعيل نموذج خارجي (استخدموا بيانات تجريبية فقط):

```
set LLM_API_KEY=...
set LLM_BASE_URL=https://openrouter.ai/api/v1
set LLM_MODEL=meta-llama/llama-3.3-70b-instruct
```

### الواجهة

| الطلب | الوظيفة |
|---|---|
| `POST /scans` | تسجيل نتيجة فحص، شرح المفتوح، وبناء تعليق الـ PR |
| `GET /gate` | هل يمر هذا الـ commit؟ |
| `GET /evidence` | سجل الأدلة لـ PR |
| `GET /evidence/verify` | سلامة سلسلة السجل |

### غير موجود بعد

- ربط GitHub (نشر التعليق فعلياً وحالة الفحص على الـ PR).
- البحث في بيانات الثغرات (RAG) وأمثلة few-shot.
- تخزين دائم للحالة (الآن في الذاكرة، والسجل فقط على ملف).
- طلب الاستثناءات.

---

## English

The first slice of the agent: it takes a scan result, explains every open finding in words only, builds the pull request comment, and decides whether merging may pass using a fixed rule.

### Rules the code enforces

- A merge passes only if a scan exists for the exact commit being merged and it has no open **high-severity** finding. Low-severity findings do not block, but they are shown in the comment and recorded; they are not harmless.
- There are only two levels: only an explicit **low** passes. Any other name (critical, medium, info, or anything unknown) counts as **high**, so a label we did not expect can never let a finding slip through.
- A new, unscanned commit stays blocked.
- With no scan at all, or after a server restart, it stays blocked (the rule fails closed).
- The language model never takes part in the decision.
- The agent explains and never writes code. If the model writes code, its answer is rejected and retried once, then a fixed template is used.
- Every finding has a fingerprint that ignores the line number, so it disappears only when it is really fixed.
- The evidence log is hash-chained; editing or deleting anything in the middle is detected by `GET /evidence/verify`.
- Every request needs a token (`API_TOKEN`); without one the server refuses.
- The finding's code snippet is not sent to the external model unless `SEND_SNIPPETS=1` is set.

### Run

See the commands above. Without `LLM_API_KEY` it uses a fixed template. To enable an external model (use test data only), set `LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL`.

### Not built yet

- GitHub integration (actually posting the comment and the status check on the PR).
- Search over the vulnerability data (RAG) and few-shot examples.
- Persistent state (now in memory; only the log is on disk).
- Exception requests.
