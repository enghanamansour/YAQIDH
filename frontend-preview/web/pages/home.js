/* The landing page: what Yaqidh is, the problem it removes, how a request moves, and who decides what. */

function landing(){
  const go=profile?(profile.role==='company-admin'?'/admin':'/dashboard'):'/login';
  const goLabel=profile?copy('فتح لوحة المتابعة','Open the dashboard'):copy('تسجيل الدخول','Sign in');
  const journey=[
    [copy('فتح الطلب','Pull request opened'),copy('المطوّر يرفع تعديله.','The developer pushes a change.')],
    [copy('فحص الجودة','Quality check'),copy('يقظ يجرب الموقع ويشرح أي مشكلة.','Yaqidh tries the site and explains any problem.')],
    [copy('موافقة الجودة','QA approval'),copy('مراجع الجودة يقرر، وتنفتح البوابة للتجهيز.','The QA reviewer decides; the staging gate opens.')],
    [copy('الفحص الأمني','Security check'),copy('فحص الكود والمكتبات، ويعاد بعد كل تعديل.','Code and libraries are scanned, again after every change.')],
    [copy('موافقة الأمن','Security approval'),copy('مراجع الأمن يعتمد أو يرجّع مع السبب.','The security reviewer approves or returns with a reason.')],
    [copy('جاهز للدمج','Ready to merge'),copy('البوابة تنفتح على هذا الـ commit بالذات.','The gate opens for this exact commit.')]
  ];
  const who=[
    ['01',copy('الأدوات تفحص','Tools check'),copy('<bdi>Semgrep</bdi> و<bdi>Trivy</bdi> و<bdi>Playwright</bdi> تفحص الكود والمكتبات والموقع نفسه.','Semgrep, Trivy and Playwright check the code, the libraries and the site itself.')],
    ['02',copy('الكود يقرر','Code decides'),copy('محرك السياسة والمدقّق: نفس المدخلات تعطي دائمًا نفس القرار.','The policy engine and the verifier: the same input always gives the same decision.')],
    ['03',copy('الذكاء الاصطناعي يشرح','AI explains'),copy('يشرح كل مشكلة بلغة بسيطة. ما يصلح ولا يوافق ولا يدمج.','It explains each problem in plain language. It never fixes, approves or merges.')],
    ['04',copy('الناس توافق','People approve'),copy('موافقة الجودة وموافقة الأمن، كل واحدة باسم صاحبها وسببها.','A QA approval and a security approval, each with a name and a reason.')]
  ];
  const roles=[
    [copy('المطوّر','Developer'),copy('وش يمنع طلبه، وشرح لكل مشكلة، وسبب الإرجاع، ونتيجة إعادة الفحص.','What blocks the request, an explanation for each problem, why it was returned, and the re-check result.')],
    [copy('مراجع الجودة','QA reviewer'),copy('الفحوصات الخمسة بنتيجة كل واحد، وقرار الموافقة أو الإرجاع.','The five checks with their results, and the decision to approve or return.')],
    [copy('مراجع الأمن','Security reviewer'),copy('الثغرات مرتبة بالخطورة مع النسخة المصلحة، ومنح الاستثناءات، والاعتماد.','Vulnerabilities by severity with the fixed version, exceptions, and the final approval.')],
    [copy('مسؤول الشركة','Company admin'),copy('الحسابات والأدوار، وصحة الربط مع GitHub.','Accounts and roles, and the health of the GitHub connection.')]
  ];
  const trust=[
    [copy('سجل لا يُعدَّل بصمت','A record nobody can edit silently'),copy('كل حدث مربوط بسلسلة بصمات، وأي تغيير ينكشف.','Every event is chained by hashes, so any change shows.')],
    [copy('بوابة مقفولة على الـ commit','A gate locked to the commit'),copy('أي push بعد الموافقة يقفل البوابة لين يُفحص الجديد.','A push after an approval closes the gate until the new code is checked.')],
    [copy('استثناء بتبرير وموافقة','Exceptions need a reason and a person'),copy('وللمتوسط فقط. الحرج والعالي ما ينقبل لهم استثناء.','And only for medium findings. High and critical ones can never be excepted.')]
  ];
  const ring=(r,cls)=>'<svg class="lp-ring '+cls+'" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="'+r+'"/></svg>';
  return '<main class="landing2">'
    +'<section class="lp-hero"><div class="lp-bg" aria-hidden="true"><div class="lp-grid"></div></div>'
    +'<div class="lp-hero-inner"><div class="lp-copy"><span class="lp-tag">'+copy('الجاهزية الأمنية للإصدارات','Security readiness for releases')+'</span>'
    +'<h1>'+copy('أمان <span class="grad">استباقي</span>، إطلاق أسرع.','<span class="grad">Proactive</span> security, faster releases.')+'</h1>'
    +'<p class="lp-sub">'+copy('يقظ يرافق منتجك قبل الإطلاق: يفحص، يشرح، ويعيد الفحص تلقائيًا، والقرار دايمًا بيد الفريق.','Yaqidh accompanies your product before release: it checks, explains and re-checks automatically, and the decision always stays with your team.')+'</p>'
    +'<div class="actions lp-cta"><a class="action primary" href="'+go+'">'+goLabel+'</a><a class="action" href="#about">'+copy('كيف يعمل','How it works')+'</a></div></div>'
    +'<div class="lp-art" aria-hidden="true">'+ring(190,'a')+ring(150,'b')+'<img class="lp-mark" alt="" src="'+logo()+'"></div></div></section>'

    +'<section class="lp-section" id="problem"><h2>'+copy('الدورة اللي تأخّر الإطلاق','The loop that delays every release')+'</h2>'
    +'<div class="lp-two"><article class="lp-card"><small>'+copy('بدون يقظ','Without Yaqidh')+'</small><h3>'+copy('لفّة بعد لفّة','Round after round')+'</h3>'
    +'<ol class="lp-flow"><li>'+copy('الأمن يرجّع الثغرات للمطوّرين','Security sends findings back to developers')+'</li><li>'+copy('المطوّرين يصلحونها','Developers fix them')+'</li><li>'+copy('الأمن يعيد الفحص','Security re-scans')+'</li><li>'+copy('وتتكرر لين تنقفل كلها','Repeat until all are closed')+'</li></ol>'
    +'<p class="muted">'+copy('كل لفّة تستهلك وقت وجهد بشري وتأخّر الإطلاق.','Every round costs human time and effort, and delays the release.')+'</p></article>'
    +'<article class="lp-card on"><small>'+copy('مع يقظ','With Yaqidh')+'</small><h3>'+copy('الدورة تمشي لحالها','The loop runs by itself')+'</h3>'
    +'<ol class="lp-flow"><li>'+copy('يفحص تلقائيًا عند كل طلب دمج','Checks automatically on every pull request')+'</li><li>'+copy('يشرح كل مشكلة فورًا للمطوّر','Explains each problem to the developer at once')+'</li><li>'+copy('يعيد الفحص بعد كل تعديل ويتأكد إنها انقفلت','Re-checks after every change and confirms it is closed')+'</li><li>'+copy('الناس تتدخل للموافقة بس','People step in only to approve')+'</li></ol></article></div></section>'

    +'<section class="lp-section" id="about"><h2>'+copy('كيف يمشي الطلب','How a request moves')+'</h2><ol class="lp-journey">'
    +journey.map(([title,text],i)=>'<li><i>'+(i+1)+'</i><b>'+title+'</b><small>'+text+'</small></li>').join('')+'</ol>'
    +'<p class="lp-loop">↻ '+copy('عند الإخفاق: يرجع للمطوّر، وإعادة الفحص تلقائية، والمدقّق يتأكد إن المشكلة انقفلت.','On failure: back to the developer, an automatic re-check, and the verifier confirms the problem is closed.')+'</p></section>'

    +'<section class="lp-section"><h2>'+copy('من يفعل ماذا','Who does what')+'</h2><div class="lp-four">'
    +who.map(([n,title,text])=>'<article class="lp-card"><span class="lp-n">'+n+'</span><h3>'+title+'</h3><p class="muted">'+text+'</p></article>').join('')+'</div></section>'

    +'<section class="lp-section"><h2>'+copy('لكل دور شاشته','A screen for every role')+'</h2><div class="lp-four">'
    +roles.map(([title,text])=>'<article class="lp-card"><h3>'+title+'</h3><p class="muted">'+text+'</p></article>').join('')+'</div></section>'

    +'<section class="lp-section"><h2>'+copy('ليش تثق فيه','Why you can trust it')+'</h2><div class="lp-three">'
    +trust.map(([title,text])=>'<article class="lp-card"><h3>'+title+'</h3><p class="muted">'+text+'</p></article>').join('')+'</div></section>'

    +'<section class="lp-final"><h2>'+copy('جاهز تجرّب؟','Ready to try it?')+'</h2><div class="actions"><a class="action primary" href="'+go+'">'+goLabel+'</a></div></section>'
    +'<footer class="lp-foot">'+copy('يقظ · الجاهزية الأمنية للإصدارات','Yaqidh · security readiness for releases')+'</footer></main>';
}
