/* The QA reviewer's page: one screen that answers "what do I need to do now?" and shows the evidence to decide on. */

const qaBlocked=status=>['qa_blocked','qa_rejected','security_blocked','security_rejected'].includes(status);
const qaTone=status=>qaBlocked(status)?'bad':status==='ready_to_merge'?'good':['awaiting_qa_approval','not_started','awaiting_security_scan','awaiting_security_approval'].includes(status)?'wait':'good';
const qaStepIndex=status=>({not_started:1,qa_blocked:1,awaiting_qa_approval:2,qa_rejected:2,awaiting_security_scan:3,security_blocked:3,awaiting_security_approval:4,security_rejected:4,ready_to_merge:5})[status]??1;

function qaStepper(status){
  const names=[copy('فتح الطلب','PR opened'),copy('فحص الجودة','Quality check'),copy('موافقة الجودة','QA approval'),copy('الفحص الأمني','Security check'),copy('موافقة الأمن','Security approval'),copy('جاهز للدمج','Ready to merge')];
  const now=qaStepIndex(status),tone=qaTone(status);
  return '<ol class="steps '+tone+'" aria-label="'+copy('رحلة الطلب','Request journey')+'">'
    +names.map((name,i)=>{
      const done=i<now||(status==='ready_to_merge'&&i===now);
      const cls=done?'done':i===now?'now':'todo';
      return '<li class="step '+cls+'"><i>'+(done?'✓':i+1)+'</i><span>'+name+'</span></li>';
    }).join('')+'</ol>';
}

function qaQueue(){
  const rows=profile.releases||[];
  const chip=item=>item.pendingReview?['wait',copy('ينتظر قرارك','Needs your decision')]
    :item.active==='security'?['good',copy('في الفحص الأمني','In security check')]
    :item.outcome==='fail'?['bad',copy('يحتاج إصلاح','Needs a fix')]:['wait',copy('بانتظار الفحص','Waiting for the check')];
  const waiting=rows.filter(r=>r.pendingReview).length;
  return '<section class="qa-queue-wrap"><div class="section-head"><h2>'+copy('قائمة الطلبات','Requests')+'</h2><small>'+waiting+' '+copy('بانتظار قرارك','waiting for you')+'</small></div>'
    +'<div class="qa-queue">'+rows.map(item=>{const [tone,label]=chip(item);
      return '<button type="button" class="qa-q '+(release&&item.id===release.id?'on':'')+'" data-action="queue" data-id="'+safe(item.id)+'"><b>'+safe(requestName(item.pr))+'</b><small>'+mon(item.commit)+'</small><span class="chip '+tone+'">'+label+'</span></button>';}).join('')+'</div></section>';
}

function qaHero(){
  const g=release.gate||{},status=g.status||(release.outcome?(release.outcome.result==='pass'?'awaiting_qa_approval':'qa_blocked'):'not_started');
  const checks=release.qaChecks||[],open=checks.filter(c=>c.state==='failed').length||release.findings.filter(f=>f.status==='open').length;
  const headline={
    qa_blocked:copy('فحص الجودة فشل','Quality check failed')+' · '+open+' '+copy('مشاكل مفتوحة','open problems'),
    awaiting_qa_approval:copy('فحص الجودة نجح · بانتظار قرارك','Quality check passed · waiting for your decision'),
    qa_rejected:copy('تم إرجاع الطلب للمطوّر','The request was returned to the developer'),
    not_started:copy('بانتظار نتائج الفحص','Waiting for the check results')
  }[status]||copy('وافقت الجودة على هذا الطلب','Quality approved this request');
  const todo={
    awaiting_qa_approval:copy('راجعي الفحوصات تحت، ثم اتخذي قرارك.','Review the checks below, then decide.'),
    qa_blocked:copy('لا شي الحين: بانتظار المطوّر. يقظ يعيد الفحص تلقائيًا بعد كل تعديل.','Nothing now: waiting for the developer. Yaqidh re-checks automatically after every change.'),
    qa_rejected:copy('لا شي الحين: بانتظار تعديل المطوّر.','Nothing now: waiting for the developer.'),
    not_started:copy('لا شي الحين: الفحص لم يكتمل.','Nothing now: the check has not finished.')
  }[status]||copy('لا شي: قرارك محفوظ، والفحص الأمني يتابع.','Nothing: your decision is saved and the security check continues.');
  const tone=qaTone(status),icon=tone==='good'?'✓':tone==='bad'?'✕':'…';
  const buttons=(release.canReject?action('reject',copy('إرجاع مع السبب','Return with a reason')):'')+(release.canApprove?action('approve',copy('موافقة','Approve'),'class="primary"'):'');
  const stagingOk=g.staging===true;
  return '<section class="qa-hero '+tone+'"><div class="qa-hero-main">'
    +'<p class="qa-kicker">'+safe(requestName(release.pr))+' · '+safe(branchName(release.branch))+' · '+mon(release.commit)+'</p>'
    +'<h1><span class="qa-ico big">'+icon+'</span> '+headline+'</h1>'
    +'<p class="qa-sub"><b>'+copy('المطلوب منك','Your part')+':</b> '+todo+'</p>'
    +(buttons?'<div class="actions qa-actions">'+buttons+'</div>':'')+'</div>'
    +'<div class="qa-gate '+(stagingOk?'good':'bad')+'"><small>'+copy('الدمج على staging','Merge to staging')+'</small><b>'+(stagingOk?copy('مسموح','Allowed'):copy('ممنوع','Blocked'))+'</b>'
    +(g.reasons&&g.reasons.length&&!stagingOk?'<small>'+g.reasons.map(r=>safe(displayReason(r))).join(' · ')+'</small>':'')+'</div></section>';
}

function qaCheckCard(c){
  const label={passed:copy('نجح','Passed'),failed:copy('فشل','Failed'),fixed:copy('انحلّت','Fixed'),pending:copy('بانتظار الفحص','Waiting')}[c.state];
  const tone={passed:'good',fixed:'good',failed:'bad',pending:'wait'}[c.state];
  const icon={passed:'✓',fixed:'✓',failed:'✕',pending:'…'}[c.state];
  const f=c.finding?release.findings.find(item=>item.fingerprint===c.finding):null;
  const why=c.state==='failed'&&f?'<details class="qa-why" open><summary>'+copy('شرح يقظ','Yaqidh explanation')+' '+badge(copy('كتبه الذكاء الاصطناعي · ليس حقيقة مثبتة','AI-written · not a verified fact'))+'</summary>'
    +(f.explanation?'<div class="explain">'+safe(f.explanation.text)+'</div>':'<p class="muted">'+copy('الشرح قيد الكتابة.','The explanation is being written.')+'</p>')
    +'<p>'+action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"')+'</p></details>':'';
  const fixed=c.state==='fixed'?'<p class="qa-fixed">'+copy('انحلّت · تأكّد منها المدقّق بعد إعادة الفحص','Fixed · confirmed by the verifier after the re-check')+'</p>':'';
  return '<article class="qa-check '+c.state+' '+tone+'"><span class="qa-ico">'+icon+'</span><div><h3>'+safe(copy(c.titleAr,c.titleEn))+'</h3><p class="muted">'+safe(copy(c.descAr,c.descEn))+'</p>'+why+fixed+'</div><span class="badge '+tone+'">'+label+'</span></article>';
}

function qaChecksSection(){
  const checks=release.qaChecks||[];
  if(!checks.length)return '';
  const count=s=>checks.filter(c=>c.state===s).length;
  return '<section><div class="section-head"><h2>'+copy('الفحوصات','Checks')+'</h2><small>'+checks.length+' · '+copy('نجح','passed')+' '+count('passed')+' · '+copy('فشل','failed')+' '+count('failed')+' · '+copy('انحلّت','fixed')+' '+count('fixed')+'</small></div>'
    +'<div class="qa-checks">'+checks.slice().sort((a,b)=>({failed:0,pending:1,fixed:2,passed:3}[a.state]-{failed:0,pending:1,fixed:2,passed:3}[b.state])).map(qaCheckCard).join('')+'</div></section>';
}

function qaHistorySection(){
  const log=release.log;
  if(!log||!log.entries||!log.entries.length)return '';
  const ok=log.verified&&log.verified.ok;
  const rows=log.entries.slice(-8).reverse().map(e=>'<li><span>'+mon(String(e.time).slice(11,16))+'</span><span>'+safe(eventName(e.event))+' <small>'+safe(eventDetail(e))+'</small></span><small>'+safe(e.actor)+'</small></li>').join('');
  return '<section class="panel"><div class="section-head"><h2>'+copy('السجل','History')+'</h2>'
    +badge(ok?copy('سلسلة السجل سليمة','History chain intact')+' · '+log.verified.entries:copy('السلسلة مكسورة','History chain broken'),ok?'good':'bad')+'</div><ul class="qa-history">'+rows+'</ul></section>';
}

function qaHow(){
  const step=(n,title,text)=>'<div><b>'+n+' · '+title+'</b><small>'+text+'</small></div>';
  return '<section class="qa-how" aria-label="'+copy('من يفعل ماذا','Who does what')+'">'
    +step(1,copy('الأدوات تفحص','Tools check'),copy('Playwright يجرب الموقع بنفسه','Playwright tries the site itself'))
    +step(2,copy('الكود يقرر','Code decides'),copy('نجح أو فشل من محرك السياسة، مو من الذكاء الاصطناعي','Pass or fail comes from the policy engine, not from the AI'))
    +step(3,copy('الذكاء الاصطناعي يشرح','AI explains'),copy('يشرح المشكلة فقط، ما يصلح ولا يوافق','It only explains; it never fixes or approves'))
    +step(4,copy('أنتِ توافقين','You approve'),copy('الدمج ما يفتح إلا بقرارك','Nothing opens without your decision'))+'</section>';
}

function qaView(){
  const head='<header class="qa-top"><div><h1>'+roleNames(profile.role)+'</h1><small>'+(isLive()?copy('بيانات حقيقية من خادم يقظ','Live data from the Yaqidh server'):copy('معاينة محلية','Local preview'))+'</small></div><div class="actions">'+action('refresh',copy('تحديث','Refresh'))+'</div></header>';
  if(!release)return liveWarning()+head+'<section class="panel qa-empty"><h2>'+copy('ما وصل أي طلب دمج بعد','No pull request has arrived yet')+'</h2><p class="muted">'+copy('لما يفتح المطوّر طلب دمج، يظهر هنا مع نتيجة الفحص تلقائيًا.','When a developer opens a pull request it appears here with its check result.')+'</p></section>'+qaHow();
  return liveWarning()+head+qaQueue()+qaStepper((release.gate||{}).status||'not_started')+qaHero()+qaChecksSection()
    +(release.log?'':'')+qaHistorySection()+qaHow();
}
