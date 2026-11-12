/* The landing page: what Yaqidh is, the problem it removes, how a request moves, and who decides what. */

function landing(){
  const variant=['bg','edge','emblem','side','clean'].includes(new URLSearchParams(location.search).get('hero'))?new URLSearchParams(location.search).get('hero'):'side';
  // a visitor is invited to create an account (signing in stays in the top bar); a signed-in person opens their dashboard
  const go=profile?(profile.role==='company-admin'?'/admin':'/dashboard'):'/signup';
  const goLabel=profile?copy('فتح لوحة المتابعة','Open the dashboard'):copy('إنشاء حساب جديد','Create a new account');
  const journey=[
    [copy('فتح الطلب','Pull request opened'),copy('المطوّر يرفع تعديله على GitHub.','The developer pushes a change to GitHub.')],
    [copy('فحص الجودة','Quality check'),copy('يفحص الجودة الأمنية للتطبيق عبر اختبارات تحاكي سيناريوهات الهجوم.','Checks the security quality of the application with tests that simulate attack scenarios.')],
    [copy('موافقة الجودة','QA approval'),copy('يراجع المختص نتائج الاختبارات ويقيّمها، ثم يقرر اعتماد التعديل أو إعادته للمطوّر مع توضيح الملاحظات.','A specialist reviews and assesses the test results, then approves the change or returns it to the developer with the findings explained.')],
    [copy('الفحص الأمني','Security check'),copy('يحلل الكود والمكتبات البرمجية لاكتشاف الثغرات الأمنية، ويشرح مخاطرها، ثم يعيد الفحص للتحقق من نجاح الإصلاحات.','Analyzes the code and libraries to find vulnerabilities, explains their risks, then re-checks to verify the fixes worked.')],
    [copy('موافقة الأمن','Security approval'),copy('يراجع المختص نتائج الفحص والثغرات المتبقية، ويقرر اعتماد التعديل أو إعادته لمعالجة المخاطر.','A specialist reviews the results and the remaining vulnerabilities, then approves the change or returns it to address the risks.')],
    [copy('جاهز للإطــلاق','Ready to release'),copy('بعد الاعتماد النهائي من المختص، يُسمح بالإطلاق.','After the specialist\'s final approval, the release is allowed.')]
  ];
  const ring=(r,cls)=>'<svg class="lp-ring '+cls+'" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="'+r+'"/></svg>';
  return '<main class="landing2">'
    +'<section class="lp-hero v-'+variant+'"><div class="lp-bg" aria-hidden="true"><div class="lp-grid"></div></div>'
    +'<div class="lp-hero-inner"><div class="lp-copy">'
    +'<h1>'+copy('<span class="lp-l">أمــان <span class="grad">استباقــي</span>،</span> <span class="lp-l">إطــلاق أســرع.</span>','<span class="lp-l"><span class="grad">Proactive</span> security,</span> <span class="lp-l">faster releases.</span>')+'</h1>'
    +'<p class="lp-sub">'+copy('يَقِـــظ يرافــق منتجــك قبــل الإطــلاق: يفحــص، يشــرح، ويعيــد الفحــص تلقائيــًا، والقــرار دائمًــا بيــد الفريــق.','Yaqidh accompanies your product before release: it checks, explains and re-checks automatically, and the decision always stays with your team.')+'</p>'
    +'<div class="actions lp-cta"><a class="action primary" href="'+go+'">'+goLabel+'</a><a class="action" href="#about">'+copy('كيف يعمل','How it works')+'</a></div></div>'
    +'<div class="lp-art" aria-hidden="true">'+ring(190,'a')+ring(150,'b')+''+animatedLogo()+'</div></div></section>'

    +'<section class="lp-section" id="problem"><span class="lp-eyebrow">'+copy('المشكلة','The problem')+'</span><h2>'+copy('كل مراجعة أمنية تعني دورة جديدة من الانتظار.','Every security review means a new round of waiting.')+'</h2>'
    +'<div class="lp-two"><article class="lp-col lp-bad"><h3 class="lp-col-title">'+copy('بدون يَقِـــظ','Without Yaqidh')+'</h3>'
    +seq('bad',[[ICON.shield,copy('فريق الأمن السيبراني','Cybersecurity team')],[ICON.code,copy('المطوّر','Developer')]],[
      ['to-start',copy('يُرسل المنتج إلى فريق الأمن السيبراني','The product is sent to the cybersecurity team')],
      ['to-end',copy('يفحصه الفريق وتُكتشف ثغرات، فيعود المنتج للمطوّر','The team checks it and finds vulnerabilities, so it returns to the developer')],
      ['to-start',copy('يُصلح المطوّر ويُعاد المنتج للتحقق من نجاح الإصلاحات','The developer fixes it and it is sent back to verify the fixes')],
      ['to-end',copy('وتُكتشف ثغرات أخرى... فتتكرر الدورة','Then other vulnerabilities appear... and the cycle repeats')]],
      '<div class="seq-lap" aria-hidden="true"><span>↻ '+copy('لفّة 1','Round 1')+'</span><span>↻ '+copy('لفّة 2','Round 2')+'</span><span>↻ '+copy('لفّة 3','Round 3')+'</span></div>')
    +'<p class="muted">'+copy('وقت أطول في المراجعات، وجهد متكرر بين فريقي التطوير والأمن السيبراني، وتأخير في إطلاق المنتج.','More time in reviews, repeated effort between the development and cybersecurity teams, and a delayed product release.')+'</p></article>'
    +'<article class="lp-col lp-good"><h3 class="lp-col-title"><span class="grad">'+copy('مع يَقِـــظ','With Yaqidh')+'</span></h3>'
    +seq('good',[[ICON.loop,copy('يَقِـــظ','Yaqidh')],[ICON.code,copy('المطوّر','Developer')]],[
      ['to-start',copy('المطوّر يرفع تعديله على GitHub، فيُفحص تلقائيًا.','The developer pushes a change to GitHub and it is checked automatically.')],
      ['to-end',copy('يكتشف المشكلات الأمنية ويحللها ويشرحها للمطوّر','Finds and analyzes security issues and explains them to the developer')],
      ['to-start',copy('يُصلح المطوّر، فيُعاد الفحص تلقائيًا للتحقق','The developer fixes it and the check re-runs automatically to verify')],
      ['to-end',copy('تُغلق المشكلات المعالجة، وتتجهز النتائج للمراجعة','Fixed problems are closed and the results are ready for review')]],
      '<div class="seq-final"><span class="seq-chip">'+ICON.shield+copy('يجهّز النتائج للفريق الأمني لاتخاذ القرار النهائي','Prepares the results for the security team to make the final decision')+'</span></div>')
    +'<p class="muted">'+copy('فحوصات مؤتمتة، مراجعات أكثر وضوحًا، وطريق أسرع نحو الإطلاق الآمن.','Automated checks, clearer reviews, and a faster path to a safe release.')+'</p></article></div></section>'

    +'<section class="lp-section" id="about"><span class="lp-eyebrow">'+copy('كيف يعمل','How it works')+'</span><h2>'+copy('كيف يمشي الطلب','How a request moves')+'</h2>'
    +swim(journey)
    +'</section>'

    +'<section class="lp-section" id="features"><span class="lp-eyebrow">'+copy('المميزات','Features')+'</span><h2>'+copy('ما الذي يميّز يَقِـــظ','What sets Yaqidh apart')+'</h2>'
    +'<div class="lp-feat">'+features().map(([icon,title,text])=>'<article class="lp-card"><span class="lp-ico">'+icon+'</span><h3>'+title+'</h3><p class="muted">'+text+'</p></article>').join('')+'</div></section>'

    +'<section class="lp-final"><h2>'+copy('جاهز تجرّب؟','Ready to try it?')+'</h2><div class="actions"><a class="action primary" href="'+go+'">'+goLabel+'</a></div></section>'
    +'<footer class="lp-foot">'+copy('يَقِـــظ · الجاهزية الأمنية للإصدارات','Yaqidh · security readiness for releases')+'</footer></main>';
}

/* what sets Yaqidh apart: only claims the product really keeps */
function features(){
  const i=(d)=>'<svg viewBox="0 0 24 24" aria-hidden="true">'+d+'</svg>';
  return [
    [i('<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.5"/>'),
      copy('إثبات الإغلاق','Proof of closure'),
      copy('لا تُغلق الثغرة بكلام المطوّر، بل بإعادة فحص تلقائية تثبت أنها أُغلقت فعلًا.','A vulnerability is not closed on the developer\'s word, but by an automatic re-check that proves it is really closed.')],
    [i('<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9.5h8M8 12.5h5"/>'),
      copy('شرح عربي لكل ثغرة','An Arabic explanation for every finding'),
      copy('ما المشكلة، ولماذا هي مهمة، وكيف تُصلح، بلغة بسيطة يفهمها المطوّر.','What the problem is, why it matters and how to fix it, in plain language the developer understands.')],
    [i('<circle cx="12" cy="8" r="3.6"/><path d="M5 20c1-4 4-6 7-6s6 2 7 6"/>'),
      copy('القرار بيد الإنسان','The human decides'),
      copy('الذكاء الاصطناعي يشرح فقط، ولا يقرر ولا يدمج ولا يوافق. الموافقة لمراجع بشري باسمه وسببه.','The AI only explains. It never decides, merges or approves. Approval comes from a human reviewer, by name and with a reason.')],
    [i('<path d="M12 4v16M5 8h14M7 8l-3 6a3 3 0 0 0 6 0zM17 8l-3 6a3 3 0 0 0 6 0z"/>'),
      copy('قواعد واضحة وثابتة','Clear, fixed rules'),
      copy('الخطورة العالية تُحجب ولا تُستثنى، والمتوسطة تُستثنى بسبب مسجّل وموافقة، والمنخفضة تُسجَّل.','High severity is blocked and never excepted, medium can be excepted with a recorded reason and approval, low is recorded.')],
    [i('<path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4M10 12h6M10 16h6"/>'),
      copy('سجل أدلة قابل للمراجعة','A reviewable evidence log'),
      copy('كل خطوة وقرار يُسجَّل، والموافقة مربوطة بنسخة الكود نفسها.','Every step and decision is recorded, and the approval is tied to that exact version of the code.')]
  ];
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

/* a sequence diagram: two actors and the arrows that go back and forth between them */
const ICON={
  shield:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 5-3.2 8.6-7 10-3.8-1.4-7-5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  code:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 6l-3 12"/></svg>',
  loop:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v4h-4"/></svg>'
};
function seq(kind,actors,rows,tail){
  return '<div class="seq '+kind+'"><div class="seq-head">'+actors.map(([icon,name])=>'<span class="seq-actor">'+icon+'<b>'+name+'</b></span>').join('')+'</div>'
    +'<ol class="seq-rows">'+rows.map(([dir,text])=>'<li class="'+dir+'"><span class="seq-text">'+text+'</span><span class="seq-arrow"></span></li>').join('')+'</ol>'+tail+'</div>';
}

/* swimlanes: who does each step (the specialist, يَقِـــظ, or the developer) and how the request moves between them */
ICON.person='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.6"/><path d="M5 20c1-4 4-6 7-6s6 2 7 6"/></svg>';
function swim(steps){
  const lanes=['dev','auto','human','auto','human','human'];
  const col={human:'col1',auto:'col2',dev:'col3'};
  const links=[['l23','to-start'],['l12','to-start'],['l12','to-end'],['l12','to-start'],['l11','down']];
  const head=[['human',ICON.person,copy('المختص','The specialist'),copy('قرار بشري','Human decision')],['auto',ICON.loop,copy('يَقِـــظ','Yaqidh'),copy('تلقائي','Automatic')],['dev',ICON.code,copy('المطوّر','The developer'),copy('يُصلح ويرفع','Fixes and pushes')]];
  const lane=l=>({human:copy('قرار بشري','Human decision'),auto:copy('تلقائي','Automatic'),dev:copy('المطوّر','Developer')})[l];
  let body='';
  steps.forEach(([title,text],i)=>{
    body+='<article class="sw-node '+col[lanes[i]]+' '+lanes[i]+'"><span class="sw-num">'+(i+1)+'</span><div><small class="sw-tag">'+lane(lanes[i])+'</small><h3>'+title+'</h3><p>'+text+'</p></div></article>';
    if(links[i])body+='<div class="sw-link '+links[i][0]+' '+links[i][1]+'" aria-hidden="true"><i class="a"></i><i class="b"></i></div>';
  });
  return '<div class="sw"><div class="sw-head">'+head.map(([k,icon,name,tag])=>'<span class="sw-actor '+k+'">'+icon+'<b>'+name+'</b><small>'+tag+'</small></span>').join('')+'</div><div class="sw-body">'+body+'</div></div>';
}
