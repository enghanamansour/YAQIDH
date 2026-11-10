function reviewQueue(){
  const all=profile.releases||[];
  const state=item=>item.outcome==='fail'?copy('فشل','Failed'):item.pendingReview?copy('ينتظر قرارك','Awaiting your decision'):item.outcome==='pass'?copy('نجح','Passed'):copy('بانتظار الفحص','Awaiting checks');
  const lists=[
    [copy('الطلبات التي تنتظر الموافقة','Requests awaiting approval'),all.filter(item=>item.active===profile.role&&item.pendingReview)],
    [copy('الطلبات المفتوحة','Open requests'),all.filter(item=>item.active===profile.role&&!item.pendingReview)],
    [copy('الطلبات المغلقة','Closed requests'),all.filter(item=>item.active!==profile.role)]
  ];
  return '<section class="panel request-lists">'+lists.map(([title,rows])=>{
    const here=rows.some(item=>release&&item.id===release.id);
    return '<label class="field"><span>'+title+' · <b>'+rows.length+'</b></span><select class="request-pick" '+(rows.length?'':'disabled')+'>'
      +'<option value="">'+(rows.length?copy('اختاري طلبًا','Choose a request'):copy('لا توجد طلبات','No requests'))+'</option>'
      +rows.map(item=>'<option value="'+safe(item.id)+'" '+(here&&release&&item.id===release.id?'selected':'')+'>'+requestName(item.pr)+' · '+state(item)+'</option>').join('')+'</select></label>';
  }).join('')+'</section>';
}

function releaseHeader(){
  return (profile.role==='qa'?'':'<section class="intro"><div><h2>'+stageText(release.stage)+'</h2><small>'+safe(projectName(release.project))+' · '+safe(requestName(release.pr))+' · '+safe(branchName(release.branch))+' · '+mon(release.commit)+'</small></div>'
    +'</section>')
    +(profile.role==='qa'?'':statusPanel())
    +(profile.role==='qa'?'<h2 class="result-title">'+copy('نتيجة الفحص','Check result')+'</h2>':'')
    +(profile.role==='qa'?'':'<section class="summary '+(release.outcome?.result==='fail'?'bad':release.outcome?.result==='pass'?'good':'wait')+'"><div><b>'+copy('نتيجة الفحص','Check result')+' · '+outcomeText()+'</b><p>'
    +(release.outcome?.reasons.map(displayReason).join(' · ')||copy('تتوفر النتائج بعد اكتمال الفحوصات المطلوبة.','Results are available once required checks complete.'))+'</p></div>'
    +'<div><small>'+copy('قرارك','Your decision')+'</small><p>'+decisionText()+'</p></div></section>');
}

function findingsView(){
  const sources=[...new Set([...release.runs.map(r=>r.tool),...release.findings.map(f=>f.tool)])];
  const options=sources.map(id=>'<option value="'+safe(id)+'" '+(tool===id?'selected':'')+'>'+safe(toolName(id))+'</option>').join('');
  const rows=matched(), high=rows.filter(f=>f.severity==='high').length, low=rows.length-high;
  const records=rows.map(f=>'<tr><td>'+safe(findingName(f))+'<br><small>'+safe(f.location)+'</small></td><td>'+safe(toolName(f.tool))+'</td><td>'+badge(severityName(f.severity),f.severity==='high'?'bad':'good')+'</td><td>'+safe(findingState(f))+'</td><td>'
    +action('finding',copy('الدليل','Evidence'),'data-id="'+safe(f.fingerprint)+'"')+'</td></tr>').join('');
  return '<section class="panel"><div class="section-head"><h2>'+copy('فلترة الأدلة','Evidence filters')+'</h2><small>'+copy('نتيجة المرحلة محسوبة على البناء كاملًا','Stage outcome applies to the full build')+'</small></div><div class="filters">'
    +'<label>'+copy('أداة الفحص','Scan tool')+'<select id="tool-filter"><option value="all">'+copy('جميع الأدوات','All tools')+'</option>'+options+'</select></label>'
    +'<label>'+copy('خطورة الملاحظة','Finding severity')+'<select id="severity-filter"><option value="all">'+copy('جميع التصنيفات','All severities')+'</option>'
    +['high','low'].map(id=>'<option value="'+id+'" '+(id===severity?'selected':'')+'>'+severityName(id)+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',copy('قيد التنفيذ','In progress')],['fixed',copy('مغلقة','Closed')],['excepted',copy('مستثناة','Excepted')]])
     +adminSelect('run-filter',copy('حالة التشغيل','Run state'),runFilter,stateLabels())+'</div>'+chipRow([['tool',tool,toolName(tool)],['severity',severity,severityName(severity)],['finding',findingFilter,findingFilter==='all'?'':findingLabel(findingFilter)],['run',runFilter,statusText(runFilter)]],'clear')+'</section>'+stageCharts()
    +'<div class="findings-layout"><section class="panel"><h2>'+copy('الملاحظات المطابقة','Matching findings')+' · '+rows.length+'</h2>'
    +(records?'<div class="table-wrap"><table><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الأداة','Tool')+'</th><th>'+copy('الخطورة','Severity')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('التفاصيل','Details')+'</th></tr></thead><tbody>'+records+'</tbody></table></div>':'<p class="muted">'+copy('لا توجد ملاحظات مطابقة في السجل المعروض.','No matching findings in this record.')+'</p>')+'</section>'
    +'<section class="panel"><h2>'+copy('الملاحظات حسب الخطورة','Findings by severity')+'</h2>'
    +[['high',high],['low',low]].map(([id,count])=>'<div class="bar-row '+(id==='high'?'bad':'good')+'"><span>'+action('bar',severityName(id),'data-id="'+id+'" aria-pressed="'+(severity===id)+'"')+'<b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(rows.length,1)+'"></progress></div>').join('')+'</section></div>';
}

function qaReviewAlerts(records){
  return records.length?records.map(item=>'<article class="note"><b>'
    +(item.kind==='exception'?copy('اعتمد الأمن استثناءً','Security approved an exception'):copy('اعتمد الأمن تمديد المهلة','Security approved an extension'))
    +'</b><p>'+safe(buildName(item.build))+' · '+mon(item.commit)+' · '+safe(accountName(item.by))+'</p>'
    +'<p>'+(item.approvedDeadline?copy('الموعد الجديد المعتمد','Approved new deadline')+' '+displayReviewDeadline(item.approvedDeadline)
      :copy('لا يوجد موعد جديد معتمد لهذه الملاحظة.','No new deadline has been approved for this finding.'))+'</p></article>').join('')
    :'<p>'+copy('لا توجد قرارات أمنية معتمدة ضمن نطاقك.','No approved security decisions in your scope.')+'</p>';
}

function qaReviewAlertsPanel(){
  return '<section class="panel"><h2>'+copy('تنبيهات قرارات الأمن السيبراني','Security decision alerts')+'</h2><div id="qa-review-alerts" aria-live="polite">'+qaReviewAlerts(profile.reviewAlerts)+'</div></section>';
}

async function refreshQAReviewAlerts(){
  const account=profile;
  const panel=app.querySelector('#qa-review-alerts');
  if(account?.role!=='qa'||!panel||document.hidden)return;
  try{
    const alerts=await api('/api/qa/review-alerts');
    if(profile!==account||!panel.isConnected)return;
    if(JSON.stringify(alerts)===JSON.stringify(account.reviewAlerts))return;
    account.reviewAlerts=alerts;
    panel.innerHTML=qaReviewAlerts(alerts);
  }catch{
    // Keep the last successful alert list until the next refresh.
  }
}

function reviewView(){
  if(!release)return '<section class="panel">'+copy('لا يوجد بناء في نطاق الحساب','No builds in this account scope')+'</section>';
  const open=matched().filter(f=>findingGroup(f)==='open');
  const blockers=release.findings.filter(f=>(release.blockerIds||[]).includes(f.fingerprint));
  const closed=matched().filter(f=>f.closure?.result==='closed');
  const visibleRuns=release.runs.filter(r=>(tool==='all'||r.tool===tool)&&(runFilter==='all'||r.state===runFilter));
  const completed=visibleRuns.filter(r=>r.state==='completed');
  const unread=threads.filter(thread=>thread.release===release.id&&thread.unread);
  if(profile.role==='qa'){
    const shown=qaShowsRelease();
    const main=shown?qaResult(open,closed):qaEmptyResult();
    return '<div class="qa-page">'+greeting()+'<div class="qa-app">'+qaRail()+'<div class="qa-main">'+main+'</div></div>'+'<div class="qa-below">'+(shown?qaMetrics(open,closed)+qaDetailsHtml+qaStory():qaZeroMetrics())+'</div>'+'</div>';
  }

  const pendingRequests=profile.role==='security'?threads.filter(thread=>thread.release===release.id
    && (thread.exceptionRequest||thread.deadline)?.status==='pending'):[];
  const reviewLinks=pendingRequests.map(thread=>'<a class="action" href="/communication?thread='+encodeURIComponent(thread.id)+'">'
    +(thread.exceptionRequest?copy('مراجعة طلب استثناء','Review exception request'):copy('مراجعة طلب تمديد','Review extension request'))+'</a>').join('');
  return greeting()+reviewQueue()+releaseHeader()
    +(profile.role==='qa'?qaMetrics(open,closed):'<div class="metric-row">'+(profile.role==='security'?metric(copy('ملاحظات مانعة','Blocking findings'),release.outcome?blockers.length:'—',blockers.length?'bad':'',blockers,buildScope(release.outcome?.reasons.map(displayReason).join(' · ')||copy('بانتظار نتيجة محرك القواعد.','Awaiting a policy outcome.')),findingRecord):metric(copy('مشاكل مفتوحة','Open problems'),open.length,open.length?'wait':'',open,buildScope(copy('الملاحظات المطابقة التي تحتاج متابعة.','Matching findings that need follow-up.')),findingRecord))
    +metric(copy('مشاكل انحلّت','Problems fixed'),closed.length,'good',closed,buildScope(copy('الإغلاقات المثبتة ضمن الفلاتر الحالية.','Verified closures within active filters.')),findingRecord)
    +metric(copy('تشغيلات مكتملة في السجل','Completed recorded runs'),visibleRuns.length?fraction(completed.length,visibleRuns.length):'—','',visibleRuns,buildScope(copy('المكتمل من التشغيلات المطابقة للأداة وحالة التشغيل.','Completed runs out of those matching tool and run-state filters.')),runRecord)
    +metric(copy('محادثات تنتظر الاطلاع','Unread conversations'),unread.length,'',unread,buildScope(copy('المحادثات غير المقروءة لهذا البناء.','Unread conversations for this build.')),thread=>'<a href="/communication?thread='+encodeURIComponent(thread.id)+'">'+safe(threadText(thread.subject))+'</a>')+'</div>')
    +'<section class="panel"><div class="section-head"><h2>'+copy('أدلة المرحلة والإجراءات','Stage evidence and actions')+'</h2><div class="actions">'
    +(profile.role==='qa'?action('new-thread',copy('مراسلة المطوّر','Message the developer')):'')+action('runs',copy('سجل تشغيل الأدوات','Tool runs'))+action('evidence',copy('ملف الأدلة','Evidence'))+action('decisions',copy('سجل القرارات','Decision log'))
    +(profile.role==='security'?action('previous-qa',copy('موافقة الجودة السابقة','Previous QA approval')):'')+(release.prior?action('prior',copy('البناء السابق','Previous build')):'')
    +reviewLinks
    +(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')
    +(release.canApprove?action('approve',profile.role==='security'?copy('اعتماد البناء','Approve build'):copy('تسجيل الموافقة','Record approval'),'class="primary"'):'')
    +'</div></div></section>'+findingsView()+'<section class="panel"><h2>'+copy('السجل','History')+'</h2>'+historyView()+'</section>';
}

function greeting(){
  if(profile.role!=='qa'&&profile.role!=='developer')return '';
  return '<header class="greet"><p class="greet-hi">'+copy('أهلًا بك','Welcome')+(profile.display?'، '+safe(profile.display):'')+'</p><h1 class="greet-title">'+(profile.role==='developer'?copy('لوحة متابعة المطوّر','Developer dashboard'):copy('لوحة متابعة الجودة','QA dashboard'))+'</h1></header>';
}

function qaMetrics(open,closed){
  const checks=release.qaChecks||[];
  const failedTests=checks.filter(c=>c.state==='failed');
  const passedTests=checks.filter(c=>c.state==='passed'||c.state==='fixed');
  const awaiting=(profile.releases||[]).filter(r=>r.active===profile.role&&r.pendingReview);
  const testRecord=c=>'<b>'+safe(copy(c.titleAr,c.titleEn))+'</b><br><small>'+safe(copy(c.descAr,c.descEn))+'</small>';
  const issueRecord=f=>'<b>'+safe(findingName(f))+'</b><br><small>'+copy('الدليل','Evidence')+': '+safe(f.detail||'—')+'</small> '+action('finding',copy('كل التفاصيل','All details'),'data-id="'+safe(f.fingerprint)+'"');
  const fixedRecord=f=>'<b>'+safe(findingName(f))+'</b><br><small>'+copy('انحلّت · تأكّد النظام بعد إعادة الفحص','Fixed · confirmed by the system after a re-check')+(f.closure&&f.closure.timestamp?' · '+mon(String(f.closure.timestamp).slice(0,16).replace('T',' ')):'')+'</small> '+action('finding',copy('كل التفاصيل','All details'),'data-id="'+safe(f.fingerprint)+'"');
  const requestRecord=r=>safe(requestName(r.pr))+' '+action('queue',copy('فتح الطلب','Open request'),'data-id="'+safe(r.id)+'"');
  return '<div class="metric-row five">'
    +metric(copy('العدد الإجمالي للاختبارات الفاشلة','Total failed tests'),failedTests.length,failedTests.length?'bad':'',failedTests,buildScope(copy('الاختبارات التي فشلت في هذا الطلب.','Tests that failed in this request.')),testRecord)
    +metric(copy('العدد الإجمالي للاختبارات الناجحة','Total passed tests'),passedTests.length,'good',passedTests,buildScope(copy('الاختبارات التي نجحت في هذا الطلب.','Tests that passed in this request.')),testRecord)
    +metric(copy('عدد المشاكل المفتوحة','Open problems'),open.length,open.length?'wait':'',open,buildScope(copy('كل مشكلة ودليلها.','Each problem with its evidence.')),issueRecord)
    +metric(copy('عدد المشاكل التي انحلّت','Problems fixed'),closed.length,'good',closed,buildScope(copy('مشاكل تأكّد النظام من إصلاحها.','Problems the system confirmed as fixed.')),fixedRecord)
    +metric(copy('عدد الطلبات التي تنتظر موافقتك','Requests awaiting your approval'),awaiting.length,awaiting.length?'wait':'',awaiting,copy('الطلبات التي نجحت اختباراتها وتنتظر قرارك.','Requests whose tests passed and need your decision.'),requestRecord)+'</div>';
}

function qaDecision(){
  return '<section class="panel"><div class="section-head"><h2>'+copy('قرارك','Your decision')+'</h2><div class="actions">'
    +action('new-thread',copy('مراسلة المطوّر','Message the developer'))
    +(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')
    +(release.canApprove?action('approve',copy('تسجيل الموافقة','Record approval'),'class="primary"'):'')
    +'</div></div>'+(release.canApprove||release.canReject?'':'<p class="muted">'+copy('لا قرار مطلوب منك الحين.','No decision is needed from you now.')+'</p>')+'</section>';
}

function qaResult(open,closed){
  const checks=release.qaChecks||[];
  const reqs=release.requirements||[];
  const tone=release.outcome?.result==='pass'?'good':release.outcome?.result==='fail'?'bad':'wait';
  const reqTone={met:'good',failed:'bad',pending:'wait',uncovered:'wait'};
  const reqLabel={met:copy('تحقق','Met'),failed:copy('لم يتحقق','Not met'),pending:copy('بانتظار الفحص','Waiting'),uncovered:copy('غير مغطّى','Not covered')};
  const byState=st=>reqs.filter(r=>r.state===st);
  const failedR=byState('failed'),metR=byState('met'),restR=reqs.filter(r=>r.state==='pending'||r.state==='uncovered');
  const okTests=checks.filter(c=>c.state==='passed'||c.state==='fixed').length;
  const ok=reqs.length?metR.length:okTests,count=reqs.length||Math.max(checks.length,1);
  const pct=Math.round(ok/count*100);
  const row=r=>'<li class="req '+reqTone[r.state]+'"><span class="req-id">'+safe(r.id)+'</span><span class="req-title">'+safe(copy(r.titleAr,r.titleEn))+(r.checks.length?'<small>'+r.checks.map(c=>safe(copy(c.titleAr,c.titleEn))).join('، ')+'</small>':'')+'</span><span class="pill '+reqTone[r.state]+'">'+reqLabel[r.state]+'</span></li>';
  const group=(title,list,kind,openIt)=>list.length?'<details class="req-group '+kind+'"'+(openIt?' open':'')+'><summary><span>'+title+'</span><b>'+list.length+'</b></summary><ul>'+list.map(row).join('')+'</ul></details>':'';
  const seg=(list,t,x)=>list.length?'<rect class="seg '+t+'" x="'+x+'" y="0" width="'+(list.length/reqs.length*100)+'" height="8" rx="2"/>':'';
  const bar=reqs.length?'<svg viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">'+seg(metR,'good',0)+seg(failedR,'bad',metR.length/reqs.length*100)+seg(restR,'wait',(metR.length+failedR.length)/reqs.length*100)+'</svg>':'';
  const shield='<div class="shield-chart qa-shield '+tone+'"><svg viewBox="0 0 140 145" aria-hidden="true"><path class="shield-outer" d="M70 6 131 26v46c0 35-26 53-61 68C35 125 9 107 9 72V26Z"/><path class="shield-inner" d="M70 15 122 32v40c0 30-22 46-52 59C40 118 18 102 18 72V32Z"/></svg><div class="shield-content"><strong>'+outcomeText()+'</strong></div></div>';
  const ring='<div class="qa-ring-wrap"><svg viewBox="0 0 108 108" class="chart-donut qa-ring" role="img" aria-label="'+ok+' / '+count+'"><circle class="qa-ring-track" cx="54" cy="54" r="39" pathLength="100"/><circle class="qa-ring-ok" cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="100" stroke-dashoffset="'+(100-pct)+'"/><text x="54" y="60">'+ok+'/'+count+'</text></svg></div>';
  const decide=(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')+(release.canApprove?action('approve',copy('تسجيل الموافقة','Record approval'),'class="primary"'):'');
  const summary=reqs.length?'<b>'+failedR.length+'</b> '+copy('من','of')+' <b>'+reqs.length+'</b> '+copy('متطلب لم يتحقق','requirements are not met'):'';
  const key=reqs.length?'<div class="qa-req-key"><span class="good">'+copy('تحققت','Met')+' '+metR.length+'</span><span class="bad">'+copy('لم تتحقق','Not met')+' '+failedR.length+'</span><span class="wait">'+copy('غير مغطّاة','Not covered')+' '+restR.length+'</span><span class="fixed">'+copy('مشاكل انحلّت','Problems fixed')+' '+closed.length+'</span></div>':'<div class="qa-req-key"><span class="fixed">'+copy('مشاكل انحلّت','Problems fixed')+' '+closed.length+'</span></div>';
  const source=release.requirementsSource&&release.requirementsSource.kind==='github'?'<p class="req-source">'+copy('المصدر: GitHub','Source: GitHub')+' · <span dir="ltr">'+safe(release.requirementsSource.repo)+'/'+safe(release.requirementsSource.path)+'</span></p>':'';
  qaDetailsHtml=reqs.length?'<details class="qa-card qa-reqs-card"><summary><h3 class="card-title">'+copy('المتطلبات','Requirements')+'</h3><span>'+reqs.length+' · '+copy('اضغطي للعرض','tap to view')+'</span></summary>'+source+group(copy('لم تتحقق','Not met'),failedR,'bad',true)+group(copy('تحققت','Met'),metR,'good',false)+group(copy('غير مغطّاة أو بانتظار الفحص','Not covered or waiting'),restR,'wait',false)+'</details>':'';
  return '<section class="qa-card qa-verdict qa-solo '+tone+'"><div class="verdict-top"><span class="eyebrow">'+copy('نتيجة الفحص','Check result')+'</span>'+(decide?'<div class="actions">'+decide+'</div>':'')+'</div>'+ring+'<small class="ring-cap">'+copy('متطلبات تحققت','requirements met')+'</small></section>';
}

let qaDetailsHtml='';
function qaCurrentTab(){
  const all=profile.releases||[];
  const item=release?all.find(r=>r.id===release.id):null;
  return qaTab||(item?qaGroup(item):qaDefaultTab());
}
function qaShowsRelease(){
  if(!release)return false;
  const item=(profile.releases||[]).find(r=>r.id===release.id);
  return Boolean(item)&&qaGroup(item)===qaCurrentTab();
}
function qaEmptyResult(){
  const ring='<div class="qa-ring-wrap"><svg viewBox="0 0 108 108" class="chart-donut qa-ring" role="img" aria-label="0 / 0"><circle class="qa-ring-track" cx="54" cy="54" r="39" pathLength="100"/><text x="54" y="60">0/0</text></svg></div>';
  return '<section class="qa-card qa-verdict qa-solo wait"><div class="verdict-top"><span class="eyebrow">'+copy('نتيجة الفحص','Check result')+'</span></div>'+ring+'<small class="ring-cap">'+copy('اختاري طلبًا من القائمة','Choose a request from the list')+'</small></section>';
}
function qaZeroMetrics(){
  const z=(label,tone)=>metric(label,0,tone,[],'',safe);
  return '<div class="metric-row five">'+z(copy('العدد الإجمالي للاختبارات الفاشلة','Total failed tests'),'')+z(copy('العدد الإجمالي للاختبارات الناجحة','Total passed tests'),'')+z(copy('عدد المشاكل المفتوحة','Open problems'),'')+z(copy('عدد المشاكل التي انحلّت','Problems fixed'),'')+z(copy('عدد الطلبات التي تنتظر موافقتك','Requests awaiting your approval'),'')+'</div>';
}

let qaTab=null;
function qaGroup(item){
  if(profile.role==='developer')return (item.returnReason||item.outcome==='fail')?'action':item.gate==='ready_to_merge'?'done':'review';
  return item.active!==profile.role?'closed':item.pendingReview?'awaiting':'open';
}
const qaDefaultTab=()=>profile.role==='developer'?'action':'open';
function qaRail(){
  const all=profile.releases||[];
  const groups=profile.role==='developer'?[['action',copy('تحتاج إجراءك','Needs you')],['review',copy('قيد المراجعة','In review')],['done',copy('جاهزة','Ready')]]:[['awaiting',copy('تنتظر موافقتك','Awaiting you')],['open',copy('مفتوحة','Open')],['closed',copy('مغلقة','Closed')]];
  const current=qaCurrentTab();
  const rows=all.filter(r=>qaGroup(r)===current);
  const status=item=>item.outcome==='fail'?['bad',copy('فشل','Failed')]:item.pendingReview?['wait',copy('ينتظر قرارك','Awaiting you')]:item.outcome==='pass'?['good',copy('نجح','Passed')]:['wait',copy('بانتظار الفحص','Waiting')];
  const pick='<label class="rail-pick"><span>'+copy('اختاري الطلب','Choose a request')+'</span><select class="request-pick">'+(release?'':'<option value="">—</option>')
    +groups.map(([id,label])=>{const list=all.filter(r=>qaGroup(r)===id);return list.length?'<optgroup label="'+label+'">'+list.map(item=>'<option value="'+safe(item.id)+'" '+(release&&item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+status(item)[1]+'</option>').join('')+'</optgroup>':''}).join('')+'</select></label>';
  return '<aside class="qa-rail"><span class="eyebrow">'+copy('الطلبات','Requests')+'</span>'+pick+'<div class="rail-tabs" role="tablist">'
    +groups.map(([id,label])=>'<button type="button" role="tab" aria-selected="'+(id===current)+'" class="'+(id===current?'on':'')+'" data-action="qa-tab" data-id="'+id+'">'+label+'<b>'+all.filter(r=>qaGroup(r)===id).length+'</b></button>').join('')+'</div>'
    +'<div class="rail-list">'+(rows.length?rows.map(item=>{const [t,l]=status(item);return '<div class="rail-item"><button type="button" class="rail-row '+t+(release&&item.id===release.id?' on':'')+'" data-action="queue" data-id="'+safe(item.id)+'"><i></i><span class="rail-name">'+safe(requestName(item.pr))+'</span><small>'+safe(branchName(item.branch||''))+'</small><em>'+l+'</em></button>'+'</div>'}).join(''):'<p class="muted rail-empty">'+copy('لا توجد طلبات هنا.','No requests here.')+'</p>')+'</div>'+(current==='awaiting'&&profile.role==='qa'?'<button type="button" class="rail-approve" data-action="approve" '+(release&&release.canApprove&&qaShowsRelease()?'':'disabled ')+'title="'+copy('تتفعّل لما يوصلك طلب ناجح ينتظر موافقتك','Enabled when a passing request is waiting for you')+'">'+copy('موافقة','Approve')+'</button>':'')+'</aside>';
}

function reqModal(id){
  const r=(release.requirements||[]).find(x=>x.id===id);
  if(!r)return;
  const tone={met:'good',failed:'bad',pending:'wait',uncovered:'wait'}[r.state];
  const label={met:copy('تحقق','Met'),failed:copy('لم يتحقق','Not met'),pending:copy('بانتظار الفحص','Waiting'),uncovered:copy('غير مغطّى: لا يوجد اختبار','Not covered: no test')}[r.state];
  const full=(release.qaChecks||[]);
  const rows=r.checks.map(c=>{const chk=full.find(x=>x.id===c.id)||c;const f=chk.finding?release.findings.find(x=>x.fingerprint===chk.finding):null;const good=c.state==='passed'||c.state==='fixed';
    return '<li class="req-test '+(good?'good':c.state==='failed'?'bad':'wait')+'"><i>'+(good?'✓':c.state==='failed'?'✕':'…')+'</i><span><b>'+safe(copy(c.titleAr,c.titleEn))+'</b>'+(f&&f.detail?'<small>'+safe(f.detail)+'</small>':'')+'</span>'+(f?action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"'):'')+'</li>'}).join('');
  modal(safe(r.id)+' · '+safe(copy(r.titleAr,r.titleEn)),'<p><span class="pill '+tone+'">'+label+'</span></p>'+(rows?'<ul class="req-tests">'+rows+'</ul>':'<p class="muted">'+copy('هذا المتطلب ما له اختبار بعد.','This requirement has no test yet.')+'</p>'));
}

function qaStory(){
  const entries=((release.log||{}).entries||[]).filter(e=>profile.role==='developer'||!(e.data||{}).stage||(e.data||{}).stage==='qa');
  const findingOf=fp=>release.findings.find(f=>f.fingerprint===fp);
  const line=e=>{const d=e.data||{};
    if(e.event==='event')return ['wait',d.event==='pull_request_opened'?copy('المطوّر فتح الطلب على GitHub','The developer opened the request on GitHub'):copy('المطوّر رفع تعديلًا جديدًا','The developer pushed a new change'),''];
    if(e.event==='scan')return ['wait',copy('فحص يقظ الطلب','Yaqidh checked the request'),d.findings+' '+copy('مشكلة وُجدت','problems found')];
    if(e.event==='rescan')return ['good',copy('أعاد يقظ الفحص','Yaqidh re-checked'),copy('انحلّت','Fixed')+' '+(d.closed||[]).length+' · '+copy('بقيت','Still open')+' '+(d.still_open||[]).length+' · '+copy('جديدة','New')+' '+(d.new||[]).length];
    if(e.event==='policy_decision')return [d.result==='pass'?'good':'bad',d.result==='pass'?copy('قرر النظام: نجح','The system decided: passed'):copy('قرر النظام: فشل','The system decided: failed'),(d.reasons||[]).map(displayReason).join(' · ')];
    if(e.event==='explanation'){const f=findingOf(d.fingerprint);return ['wait',copy('شرح الوكيل المشاكل للمطوّر','The agent explained the problems to the developer'),f?findingName(f)+(((f.explanation&&f.explanation.text)||d.text)?': '+((f.explanation&&f.explanation.text)||d.text):''):(d.text||'')];}
    if(e.event==='human_decision')return [d.decision==='approve'?'good':'bad',d.decision==='approve'?copy('وافق مراجع الجودة','The QA reviewer approved'):copy('أرجع مراجع الجودة الطلب','The QA reviewer returned the request'),d.reason||''];
    return null};
  const rows=[];
  let prev='';
  entries.forEach(e=>{const l=line(e);if(!l)return;if(e.event==='policy_decision'&&prev==='rescan'){prev=e.event;return}prev=e.event;const last=rows[rows.length-1];if(last&&last.text===l[1]&&e.event==='explanation'){if(l[2]&&!last.detail.includes(l[2]))last.detail+=(last.detail?'\n\n':'')+l[2];return}if(last&&last.text===l[1]&&last.detail===l[2])return;rows.push({tone:l[0],text:l[1],detail:l[2],time:String(e.time).slice(0,16).replace('T',' ')})});
  if(!rows.length)return '';
  const shown=rows.slice(-10);
  return '<details class="qa-card qa-log qa-reqs-card"><summary><h3 class="card-title">'+copy('السجل','History')+'</h3><span>'+shown.length+' · '+copy('اضغطي للعرض','tap to view')+'</span></summary><ol>'
    +shown.map(r=>'<li class="'+r.tone+'"><details><summary><i></i><span>'+safe(r.text)+'</span><small>'+mon(r.time)+'</small></summary>'+(r.detail?'<p>'+safe(r.detail)+'</p>':'')+'</details></li>').join('')+'</ol></details>';
}
