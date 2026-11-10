/* The QA reviewer's page: one screen that answers "what do I need to do now?" and shows the evidence to decide on. */

const qaBlocked=status=>['qa_blocked','qa_rejected','security_blocked','security_rejected'].includes(status);
const qaTone=status=>qaBlocked(status)?'bad':status==='ready_to_merge'?'good':['awaiting_qa_approval','not_started','awaiting_security_scan','awaiting_security_approval'].includes(status)?'wait':'good';
const qaStepIndex=status=>({not_started:1,qa_blocked:1,awaiting_qa_approval:2,qa_rejected:2,awaiting_security_scan:3,security_blocked:3,awaiting_security_approval:4,security_rejected:4,ready_to_merge:5})[status]??1;

function qaQueue(){
  const rows=profile.releases||[];
  if(rows.length<2)return '';
  const dot=item=>item.pendingReview?'wait':item.outcome==='fail'?'bad':'good';
  return '<nav class="qa-queue" aria-label="'+copy('الطلبات','Requests')+'">'+rows.map(item=>'<button type="button" class="qa-q '+dot(item)+' '+(release&&item.id===release.id?'on':'')+'" data-action="queue" data-id="'+safe(item.id)+'"><i></i>'+safe(requestName(item.pr))+'</button>').join('')+'</nav>';
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
  const reasons=g.reasons&&g.reasons.length&&!stagingOk?' · '+g.reasons.map(r=>safe(displayReason(r))).join(' · '):'';
  return '<section class="qa-hero '+tone+'"><span class="qa-ico big">'+icon+'</span><div class="qa-hero-main">'
    +'<p class="qa-kicker">'+safe(requestName(release.pr))+' · '+safe(branchName(release.branch))+' · '+mon(release.commit)+'</p>'
    +'<h1>'+headline+'</h1><p class="qa-sub">'+todo+'</p>'
    +'<p class="qa-gate-line '+(stagingOk?'good':'bad')+'">'+copy('الدمج على staging','Merge to staging')+': <b>'+(stagingOk?copy('مسموح','Allowed'):copy('ممنوع','Blocked'))+'</b>'+reasons+'</p></div>'
    +(buttons?'<div class="actions qa-actions">'+buttons+'</div>':'')+'</section>';
}

function qaCheckCard(c){
  const label={passed:copy('نجح','Passed'),failed:copy('فشل','Failed'),fixed:copy('انحلّت','Fixed'),pending:copy('بانتظار الفحص','Waiting')}[c.state];
  const tone={passed:'good',fixed:'good',failed:'bad',pending:'wait'}[c.state];
  const icon={passed:'✓',fixed:'✓',failed:'✕',pending:'…'}[c.state];
  const f=c.finding?release.findings.find(item=>item.fingerprint===c.finding):null;
  const why=c.state==='failed'?'<p class="qa-short">'+safe(copy(c.descAr,c.descEn))+'</p><details class="qa-more"><summary>'+copy('ليش فشل؟','Why did it fail?')+'</summary>'
    +(f&&f.explanation?'<div class="explain">'+safe(f.explanation.text)+'</div><p class="muted">'+badge(copy('كتبه الذكاء الاصطناعي · ليس حقيقة مثبتة','AI-written · not a verified fact'))+'</p>':'<p class="muted">'+copy('الشرح قيد الكتابة.','The explanation is being written.')+'</p>')
    +(f?'<p>'+action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"')+'</p>':'')+'</details>':'';
  return '<article class="qa-tile '+c.state+' '+tone+'"><span class="qa-ico big">'+icon+'</span><h3>'+safe(copy(c.titleAr,c.titleEn))+'</h3><span class="qa-state">'+label+'</span>'+why+'</article>';
}

function qaChecksSection(){
  const checks=release.qaChecks||[];
  if(!checks.length)return '';
  const order={failed:0,pending:1,fixed:2,passed:3};
  const ok=checks.filter(c=>c.state==='passed'||c.state==='fixed').length;
  const bad=checks.filter(c=>c.state==='failed').length;
  const pct=Math.round(ok/checks.length*100);
  return '<section class="qa-checks2"><div class="qa-score"><div class="qa-score-n"><b>'+ok+'</b><span>/ '+checks.length+'</span></div><div class="qa-score-t"><strong>'+copy('فحوصات ناجحة','checks passed')+(bad?' · '+bad+' '+copy('فشلت','failed'):'')+'</strong>'
    +'<div class="qa-bar '+(bad?'bad':'good')+'"><i class="p'+Math.round(pct/10)+'"></i></div></div></div>'
    +'<div class="qa-tiles">'+checks.slice().sort((a,b)=>order[a.state]-order[b.state]).map(qaCheckCard).join('')+'</div></section>';
}

function qaHistorySection(){
  const log=release.log;
  if(!log||!log.entries||!log.entries.length)return '';
  const all=log.entries.slice().reverse();
  const row=e=>'<li><i></i><span>'+safe(eventName(e.event))+'</span><small>'+mon(String(e.time).slice(11,16))+'</small></li>';
  return '<section class="qa-hist"><div class="section-head"><h2>'+copy('آخر الأحداث','Recent events')+'</h2></div><ul>'+all.slice(0,3).map(row).join('')+'</ul>'
    +(all.length>3?'<details class="qa-more"><summary>'+copy('كل السجل','Full history')+' ('+all.length+')</summary><ul>'+all.slice(3,15).map(row).join('')+'</ul></details>':'')+'</section>';
}

function qaView(){
  const head='<header class="qa-top"><div><h1>'+roleNames(profile.role)+'</h1><small>'+(isLive()?copy('بيانات حقيقية من خادم يقظ','Live data from the Yaqidh server'):copy('معاينة محلية','Local preview'))+'</small></div><div class="actions">'+action('refresh',copy('تحديث','Refresh'))+'</div></header>';
  if(!release)return liveWarning()+head+'<section class="panel qa-empty"><h2>'+copy('ما وصل أي طلب دمج بعد','No pull request has arrived yet')+'</h2><p class="muted">'+copy('لما يفتح المطوّر طلب دمج، يظهر هنا مع نتيجة الفحص تلقائيًا.','When a developer opens a pull request it appears here with its check result.')+'</p></section>'
  return liveWarning()+head+qaQueue()+qaHero()+qaChecksSection()
    +qaHistorySection();
}
