/* The guided demo (only when the server runs with YAQIDH_DEMO_MODE): a visitor plays developer, QA and security on one request.
   The banner says what is real and what is replayed, which role the visitor plays, and what to do next. */

let demoInfo=null;

function demoStep(guide){
  const role=profile.role,status=guide.status,phase=guide.phase;
  const swap=(to,label)=>'<button type="button" class="action" data-action="demo-role" data-id="'+to+'">'+label+'</button>';
  const push=()=>'<button type="button" class="action primary" data-action="demo-push">'+copy('ارفع على GitHub','Push to GitHub')+'</button>';
  const mine=(owner,doing,otherwise)=>role===owner?doing:otherwise;
  const toDev=swap('developer',copy('بدّل إلى المطوّر','Switch to the developer'));
  const toQa=swap('qa',copy('بدّل إلى مراجع الجودة','Switch to the QA reviewer'));
  const toSec=swap('security',copy('بدّل إلى مراجع الأمن','Switch to the security reviewer'));
  if(status==='none')
    return [1,mine('developer',
        copy('أنت المطوّر. ما فيه طلب بعد. اضغط «ارفع على GitHub» لتفتح طلب دمج جديد، ويقظ يفحصه تلقائيًا.','You are the developer. There is no request yet. Press "Push to GitHub" to open a new pull request, and Yaqidh checks it automatically.'),
        copy('ما فيه طلب بعد. بدّل لدور المطوّر وارفع طلبًا على GitHub.','There is no request yet. Switch to the developer and push a request to GitHub.')),
      mine('developer',push(),toDev)];
  if(status==='ready_to_merge')
    return [6,copy('انتهت القصة: الطلب جاهز للإطلاق. الموافقة مربوطة بهذه النسخة من الكود فقط. تقدر تضغط «ابدأ من جديد» وتجرّبها بدور ثاني.','The story is over: the request is ready to release. The approval is tied to this exact version of the code. Press "Start over" to try it with another role.'),''];
  if(status==='qa_rejected'||status==='security_rejected')
    return [phase>=2?5:phase>=1?4:2,copy('المراجع رجّع الطلب للمطوّر. بدّل لدور المطوّر، واضغط «ارفع على GitHub» ليفحص يقظ من جديد.','The reviewer sent the request back to the developer. Switch to the developer and press "Push to GitHub" so Yaqidh checks again.'),
      mine('developer',push(),toDev)];
  if(status==='qa_blocked')
    return [2,mine('developer',
        copy('يقظ فحص طلبك وفحص الجودة فشل: لقي مشاكل بالكود وشرحها لك بالعربي تحت. تخيّل إنك صلّحتها، ثم اضغط «ارفع على GitHub» لترفع التعديل.','Yaqidh checked your request and the quality check failed: it found problems in the code and explained them in Arabic below. Imagine you fixed them, then press "Push to GitHub" to push your change.'),
        copy('الطلب عند المطوّر لأن فحص الجودة فشل. بدّل لدور المطوّر.','The request is with the developer because the quality check failed. Switch to the developer.')),
      mine('developer',push(),toDev)];
  if(status==='awaiting_qa_approval')
    return [3,mine('qa',
        copy('يقظ أعاد الفحص تلقائيًا ونجحت كل الاختبارات. الحين دورك كمراجع جودة: اضغط «موافقة».','Yaqidh re-checked automatically and every test passed. Now it is your turn as the QA reviewer: press "Approve".'),
        copy('فحص الجودة نجح، والطلب ينتظر مراجع الجودة. بدّل لدوره ووافق.','The quality check passed and the request waits for the QA reviewer. Switch to that role and approve.')),
      mine('qa','',toQa)];
  if(status==='security_blocked'&&phase<2)
    return [4,mine('developer',
        copy('الجودة وافقت، وبدأ الفحص الأمني: يقظ لقي ثغرات بالكود والمكتبات وشرحها لك. تخيّل إنك صلّحتها، ثم اضغط «ارفع على GitHub».','Quality approved and the security check started: Yaqidh found vulnerabilities in the code and libraries and explained them. Imagine you fixed them, then press "Push to GitHub".'),
        copy('الفحص الأمني لقي ثغرات. بدّل لدور المطوّر ليصلحها.','The security check found vulnerabilities. Switch to the developer to fix them.')),
      mine('developer',push(),toDev)];
  if(status==='security_blocked')
    return [5,mine('security',
        copy('يقظ أعاد الفحص وأُغلقت الثغرات، وبقيت ملاحظة وحدة متوسطة. دورك كمراجع أمن: اقبل الاستثناء مع سبب مكتوب (أسفل الصفحة)، ثم اضغط «موافقة».','Yaqidh re-checked and the vulnerabilities are closed; one medium finding is left. Your turn as the security reviewer: accept the exception with a written reason (further down the page), then press "Approve".'),
        copy('أُغلقت الثغرات، وبقيت ملاحظة متوسطة تحتاج قرار مراجع الأمن. بدّل لدوره.','The vulnerabilities are closed; one medium finding needs the security reviewer. Switch to that role.')),
      mine('security','',toSec)];
  if(status==='awaiting_security_approval')
    return [5,mine('security',
        copy('كل شي جاهز لقرارك كمراجع أمن: اضغط «موافقة»، وتنفتح البوابة لهذه النسخة فقط.','Everything is ready for your decision as the security reviewer: press "Approve" and the gate opens for this version only.'),
        copy('الطلب ينتظر موافقة مراجع الأمن. بدّل لدوره ووافق.','The request waits for the security reviewer. Switch to that role and approve.')),
      mine('security','',toSec)];
  return [2,copy('يقظ يفحص الطلب...','Yaqidh is checking the request...'),''];
}

function demoBannerHtml(){
  if(!profile||!profile.guide||location.pathname!=='/dashboard')return '';
  const [step,text,buttons]=demoStep(profile.guide);
  const real=demoInfo&&demoInfo.githubUrl?' <a href="'+safe(demoInfo.githubUrl)+'" target="_blank" rel="noopener">'+copy('شاهد الطلب الحقيقي على GitHub','See the real request on GitHub')+'</a>':'';
  const roles=['developer','qa','security'].map(r=>'<button type="button" class="demo-role" data-action="demo-role" data-id="'+r+'" aria-pressed="'+(profile.role===r)+'">'+roleNames(r)+'</button>').join('');
  return '<section class="demo-banner" aria-label="'+copy('الديمو التفاعلي','Guided demo')+'">'
    +'<div class="demo-note"><b>'+copy('ديمو توضيحي','Guided demo')+'</b><span>'+copy('جُرّب النظام على طلب دمج حقيقي في GitHub. القرارات والشرح العربي والسجل يشتغلون بالنظام الحقيقي.','The system was tested on a real GitHub pull request. The decisions, the Arabic explanations and the evidence log run on the real system.')+real+'</span></div>'
    +'<div class="demo-roles" role="group" aria-label="'+copy('الدور الذي تلعبه','The role you are playing')+'"><span>'+copy('أنت تلعب دور:','You are playing:')+'</span>'+roles+'</div>'
    +'<div class="demo-step"><span class="demo-num">'+copy('الخطوة ','Step ')+step+copy(' من 6',' of 6')+'</span><p>'+text+'</p><div class="demo-actions">'+buttons
    +'<button type="button" class="action" data-action="demo-reset">'+copy('ابدأ من جديد','Start over')+'</button></div></div></section>';
}

/* the story moves when a reviewer approves or the developer pushes, so the banner follows without a reload */
setInterval(async()=>{
  if(!profile||!profile.guide||document.hidden||location.pathname!=='/dashboard')return;
  try{
    const fresh=await api('/api/dashboard');
    if(!fresh.guide||JSON.stringify(fresh.guide)===JSON.stringify(profile.guide))return;
    profile.guide=fresh.guide;
    const banner=document.querySelector('.demo-banner');
    if(banner)banner.outerHTML=demoBannerHtml();
  }catch{/* the next tick tries again */}
},2500);
