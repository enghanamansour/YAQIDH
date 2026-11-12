function secData(){
  const open=release.findings.filter(f=>findingGroup(f)==='open');
  const closed=release.findings.filter(f=>f.closure?.result==='closed'||findingGroup(f)==='fixed');
  const eligible=new Set(release.exceptionEligible||[]);
  const medium=open.filter(f=>eligible.has(f.fingerprint)||f.reported_as==='medium');
  const high=open.filter(f=>!medium.includes(f));
  const requests=threads.filter(t=>t.release===release.id&&(t.exceptionRequest||t.deadline)&&(t.exceptionRequest||t.deadline).status==='pending');
  const awaiting=(profile.releases||[]).filter(r=>r.active==='security'&&r.pendingReview);
  return {open,closed,medium,high,requests,awaiting};
}

function secResult(){
  const d=secData();
  const total=release.findings.length;
  const ok=d.closed.length;
  const pct=total?Math.round(ok/total*100):100;
  const tone=release.outcome?.result==='pass'?'good':release.outcome?.result==='fail'?'bad':'wait';
  const ring='<div class="qa-ring-wrap"><svg viewBox="0 0 108 108" class="chart-donut qa-ring" role="img" aria-label="'+ok+' / '+total+'"><circle class="qa-ring-track" cx="54" cy="54" r="39" pathLength="100"/><circle class="qa-ring-ok" cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="100" stroke-dashoffset="'+(100-pct)+'"/><text x="54" y="60">'+ok+'/'+total+'</text></svg></div>';
  const decide=(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')+(release.canApprove?action('approve',copy('موافقة','Approve'),'class="primary"'):'');
  return '<section class="qa-card qa-verdict qa-solo '+tone+'"><div class="verdict-top"><span class="eyebrow">'+copy('نتيجة الفحص','Check result')+'</span>'+(decide?'<div class="actions">'+decide+'</div>':'')+'</div>'+ring
    +'<small class="ring-cap">'+copy('ثغرات انحلّت من الإجمالي','vulnerabilities fixed out of the total')+'</small></section>';
}

function secZero(){
  const z=(label,tone)=>metric(label,0,tone,[],'',safe);
  return '<div class="metric-row five">'+z(copy('ثغرات أُغلقت','Vulnerabilities closed'),'')+z(copy('ثغرات عالية الخطورة مفتوحة','High-severity vulnerabilities open'),'')+z(copy('ثغرات متوسطة تحتاج قرارك','Medium vulnerabilities for your decision'),'')+z(copy('طلبات تنتظر موافقتك','Requests awaiting your approval'),'')+'</div>';
}

function secMetrics(d){
  const rec=f=>'<b>'+safe(findingName(f))+'</b> '+badge(severityName(f.severity),f.severity==='high'?'bad':'good')+'<br><small>'+safe(f.detail||'—')+'</small> '+action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"');
  const reqRecord=r=>safe(requestName(r.pr))+' '+action('queue',copy('فتح الطلب','Open request'),'data-id="'+safe(r.id)+'"');
  return '<div class="metric-row five">'
    +metric(copy('ثغرات أُغلقت','Vulnerabilities closed'),d.closed.length,'good',d.closed,buildScope(copy('ثغرات تأكّد النظام من إصلاحها.','Findings the system confirmed as fixed.')),rec)
    +metric(copy('ثغرات عالية الخطورة مفتوحة','High-severity vulnerabilities open'),d.high.length,d.high.length?'bad':'',d.high,buildScope(copy('ثغرات عالية تمنع الإطلاق وما تُستثنى.','High findings block the release and cannot be excepted.')),rec)
    +metric(copy('ثغرات متوسطة تحتاج قرارك','Medium vulnerabilities for your decision'),d.medium.length,d.medium.length?'wait':'',d.medium,buildScope(copy('ثغرات متوسطة يمكن استثناؤها بقرارك.','Medium findings that you may except.')),rec)
    +metric(copy('طلبات تنتظر موافقتك','Requests awaiting your approval'),d.awaiting.length,d.awaiting.length?'wait':'',d.awaiting,copy('طلبات اكتمل فحصها وتنتظر قرارك.','Requests whose checks are complete and wait for you.'),reqRecord)+'</div>';
}

function secTools(){
  const rep=release.reports||{},v=release.toolVersions||{};
  const tools=[['semgrep','Semgrep',copy('فحص الكود','Code scan'),'⌗',['semgrep-rules']],['trivy','Trivy',copy('المكتبات والأسرار','Libraries and secrets'),'◫',['trivy','trivy-db']]];
  const cards=tools.map(([id,name,what,icon,keys])=>{
    const mine=release.findings.filter(f=>f.tool===id),openN=mine.filter(f=>findingGroup(f)==='open').length;
    const ver=keys.filter(k=>v[k]).map(k=>k+' '+String(v[k]).slice(0,10)).join(' · ');
    const m=rep[id];
    return '<div class="qa-card rep-card"><span class="rep-ico">'+icon+'</span><div class="rep-body"><b>'+name+'</b><small>'+what+' · '+copy(openN+' من '+mine.length+' قيد التنفيذ',openN+' of '+mine.length+' in progress')+'</small><small>'+(ver?safe(ver):'—')+'</small></div>'
      +(m?'<a class="action rep-dl" href="/api/releases/'+encodeURIComponent(release.id)+'/reports/'+id+'" download>'+copy('تنزيل التقرير','Download report')+'</a>':'<span class="muted rep-wait">'+copy('يظهر بعد الفحص القادم','Shown after the next check')+'</span>')+'</div>';
  }).join('');
  return '<section class="rep-section"><div class="rep-head"><h3 class="card-title">'+copy('نتائج أدوات الأمن السيبراني','Cybersecurity tool results')+'</h3><small>'+copy('التقرير كما أصدرته الأداة نفسها، بدون تعديل.','The report exactly as the tool printed it, unchanged.')+'</small></div><div class="dev-stages">'+cards+'</div></section>';
}

function secRequests(d){
  const row=t=>{
    const exc=t.exceptionRequest,req=exc||t.deadline;
    const f=exc?release.findings.find(x=>x.fingerprint===t.finding):null;
    const title=exc?copy('طلب استثناء','Exception request')+(f?': '+safe(findingName(f)):''):copy('طلب تمديد المهلة','Deadline extension request');
    const why=exc?safe(demoText(req.reason||'')):copy('الموعد المقترح','Proposed deadline')+' '+displayReviewDeadline(req.requested);
    const buttons=action('approve-review-request',exc?copy('قبول الاستثناء','Approve exception'):copy('اعتماد التمديد','Approve extension'),'class="primary" data-id="'+safe(t.id)+'"')
      +(exc?'':action('adjust-review-deadline',copy('تعديل الموعد','Adjust deadline'),'data-id="'+safe(t.id)+'"'))
      +action('reject-review-request',copy('رفض','Reject'),'data-id="'+safe(t.id)+'"');
    return '<li class="sec-req"><span class="req-title"><b>'+title+'</b><small>'+why+'</small></span><span class="actions">'+buttons+'</span></li>';
  };
  return '<details class="qa-card qa-reqs-card qa-exc"'+(d.requests.length?' open':'')+'><summary><h3 class="card-title">'+copy('طلبات المطوّر','Developer requests')+'</h3><span>'+d.requests.length+' · '+(d.requests.length?copy('تنتظر قرارك','waiting for you'):copy('لا طلبات','none'))+'</span></summary>'
    +(d.requests.length?'<ul class="sec-reqs">'+d.requests.map(row).join('')+'</ul>':'<p class="rep-note">'+copy('لا توجد طلبات استثناء أو تمديد الآن.','There are no exception or extension requests now.')+'</p>')+'</details>';
}

function securityView(){
  const shown=qaShowsRelease();
  const main=shown?secResult():qaEmptyResult();
  let below=secZero();
  if(shown){const d=secData();below=secMetrics(d)+secTools()+secRequests(d)+exceptionPanel()+devBelowOld()+qaStory()}
  return '<div class="qa-page">'+greeting()+'<div class="qa-app">'+qaRail()+'<div class="qa-main">'+main+'</div></div><div class="qa-below">'+below+exceptionsSection()+'</div></div>';
}
