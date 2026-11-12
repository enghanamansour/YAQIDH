/* The guided demo (only when the server runs with YAQIDH_DEMO_MODE): a visitor plays developer, QA and security on one request.
   The banner says what is real and what is replayed, and tells the visitor what to do next. */

let demoInfo=null;

function demoStep(guide){
  const role=profile.role,status=guide.status,phase=guide.phase;
  const swap=(to,label)=>'<button type="button" class="action" data-action="demo-role" data-id="'+to+'">'+label+'</button>';
  const push=label=>'<button type="button" class="action primary" data-action="demo-push">'+label+'</button>';
  const mine=(owner,doing,else_)=>role===owner?doing:else_;
  if(status==='ready_to_merge')
    return [5,copy('انتهت القصة: الطلب جاهز للإطلاق، والموافقة مربوطة بهذه النسخة من الكود فقط. جرّب «ابدأ من جديد» وكرّرها بدور مختلف.','The story is done: the request is ready to release, and the approval is tied to this exact version of the code. Try "Start over" and play it again with another role.'),''];
  if(status==='qa_rejected'||status==='security_rejected')
    return [guide.phase>=2?4:guide.phase>=1?3:1,copy('المراجع أرجع الطلب للمطوّر. بدّل لدور المطوّر وارفع تعديلًا ليعيد يقظ الفحص.','The reviewer returned the request to the developer. Switch to the developer and push a change so Yaqidh checks again.'),
      mine('developer',push(copy('ارفع تعديلًا','Push a change')),swap('developer',copy('بدّل إلى المطوّر','Switch to the developer')))];
  if(status==='qa_blocked')
    return [1,mine('developer',
        copy('فشل فحص الجودة: يقظ لقي مشاكل وشرحها لك بالعربي أدناه. اقرأها، ثم اضغط «ارفع الإصلاح» كأنك رفعت تعديلًا على GitHub.','The quality check failed: Yaqidh found problems and explained them in Arabic below. Read them, then press "Push the fix" as if you pushed a change to GitHub.'),
        copy('الطلب عند المطوّر الحين، يصلّح مشاكل الجودة. بدّل لدور المطوّر لترفع الإصلاح.','The request is with the developer, fixing the quality problems. Switch to the developer to push the fix.')),
      mine('developer',push(copy('ارفع الإصلاح','Push the fix')),swap('developer',copy('بدّل إلى المطوّر','Switch to the developer')))];
  if(status==='awaiting_qa_approval')
    return [2,mine('qa',
        copy('أعاد يقظ الفحص تلقائيًا ونجحت كل الاختبارات. القرار لك كمراجع جودة: وافق من لوحة القرار.','Yaqidh re-checked automatically and every test passed. The decision is yours as the QA reviewer: approve it.'),
        copy('نجح فحص الجودة بعد الإصلاح، والطلب ينتظر موافقة مراجع الجودة. بدّل لدوره ووافق.','The quality check passed after the fix, and the request waits for the QA reviewer. Switch to that role and approve.')),
      mine('qa','',swap('qa',copy('بدّل إلى مراجع الجودة','Switch to the QA reviewer')))];
  if(status==='security_blocked'&&phase<2)
    return [3,mine('developer',
        copy('وافقت الجودة، وبدأ الفحص الأمني: لقي يقظ ثغرات في الكود والمكتبات وشرحها لك. عالجها ثم اضغط «ارفع الإصلاح الأمني».','Quality approved and the security check started: Yaqidh found vulnerabilities in the code and libraries and explained them. Fix them, then press "Push the security fix".'),
        copy('وافقت الجودة، ولقي الفحص الأمني ثغرات. بدّل لدور المطوّر ليصلحها.','Quality approved and the security check found vulnerabilities. Switch to the developer to fix them.')),
      mine('developer',push(copy('ارفع الإصلاح الأمني','Push the security fix')),swap('developer',copy('بدّل إلى المطوّر','Switch to the developer')))];
  if(status==='security_blocked')
    return [4,mine('security',
        copy('أعاد يقظ الفحص وأُغلقت الثغرات، وبقيت ملاحظة متوسطة وحدة. القرار لك كمراجع أمن: اقبل الاستثناء بسبب مكتوب (أسفل الصفحة)، ثم وافق.','Yaqidh re-checked and the vulnerabilities are closed; one medium finding remains. The decision is yours as the security reviewer: accept the exception with a written reason (further down), then approve.'),
        copy('أُغلقت الثغرات، وبقيت ملاحظة متوسطة تحتاج قرار مراجع الأمن. بدّل لدوره.','The vulnerabilities are closed; one medium finding needs the security reviewer. Switch to that role.')),
      mine('security','',swap('security',copy('بدّل إلى مراجع الأمن','Switch to the security reviewer')))];
  if(status==='awaiting_security_approval')
    return [4,mine('security',
        copy('كل شي جاهز لقرارك كمراجع أمن: وافق، وتنفتح البوابة لهذه النسخة فقط.','Everything is ready for your decision as the security reviewer: approve, and the gate opens for this version only.'),
        copy('الطلب ينتظر موافقة مراجع الأمن. بدّل لدوره ووافق.','The request waits for the security reviewer. Switch to that role and approve.')),
      mine('security','',swap('security',copy('بدّل إلى مراجع الأمن','Switch to the security reviewer')))];
  return [1,copy('يقظ يفحص الطلب...','Yaqidh is checking the request...'),''];
}

function demoBannerHtml(){
  if(!profile||!profile.guide||location.pathname!=='/dashboard')return '';
  const [step,text,buttons]=demoStep(profile.guide);
  const real=demoInfo&&demoInfo.githubUrl?' <a href="'+safe(demoInfo.githubUrl)+'" target="_blank" rel="noopener">'+copy('شاهد الطلب الحقيقي على GitHub','See the real request on GitHub')+'</a>':'';
  return '<section class="demo-banner" aria-label="'+copy('الديمو التفاعلي','Guided demo')+'">'
    +'<div class="demo-note"><b>'+copy('ديمو توضيحي','Guided demo')+'</b><span>'+copy('جُرّب النظام على طلب دمج حقيقي في GitHub. هنا نتائج الأدوات (Playwright وSemgrep وTrivy) مسجّلة من تشغيل حقيقي، والقرارات والشرح العربي والسجل يشتغلون بالنظام الحقيقي.','The system was tested on a real GitHub pull request. Here the tool results (Playwright, Semgrep, Trivy) are recorded from a real run, while the decisions, the Arabic explanations and the evidence log run on the real system.')+real+'</span></div>'
    +'<div class="demo-step"><span class="demo-num">'+copy('الخطوة ','Step ')+step+copy(' من 5',' of 5')+'</span><p>'+text+'</p><div class="demo-actions">'+buttons
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
