"""The stricter dialect checks and the few-shot examples."""
import json

import httpx

from app.explainer import DIALECT_EXAMPLES, DialectRewriter, meaning_problem, preserves_meaning
from app.models import Explanation

ORIGINAL = Explanation(
    problem="تم تفعيل وضع التصحيح (debug) في الملف app.py عند السطر 17.",
    why_dangerous="يكشف معلومات حساسة لأي شخص يزور التطبيق، ولا يجوز تركه في الإنتاج.",
    direction="لا تشغّل التطبيق بهذا الوضع في الإنتاج، وعطّله قبل النشر.",
)

GOOD = {
    "problem": "وضع التصحيح (debug) مفعّل في الملف app.py عند السطر 17.",
    "why_dangerous": "يكشف معلومات حساسة لأي أحد يزور التطبيق، ولا يصير تتركه في الإنتاج.",
    "direction": "لا تشغّل التطبيق بهذا الوضع في الإنتاج، وعطّله قبل النشر.",
}


def _variant(**changes) -> Explanation:
    return Explanation(**{**GOOD, **changes})


def test_a_faithful_rewrite_passes():
    assert preserves_meaning(ORIGINAL, Explanation(**GOOD))


def test_the_few_shot_examples_pass_our_own_checks():
    # if an example breaks the rules we teach, the model learns to break them
    for formal, dialect in DIALECT_EXAMPLES:
        assert preserves_meaning(Explanation(**formal), Explanation(**dialect))


def test_line_turned_into_page_is_rejected():
    # a real failure from the first comparison run: "السطر 12" became "بالصفحة 12"
    bad = _variant(problem="وضع التصحيح (debug) مفعّل في الملف app.py بالصفحة 17.")
    assert not preserves_meaning(ORIGINAL, bad)


def test_file_word_dropped_is_rejected():
    bad = _variant(problem="وضع التصحيح (debug) مفعّل في app.py عند السطر 17.")
    assert not preserves_meaning(ORIGINAL, bad)


def test_a_lost_english_term_is_rejected():
    bad = _variant(problem="وضع التصحيح مفعّل في الملف app.py عند السطر 17.")  # "debug" gone
    assert not preserves_meaning(ORIGINAL, bad)


def test_a_changed_file_name_is_rejected():
    bad = _variant(problem="وضع التصحيح (debug) مفعّل في الملف main.py عند السطر 17.")
    assert not preserves_meaning(ORIGINAL, bad)


def test_a_dropped_prohibition_is_rejected():
    bad = _variant(direction="شغّل التطبيق بهذا الوضع في الإنتاج، وعطّله قبل النشر.")  # "لا" gone
    assert not preserves_meaning(ORIGINAL, bad)


def test_a_negation_with_a_prefix_still_counts():
    # "ولا" in the original, "وما" in the rewrite: the negation is kept, so it passes
    ok = _variant(why_dangerous="يكشف معلومات حساسة لأي أحد يزور التطبيق، وما يصير تتركه في الإنتاج.")
    assert preserves_meaning(ORIGINAL, ok)
    lost = _variant(why_dangerous="يكشف معلومات حساسة لأي أحد يزور التطبيق، ويصير تتركه في الإنتاج.")
    assert not preserves_meaning(ORIGINAL, lost)


def test_cookies_are_not_mistaken_for_the_word_file():
    # a real false rejection on the Trivy sample: "ملفات تعريف الارتباط" means cookies, and the
    # rewrite used another word for them. Only the word "ملف" by itself is a location word.
    original = Explanation(
        problem="قد يرسل الخادم ملفات تعريف الارتباط الخاصة بمستخدم إلى مستخدمين آخرين.",
        why_dangerous="يحدث ذلك عندما لا يضبط التطبيق رؤوس التخزين المؤقت.",
        direction="رقّ المكتبة إلى نسخة أحدث.",
    )
    rewritten = Explanation(
        problem="ممكن الخادم يرسل الكوكيز حق مستخدم لمستخدمين ثانيين.",
        why_dangerous="هذا يصير لما التطبيق ما يضبط رؤوس التخزين المؤقت.",
        direction="رقّ المكتبة لنسخة أحدث.",
    )
    assert meaning_problem(original, rewritten) is None


def test_the_word_file_is_matched_with_prefixes_but_not_inside_longer_words():
    from app.explainer import _has_word

    for text in ("في الملف app.py", "بملف app.py", "للملف app.py", "ملف app.py", "بالسطر 12", "عند السطر 12", "سطر 12"):
        assert _has_word(text, "ملف") or _has_word(text, "سطر"), text
    assert not _has_word("ملفات تعريف الارتباط", "ملف")
    assert not _has_word("الملفات الحساسة", "ملف")
    assert not _has_word("سطرين", "سطر")


def test_egyptian_or_levantine_words_are_not_accepted_as_saudi():
    for bad_word in ("وده", "كده", "هادي", "مش"):
        bad = _variant(why_dangerous=f"يكشف معلومات حساسة لأي أحد يزور التطبيق، {bad_word} ولا يصير تتركه في الإنتاج.")
        assert "not Saudi" in meaning_problem(ORIGINAL, bad), bad_word
    # ordinary Saudi / Gulf words must pass
    assert meaning_problem(ORIGINAL, Explanation(**GOOD)) is None


def test_an_instruction_turned_into_i_need_is_rejected():
    # seen in every run: "يجب إزالة السر" became "احتاج تشيل السر" (I need to remove it)
    bad = _variant(direction="احتاج تشغّل التطبيق بهذا الوضع في الإنتاج، ولا تنسى تعطّله قبل النشر.")
    assert "I need" in meaning_problem(ORIGINAL, bad)


def test_an_invented_cwe_or_term_is_rejected():
    # a real failure from the third run: the model wrote "SQL Injection (CWE-476)" and the
    # original had no CWE at all
    original = Explanation(
        problem="يُبنى استعلام SQL من مدخلات المستخدم في الملف app.py عند السطر 12.",
        why_dangerous="يستطيع المهاجم قراءة البيانات أو تعديلها.",
        direction="استخدم استعلامات مهيأة بدل دمج النص.",
    )
    invented = Explanation(
        problem="يتبني استعلام SQL من مدخلات المستخدم في الملف app.py عند السطر 12، وهذا يسمونه SQL Injection (CWE-476).",
        why_dangerous="المهاجم يقدر يقرأ البيانات أو يعدلها.",
        direction="استخدم استعلامات مهيأة بدل دمج النص.",
    )
    assert "CWE-476" in meaning_problem(original, invented)


def test_a_non_breaking_hyphen_in_cwe_is_not_a_difference():
    # a real case: the strong model wrote "CWE‑22" and the rewrite wrote "CWE-22"
    original = Explanation(
        problem="مدخل المستخدم قد يصل إلى مسار ملف في السطر 31 من الملف files.py (CWE‑22).",
        why_dangerous="قد يقرأ المهاجم ملفات حساسة على الخادم.",
        direction="تحقق من المسار قبل استخدامه.",
    )
    rewritten = Explanation(
        problem="مدخل المستخدم ممكن يوصل لمسار ملف في السطر 31 من الملف files.py (CWE-22).",
        why_dangerous="المهاجم ممكن يقرأ ملفات حساسة على السيرفر.",
        direction="تحقق من المسار قبل ما تستخدمه.",
    )
    assert meaning_problem(original, rewritten) is None


def test_a_sentence_copied_into_two_fields_is_rejected():
    twice = "رغم إن الأداة تعطي ثقة منخفضة، إلا إن هذا النوع يستاهل الانتباه."
    original = Explanation(
        problem="مدخل المستخدم قد يصل إلى مسار ملف في السطر 31 من الملف files.py.",
        why_dangerous="قد يقرأ المهاجم ملفات حساسة. على الرغم من أن الأداة تعطي ثقة منخفضة فإن هذا النوع يستحق الانتباه.",
        direction="تحقق من المسار قبل استخدامه.",
    )
    rewritten = Explanation(
        problem="مدخل المستخدم ممكن يوصل لمسار ملف في السطر 31 من الملف files.py. " + twice,
        why_dangerous="ممكن يقرأ المهاجم ملفات حساسة. " + twice,
        direction="تحقق من المسار قبل ما تستخدمه.",
    )
    assert meaning_problem(original, rewritten) == "a sentence is repeated"


def test_a_number_written_as_a_word_may_become_a_digit():
    # "السطر الخامس" -> "السطر رقم 5" is fine (it is the same number), only new Latin terms are blocked
    original = Explanation(
        problem="تم العثور على كلمة مرور في الملف config.py في السطر الخامس.",
        why_dangerous="يستطيع أي شخص يحصل على الكود رؤيتها.",
        direction="انقلها إلى متغيرات البيئة.",
    )
    rewritten = Explanation(
        problem="لقينا كلمة مرور في الملف config.py في السطر رقم 5.",
        why_dangerous="أي أحد يحصل على الكود يقدر يشوفها.",
        direction="انقلها لمتغيرات البيئة.",
    )
    assert "5" not in (meaning_problem(original, rewritten) or "")


def test_the_word_ma_in_formal_text_is_not_a_negation():
    # a real false rejection from the second run: "ما إذا" means "whether", it is not a "no"
    original = Explanation(
        problem="تم تفعيل وضع التصحيح (debug) في الملف app.py عند السطر 17.",
        why_dangerous="يكشف معلومات تفصيلية عن الأخطاء لأي شخص يزور التطبيق.",
        direction="اعتمد على متغير بيئي لتحديد ما إذا كان التطبيق يعمل في وضع التطوير أو الإنتاج.",
    )
    rewritten = Explanation(
        problem="وضع التصحيح (debug) مفعّل في الملف app.py عند السطر 17.",
        why_dangerous="يكشف معلومات تفصيلية عن الأخطاء لأي أحد يزور التطبيق.",
        direction="اعتمد على متغير بيئي عشان تحدد إذا التطبيق يشتغل في وضع التطوير أو الإنتاج.",
    )
    assert meaning_problem(original, rewritten) is None


def test_the_reason_for_a_rejection_is_reported():
    assert meaning_problem(ORIGINAL, Explanation(**GOOD)) is None
    page = _variant(problem="وضع التصحيح (debug) مفعّل في الملف app.py بالصفحة 17.")
    assert "سطر" in meaning_problem(ORIGINAL, page)
    lost = _variant(problem="وضع التصحيح مفعّل في الملف app.py عند السطر 17.")
    assert "debug" in meaning_problem(ORIGINAL, lost)
    code = _variant(direction="لا تشغّل التطبيق بهذا الوضع، واكتب `debug=False` قبل النشر.")
    assert "code" in meaning_problem(ORIGINAL, code)
    negation = _variant(direction="شغّل التطبيق بهذا الوضع في الإنتاج، وعطّله قبل النشر.")
    assert "negation" in meaning_problem(ORIGINAL, negation)


def test_the_request_carries_the_examples_before_the_real_input():
    seen = {}

    def handler(request):
        seen["messages"] = json.loads(request.content)["messages"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(GOOD, ensure_ascii=False)}}]})

    rewriter = DialectRewriter("http://x", "k", "allam", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert rewriter.rewrite(ORIGINAL) is not None
    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system"] + ["user", "assistant"] * len(DIALECT_EXAMPLES) + ["user"]
    assert json.loads(seen["messages"][-1]["content"])["problem"] == ORIGINAL.problem
