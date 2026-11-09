function aboutView(){
  const steps=[
    [copy('رفع التعديل','Submit change'),copy('المطور يرفع طلب دمج ويعالج الملاحظات عند الإرجاع.','The developer opens a pull request and addresses returned findings.')],
    [copy('فحوصات الجودة','QA checks'),copy('يقظ يشغّل أدوات الجودة، ومراجع الجودة يسجّل قراره.','YAQIDH runs QA tools and the QA reviewer records a decision.')],
    [copy('فحوصات الأمن','Security checks'),copy('الوكيل نفسه يشغّل أدوات الأمن على البناء في فرع ما قبل الإطلاق.','The same agent runs security tools on the staging build.')],
    [copy('قرار المراجع الأمني','Security decision'),copy('يراجع السايبر الأدلة ويسجّل الموافقة أو الإرجاع مع السبب.','The reviewer examines evidence and approves or returns the build with a reason.')]
  ];
  return '<section id="about" class="about-section"><section class="panel home-hero"><small>'+copy('الجاهزية الأمنية للإصدارات','Security readiness for releases')+'</small><h1>'+copy('يقظ يربط الفحص بالقرار','YAQIDH connects checks to decisions')+'</h1><p>'+copy('وكيل واحد يرافق التعديل في مرحلتَي الجودة والأمن. يشرح نتائج الأدوات ويحفظها في ملف أدلة يراجعه الإنسان قبل اتخاذ القرار.','One agent follows the change across QA and security. It explains tool results and records evidence for human review.')+'</p><a class="action primary" href="/dashboard">'+copy('فتح لوحة المتابعة','Open dashboard')+'</a></section><div class="metric-row">'
    +steps.map(([title,text],index)=>'<article class="panel"><small>'+copy('الخطوة','Step')+' '+(index+1)+'</small><h2>'+title+'</h2><p>'+text+'</p></article>').join('')+'</div><section class="panel workflow-loop"><b>↶ '+copy('عند الإخفاق أو الإرجاع','When a check fails or a change is returned')+'</b><p>'+copy('يرجع التعديل للمطور، ثم يعاد الفحص على التعديل الجديد. يحتفظ ملف الأدلة بنتائج كل جولة.','The developer updates the change and the checks run again. Evidence retains the result of each round.')+'</p></section></section>';
}
