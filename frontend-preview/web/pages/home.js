/* The landing page: what Yaqidh is, the problem it removes, how a request moves, and who decides what. */

function landing(){
  const variant=['bg','edge','emblem','side','clean'].includes(new URLSearchParams(location.search).get('hero'))?new URLSearchParams(location.search).get('hero'):'side';
  const go=profile?(profile.role==='company-admin'?'/admin':'/dashboard'):'/login';
  const goLabel=profile?copy('فتح لوحة المتابعة','Open the dashboard'):copy('تسجيل الدخول','Sign in');
  const journey=[
    [copy('فتح الطلب','Pull request opened'),copy('المطوّر يرفع تعديله.','The developer pushes a change.')],
    [copy('فحص الجودة','Quality check'),copy('يفحص الجودة الأمنية للتطبيق عبر اختبارات تحاكي سيناريوهات الهجوم.','Checks the security quality of the application with tests that simulate attack scenarios.')],
    [copy('موافقة الجودة','QA approval'),copy('يراجع المختص نتائج الاختبارات ويقيّمها، ثم يقرر اعتماد التعديل أو إعادته للمطوّر مع توضيح الملاحظات.','A specialist reviews and assesses the test results, then approves the change or returns it to the developer with the findings explained.')],
    [copy('الفحص الأمني','Security check'),copy('يحلل الكود والمكتبات البرمجية لاكتشاف الثغرات الأمنية، ويشرح مخاطرها، ثم يعيد الفحص للتحقق من نجاح الإصلاحات.','Analyzes the code and libraries to find vulnerabilities, explains their risks, then re-checks to verify the fixes worked.')],
    [copy('موافقة الأمن','Security approval'),copy('يراجع المختص نتائج الفحص والثغرات المتبقية، ويقرر اعتماد التعديل أو إعادته لمعالجة المخاطر.','A specialist reviews the results and the remaining vulnerabilities, then approves the change or returns it to address the risks.')],
    [copy('جاهز للدمج','Ready to merge'),copy('يُسمح بدمج التعديل بعد استيفاء متطلبات الفحص والاعتماد من قبل المختص. وأي تعديل جديد يستلزم إعادة الفحص قبل السماح بالدمج.','The change may be merged once the checks and the specialist approval are complete. Any new change needs a re-check before merging is allowed.')]
  ];
  const ring=(r,cls)=>'<svg class="lp-ring '+cls+'" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="'+r+'"/></svg>';
  return '<main class="landing2">'
    +'<section class="lp-hero v-'+variant+'"><div class="lp-bg" aria-hidden="true"><div class="lp-grid"></div></div>'
    +'<div class="lp-hero-inner"><div class="lp-copy">'
    +'<h1>'+copy('<span class="lp-l">أمــان <span class="grad">استباقــي</span>،</span> <span class="lp-l">إطــلاق أســرع.</span>','<span class="lp-l"><span class="grad">Proactive</span> security,</span> <span class="lp-l">faster releases.</span>')+'</h1>'
    +'<p class="lp-sub">'+copy('يَقِـــظ يرافــق منتجــك قبــل الإطــلاق: يفحــص، يشــرح، ويعيــد الفحــص تلقائيــًا، والقــرار دائمًــا بيــد الفريــق.','Yaqidh accompanies your product before release: it checks, explains and re-checks automatically, and the decision always stays with your team.')+'</p>'
    +'<div class="actions lp-cta"><a class="action primary" href="'+go+'">'+goLabel+'</a><a class="action" href="#about">'+copy('كيف يعمل','How it works')+'</a></div></div>'
    +'<div class="lp-art" aria-hidden="true">'+ring(190,'a')+ring(150,'b')+''+animatedLogo()+'</div></div></section>'

    +'<section class="lp-section" id="problem"><span class="lp-eyebrow">'+copy('المشكلة','The problem')+'</span><h2>'+copy('من لفّات لا تنتهي إلى إطلاق أسرع','From endless rounds to a faster release')+'</h2>'
    +'<div class="lp-two"><article class="lp-col lp-bad"><h3 class="lp-col-title">'+copy('بدون يَقِـــظ','Without Yaqidh')+'</h3><ol class="lp-line"><li><i>1</i>'+copy('المنتج يُرسل للأمن','The product is sent to security')+'</li><li><i>2</i>'+copy('الأمن يفحصه ويلاقي ثغرات','Security checks it and finds vulnerabilities')+'</li><li><i>3</i>'+copy('يرجعونه للمطوّر','They send it back to the developer')+'</li><li><i>4</i>'+copy('المطوّر يصلّح ويرجعه للأمن','The developer fixes it and sends it back')+'</li><li><i>5</i>'+copy('وتتكرر الدورة من جديد ↻','And the cycle repeats ↻')+'</li></ol><p class="muted">'+copy('كل لفّة وقت وجهد، وتأخير للإطلاق.','Every round costs time and effort, and delays the release.')+'</p></article>'
    +'<article class="lp-col lp-good"><h3 class="lp-col-title"><span class="grad">'+copy('مع يَقِـــظ','With Yaqidh')+'</span></h3><ol class="lp-line"><li><i>1</i>'+copy('يفحص تلقائيًا أول بأول','Checks automatically, as you go')+'</li><li><i>2</i>'+copy('يشرح كل مشكلة فورًا','Explains every problem at once')+'</li><li><i>3</i>'+copy('يعيد الفحص بعد كل تعديل','Re-checks after every change')+'</li><li><i>4</i>'+copy('يتأكد إن المشكلة انقفلت','Confirms the problem is closed')+'</li></ol><p class="muted">'+copy('والفريق المختص يتدخل للموافقة فقط.','And the specialist team steps in only to approve.')+'</p></article></div></section>'

    +'<section class="lp-section" id="about"><span class="lp-eyebrow">'+copy('كيف يعمل','How it works')+'</span><h2>'+copy('كيف يمشي الطلب','How a request moves')+'</h2><ol class="lp-journey">'
    +journey.map(([title,text],i)=>'<li><i>'+(i+1)+'</i><b>'+title+'</b><small>'+text+'</small></li>').join('')+'</ol>'
    +'</section>'

    +'<section class="lp-section" id="features"><span class="lp-eyebrow">'+copy('المميزات','Features')+'</span><h2>'+copy('كل اللي يحتاجه فريقك قبل الإطلاق','Everything your team needs before a release')+'</h2><div class="lp-three"><article class="lp-card"><span class="lp-n">01</span><h3>'+copy('فحص تلقائي لكل طلب دمج','Automatic checks on every pull request')+'</h3><p class="muted">'+copy('Playwright وSemgrep وTrivy يفحصون الموقع والكود والمكتبات بدون تدخل.','Playwright, Semgrep and Trivy check the site, the code and the libraries with no manual work.')+'</p></article><article class="lp-card"><span class="lp-n">02</span><h3>'+copy('شرح بلغة بسيطة','Plain-language explanations')+'</h3><p class="muted">'+copy('الذكاء الاصطناعي يشرح كل مشكلة واتجاه إصلاحها، ولا يصلح ولا يوافق.','The AI explains each problem and the direction of the fix; it never fixes or approves.')+'</p></article><article class="lp-card"><span class="lp-n">03</span><h3>'+copy('إعادة فحص وتأكيد الإغلاق','Re-checks that confirm closure')+'</h3><p class="muted">'+copy('بعد كل تعديل يعيد الفحص، والمدقّق يتأكد إن المشكلة انقفلت فعلًا.','After every change it re-checks, and the verifier confirms the problem is really closed.')+'</p></article><article class="lp-card"><span class="lp-n">04</span><h3>'+copy('قرار ثابت وواضح','A fixed, clear decision')+'</h3><p class="muted">'+copy('محرك السياسة يقرر نجح أو فشل، ونفس المدخلات تعطي دائمًا نفس القرار.','The policy engine decides pass or fail, and the same input always gives the same decision.')+'</p></article><article class="lp-card"><span class="lp-n">05</span><h3>'+copy('موافقتان بشريتان','Two human approvals')+'</h3><p class="muted">'+copy('مراجع الجودة ثم مراجع الأمن، وكل قرار باسم صاحبه وسببه.','The QA reviewer then the security reviewer, each decision with a name and a reason.')+'</p></article><article class="lp-card"><span class="lp-n">06</span><h3>'+copy('بوابة دمج وسجل أمين','A merge gate and an honest record')+'</h3><p class="muted">'+copy('البوابة مقفولة على الـ commit وتظهر على GitHub، والسجل لا يُعدَّل بصمت.','The gate is locked to the commit and shows on GitHub, and the record cannot be edited silently.')+'</p></article></div></section>'

    +'<section class="lp-final"><h2>'+copy('جاهز تجرّب؟','Ready to try it?')+'</h2><div class="actions"><a class="action primary" href="'+go+'">'+goLabel+'</a></div></section>'
    +'<footer class="lp-foot">'+copy('يَقِـــظ · الجاهزية الأمنية للإصدارات','Yaqidh · security readiness for releases')+'</footer></main>';
}

/* the subtitle is typed letter by letter, once per visit */
function startTyping(){
  const el=document.querySelector('.lp-sub');
  if(!el||window.__yaqidhTyped)return;
  window.__yaqidhTyped=true;
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const full=el.textContent;
  el.style.minHeight=el.offsetHeight+'px';
  el.textContent='';
  el.classList.add('typing');
  let i=0;
  const timer=setInterval(()=>{i++;el.textContent=full.slice(0,i);if(i>=full.length){clearInterval(timer);el.classList.remove('typing')}},36);
}
