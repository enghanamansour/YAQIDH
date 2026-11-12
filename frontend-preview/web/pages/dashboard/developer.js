function developerPriority(){
  const returned=profile.releases.filter(item=>item.returnReason);
  return '<section class="panel dev-priority"><h2>'+copy('يحتاج إجراء منك','Needs your action')+'</h2>'
    +(returned.length?returned.map(item=>'<article class="note dev-return"><div><b>'+safe(requestName(item.pr))+'</b> · '+safe(stageText(item.active))+'<p>'+safe(demoText(item.returnReason))+'</p><small>'+copy('عالج المشكلة وارفع التعديل لإعادة الفحص.','Address the finding and resubmit the change for checking.')+'</small></div>'
    +action('returned-build',copy('عرض سبب الإرجاع','View return reason'),'data-id="'+safe(item.id)+'"')+'</article>').join(''):'<p>'+copy('لا توجد تعديلات معادة إليك.','No changes have been returned to you.')+'</p>')+'</section>';
}

function assignedBuildTable(rows){
  return '<section class="panel"><h2>'+copy('الطلبات المسندة','Assigned requests')+'</h2><div class="table-wrap"><table><thead><tr><th>'+copy('طلب الدمج','Pull request')+'</th><th>'+copy('البناء','Build')+'</th><th>'+copy('المرحلة','Stage')+'</th><th>'+copy('الإجراء','Action')+'</th></tr></thead><tbody>'+rows.map(item=>'<tr><td>'+safe(requestName(item.pr))+'</td><td>'+safe(buildName(item.build))+'</td><td>'+safe(stageText(item.active))+'</td><td>'+action('queue',copy('عرض المشكلات','View findings'),'data-id="'+safe(item.id)+'"')+'</td></tr>').join('')+'</tbody></table></div>'+(rows.length?'':'<p>'+copy('لا توجد تعديلات مطابقة.','No matching changes.')+'</p>')+'</section>';
}

function legacyDeveloperView(){
  if(!release)return '<section class="panel">'+copy('لا توجد تعديلات مسندة إلى حسابك.','No changes are assigned to your account.')+'</section>';
  const pending=matched().filter(f=>findingGroup(f)==='open');
  const fixed=matched().filter(f=>findingGroup(f)==='fixed');
  const dated=profile.releases.filter(item=>developerDay==='all'||item.day===developerDay);
  const assigned=dated.filter(item=>developerOutcome==='all'||(item.outcome||'pending')===developerOutcome);
  const returns=assigned.filter(item=>item.returnReason);
  const requests=[...new Map(assigned.map(item=>[item.pr,item])).values()];
  const counts=['pass','fail',null].map(id=>({state:id==='pass'?'completed':id==='fail'?'error':'pending',count:dated.filter(item=>item.outcome===id).length}));
  const rows=matched().map(f=>'<tr><td>'+safe(findingName(f))+'<br><small>'+mon(f.location)+'</small></td><td>'+findingState(f)+'</td><td>'+action('finding',copy('فتح الدليل','Open evidence'),'data-id="'+safe(f.fingerprint)+'"')+'</td></tr>').join('');
  return '<div class="developer-workspace">'+developerPriority()+statusPanel()
    +'<section class="panel filters"><label>'+copy('الطلب','Pull request and build')+'<select id="release-select">'+profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+safe(buildName(item.build))+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',copy('قيد التنفيذ','In progress')],['fixed',copy('مغلقة','Closed')],['excepted',copy('مستثناة','Excepted')]])
    +action('decisions',copy('عرض قرار المراجع','View reviewer decision'))+'</section>'+chipRow([['finding',findingFilter,copy('حالة المعالجة','Remediation status')],['developer-outcome',developerOutcome,copy('نتائج الأبنية','Build outcomes')],['developer-day',developerDay,copy('اليوم','Day')+' · '+developerDay]],'clear')
    +'<div class="metric-row">'+metric(copy('طلبات الدمج المسندة','Assigned pull requests'),requests.length,'',requests,copy('طلبات دمج مميزة ضمن الأبنية المسندة المطابقة.','Distinct pull requests in the matching assigned builds.'),buildRecord)+metric(copy('طلبات معادة للمعالجة','Returned requests'),returns.length,'bad',returns,copy('أبنية مسندة آخر قرار لها الإرجاع.','Assigned builds whose latest decision was a return.'),buildRecord)+metric(copy('تنتظر إعادة الفحص','Awaiting recheck'),pending.length,'wait',pending,buildScope(copy('مشكلات مطابقة لم يثبت إغلاقها.','Matching findings awaiting verified closure.')),findingRecord)+metric(copy('مشكلات انحلّت','Problems fixed'),fixed.length,'good',fixed,buildScope(copy('مشكلات مطابقة ثبت إغلاقها.','Matching findings with verified closure.')),findingRecord)+'</div>'
    +'<div class="role-charts">'+qaChart(matched(),copy('حالات المعالجة','Remediation status'))+toolRunChart(counts.flatMap(item=>Array.from({length:item.count},()=>item)),true)+'</div>'+adminTimeline(profile.releases.filter(item=>item.day&&(developerOutcome==='all'||(item.outcome||'pending')===developerOutcome)).map(item=>({day:item.day,state:item.outcome==='fail'?'error':item.outcome==='pass'?'completed':'pending'})),true)+assignedBuildTable(assigned)
    +'<section class="panel"><h2>'+copy('أدلة المعالجة','Remediation evidence')+'</h2>'+(rows?'<div class="table-wrap"><table><thead><tr><th>'+copy('المشكلة','Finding')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الدليل','Evidence')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>'+copy('لا توجد مشكلات مطابقة.','No matching findings.')+'</p>')+'</section></div>';
}

function devRail(){
  const all=profile.releases||[];
  const dot=item=>item.returnReason||item.outcome==='fail'||qaBlocked((item.gate||''))?'bad':item.gate==='ready_to_merge'?'good':'wait';
  return '<aside class="qa-rail dev-rail"><span class="eyebrow">'+copy('الطلبات','Requests')+'</span><div class="rail-list">'
    +all.map(item=>'<button type="button" class="rail-row '+dot(item)+(release&&item.id===release.id?' on':'')+'" data-action="queue" data-id="'+safe(item.id)+'"><i></i><span class="rail-name">'+safe(requestName(item.pr))+'</span></button>').join('')+'</div></aside>';
}

function developerView(){
  if(!release)return '<div class="qa-page">'+greeting()+'<div class="qa-app dev-app">'+qaRail()+'<div class="qa-main">'+devEmptyResult()+'</div></div><div class="qa-below"><div class="dev-stages">'+devStageCard('qa')+devStageCard('security')+'</div></div></div>';
  return '<div class="qa-page">'+greeting()+'<div class="qa-app dev-app">'+qaRail()+'<div class="qa-main">'+devResult()+'</div></div><div class="qa-below">'+devBelow()+'</div></div>';
}

function devData(){
  const bySev=(x,y)=>(y.severity==='high')-(x.severity==='high');
  const open=release.findings.filter(f=>findingGroup(f)==='open').sort(bySev);
  const fixed=release.findings.filter(f=>f.closure?.result==='closed'||findingGroup(f)==='fixed').sort(bySev);
  const reqs=release.requirements||[];
  const met=reqs.filter(r=>r.state==='met').length;
  const decisions=(release.decisions||[]);
  const lastReject=decisions.length&&decisions[decisions.length-1].decision==='reject'?decisions[decisions.length-1]:null;
  const scans=((release.log||{}).entries||[]).filter(e=>e.event==='scan'||e.event==='rescan').length;
  const item=(profile.releases||[]).find(r=>r.id===release.id)||{};
  return {open,fixed,reqs,met,lastReject,scans,item};
}

function devNextStep(d){
  const st=(release.gate||{}).status||'';
  if(d.lastReject)return ['bad',copy('الطلب رجع لك','The request came back to you'),(d.lastReject.reason?safe(demoText(d.lastReject.reason))+'. ':'')+copy('عالج المشكلات وارفع تعديلًا على GitHub، ويعيد يَقِـــظ الفحص تلقائيًا.','Fix the problems and push a change on GitHub; Yaqidh re-checks automatically.')];
  if(d.open.length)return ['bad',copy('عندك '+d.open.length+' مشكلات لازم تنحل','You have '+d.open.length+' problems to fix'),copy('ارفع التعديل على نفس الطلب في GitHub، ويعيد يَقِـــظ الفحص تلقائيًا.','Push the fix to the same request on GitHub; Yaqidh re-checks automatically.')];
  if(st==='ready_to_merge')return ['good',copy('جاهز للإطلاق','Ready to release'),copy('اعتمد المراجعان الطلب، والدمج مسموح.','Both reviewers approved; merging is allowed.')];
  return ['wait',copy('بانتظار المراجع','Waiting for the reviewer'),copy('اختباراتك نجحت، والطلب ينتظر قرار '+(release.stage==='security'?'مراجع الأمن':'مراجع الجودة')+'.','Your checks passed; the request waits for the '+(release.stage==='security'?'security':'QA')+' reviewer.')];
}

function devResult(){
  const d=devData();
  const status=(release.gate||{}).status||(release.stage==='security'?'security_blocked':'qa_blocked');
  const now=qaStepIndex(status),tone=qaTone(status),s=release.stages||{};
  const names=[copy('فتح الطلب','Request opened'),copy('فحص الجودة','Quality check'),copy('موافقة الجودة','QA approval'),copy('الفحص الأمني','Security check'),copy('موافقة الأمن','Security approval'),copy('جاهز للإطلاق','Ready to release')];
  const openN=n=>(s[n]||{}).open||d.open.length;
  const note={
    qa_blocked:copy(openN('qa')+' تحتاج إصلاحك','To fix: '+openN('qa')),not_started:copy('جاري الفحص','Checking'),
    awaiting_qa_approval:copy('بانتظار مراجع الجودة','Waiting for the QA reviewer'),qa_rejected:copy('أرجعه مراجع الجودة','Returned by the QA reviewer'),
    awaiting_security_scan:copy('بانتظار بدء الفحص الأمني','Waiting for the security check'),
    security_blocked:copy(openN('security')+' تحتاج إصلاحك','To fix: '+openN('security')),
    awaiting_security_approval:copy('بانتظار مراجع الأمن','Waiting for the security reviewer'),security_rejected:copy('أرجعه مراجع الأمن','Returned by the security reviewer'),
    ready_to_merge:copy('اعتمد المراجعان الطلب','Both reviewers approved')}[status]||'';
  const rtl=document.documentElement.dir!=='ltr';
  const X=i=>rtl?520-i*96:40+i*96;
  const bad=tone==='bad',ready=status==='ready_to_merge';
  const cur=ready?5:now;
  let svg='<svg viewBox="0 0 560 196" class="jm" role="img" aria-label="'+copy('خريطة رحلة الطلب','Request journey map')+'"><title>'+copy('خريطة رحلة الطلب','Request journey map')+'</title>';
  svg+='<line class="jm-track" x1="'+X(0)+'" y1="78" x2="'+X(5)+'" y2="78"/>';
  if(cur>0)svg+='<line class="jm-ok-line" x1="'+X(0)+'" y1="78" x2="'+X(Math.max(cur-1,0))+'" y2="78"/>';
  if(cur>0&&!ready)svg+='<line class="jm-now-line '+tone+'" x1="'+X(cur-1)+'" y1="78" x2="'+X(cur)+'" y2="78"/>';
  if(ready)svg+='<line class="jm-ok-line" x1="'+X(4)+'" y1="78" x2="'+X(5)+'" y2="78"/>';
  names.forEach((name,i)=>{
    const done=i<cur||(ready&&i===5),here=i===cur&&!ready,x=X(i);
    if(here)svg+='<circle class="jm-halo '+tone+'" cx="'+x+'" cy="78" r="27"/>';
    svg+='<circle class="jm-st '+(done?'done':here?'now '+tone:'todo')+'" cx="'+x+'" cy="78" r="'+(here?17:14)+'"/>';
    svg+='<text class="jm-mark '+(done||here?'on':'')+'" x="'+x+'" y="'+(here?84:83)+'" text-anchor="middle">'+(done?'✓':here?(bad?'✕':'…'):(i===5?'⚑':i+1))+'</text>';
    svg+='<text class="jm-name '+(here?'now '+tone:done?'':'todo')+'" x="'+x+'" y="124" text-anchor="middle">'+name+'</text>';
  });
  const px=X(cur);
  svg+='<rect class="jm-pin '+(ready?'good':tone)+'" x="'+(px-45)+'" y="6" width="90" height="24" rx="12"/><path class="jm-pin-tip '+(ready?'good':tone)+'" d="M'+(px-7)+' 29 L'+px+' 40 L'+(px+7)+' 29 Z"/><text class="jm-pin-txt" x="'+px+'" y="23" text-anchor="middle">'+(ready?copy('جاهز','Ready'):copy('أنت هنا','You are here'))+'</text>';
  if(bad&&cur>0){const bx=X(cur-1);svg+='<path class="jm-back" d="M'+px+' 134 C'+px+' 164 '+bx+' 164 '+bx+' 140"/><path class="jm-back-head" d="M'+(bx-5)+' 148 L'+bx+' 138 L'+(bx+6)+' 147"/><text class="jm-note '+tone+'" x="'+((px+bx)/2)+'" y="188" text-anchor="middle">'+note+'</text>';}
  else if(note)svg+='<text class="jm-note '+(ready?'good':tone)+'" x="'+px+'" y="150" text-anchor="middle">'+note+'</text>';
  svg+='</svg>';
  return '<section class="qa-card qa-verdict qa-solo wf-card dev-map"><div class="verdict-top"><span class="eyebrow">'+copy('أين وصل طلبك','Where your request is')+'</span></div>'+svg+devLegend()+'</section>';
}

function devLegend(){
  const item=(cls,mark,text)=>'<li><i class="lg '+cls+'">'+mark+'</i><span>'+text+'</span></li>';
  return '<ul class="jm-legend">'
    +item('done','✓',copy('نجحت','Passed'))
    +item('now bad','✕',copy('فشلت','Failed'))
    +item('flag','⚑',copy('جاهز للإطلاق','Ready to release'))
    +'</ul>';
}

function devWhen(value){
  const ms=Date.now()-new Date(value).getTime();
  if(!(ms>=0))return '';
  const min=Math.floor(ms/60000),hour=Math.floor(min/60),day=Math.floor(hour/24);
  if(min<1)return copy('الحين','Just now');
  if(min<60)return copy('قبل '+min+' دقيقة',min+' min ago');
  if(hour<24)return copy('قبل '+hour+' ساعة',hour+' h ago');
  return copy('قبل '+day+' يوم',day+' d ago');
}

function devTimeline(){
  const stageName=s=>s==='security'?copy('الفحص الأمني','the security check'):copy('فحص الجودة','the quality check');
  const reviewer=s=>s==='security'?copy('مراجع الأمن','the security reviewer'):copy('مراجع الجودة','the QA reviewer');
  const line=e=>{const d=e.data||{};
    if(e.event==='event')return ['wait',d.event==='pull_request_opened'?copy('فتحتَ الطلب على GitHub','You opened the request on GitHub'):copy('رفعتَ تعديلًا جديدًا','You pushed a new change')];
    if(e.event==='policy_decision')return [d.result==='pass'?'good':'bad',(d.result==='pass'?copy('نجح ','Passed '):copy('فشل ','Failed '))+stageName(d.stage)];
    if(e.event==='human_decision')return [d.decision==='approve'?'good':'bad',(d.decision==='approve'?copy('وافق ','Approved by '):copy('أرجع ','Returned by '))+reviewer(d.stage)+(d.reason&&d.decision!=='approve'?': '+d.reason:'')];
    return null};
  const rows=[];let last='';
  (((release.log||{}).entries)||[]).forEach(e=>{const l=line(e);if(l&&l[1]!==last){rows.push({tone:l[0],text:l[1],time:e.time});last=l[1]}});
  if(!rows.length)return '';
  return '<ul class="tl">'+rows.slice(-4).reverse().map(r=>'<li class="'+r.tone+'"><i></i><div>'+safe(r.text)+'<small>'+devWhen(r.time)+'</small></div></li>').join('')+'</ul>';
}

/* no request yet: the journey map with every step still ahead, no "you are here" pin */
function devEmptyResult(){
  const names=[copy('فتح الطلب','Request opened'),copy('فحص الجودة','Quality check'),copy('موافقة الجودة','QA approval'),copy('الفحص الأمني','Security check'),copy('موافقة الأمن','Security approval'),copy('جاهز للإطلاق','Ready to release')];
  const rtl=document.documentElement.dir!=='ltr';
  const X=i=>rtl?520-i*96:40+i*96;
  let svg='<svg viewBox="0 0 560 150" class="jm" role="img" aria-label="'+copy('خريطة رحلة الطلب','Request journey map')+'"><title>'+copy('خريطة رحلة الطلب','Request journey map')+'</title>';
  svg+='<line class="jm-track" x1="'+X(0)+'" y1="78" x2="'+X(5)+'" y2="78"/>';
  names.forEach((name,i)=>{
    svg+='<circle class="jm-st todo" cx="'+X(i)+'" cy="78" r="14"/><text class="jm-mark" x="'+X(i)+'" y="83" text-anchor="middle">'+(i===5?'⚑':i+1)+'</text><text class="jm-name todo" x="'+X(i)+'" y="124" text-anchor="middle">'+name+'</text>';
  });
  svg+='</svg>';
  return '<section class="qa-card qa-verdict qa-solo wf-card dev-map"><div class="verdict-top"><span class="eyebrow">'+copy('أين وصل طلبك','Where your request is')+'</span></div>'+svg+devLegend()+'<p class="muted dev-empty-note">'+copy('لا توجد طلبات بعد. تظهر هنا رحلة طلبك لما ترفع أول تعديل.','No requests yet. Your request\'s journey appears here once you push your first change.')+'</p></section>';
}

function devZeroMetrics(){
  const z=(label,tone)=>metric(label,0,tone,[],'',safe);
  return '<div class="metric-row five">'+z(copy('مشكلات تحتاج إصلاحك','Problems to fix'),'')+z(copy('مشكلات انحلّت','Problems fixed'),'')+z(copy('مرات الفحص','Times checked'),'')+z(copy('طلبات أرجعها المراجع','Returned requests'),'')+z(copy('طلبات تنتظر المراجع','Requests in review'),'')+'</div>';
}

function devStageCard(key){
  const st=((release||{}).stages||{})[key]||{};
  const title=key==='qa'?copy('فحص الجودة','Quality check'):copy('الفحص الأمني','Security check');
  const state=!st.scanned?['wait',copy('لم يبدأ','Not started')]:st.result==='pass'?['good',copy('نجح','Passed')]:st.result==='fail'?['bad',copy('فشل','Failed')]:['wait',copy('قيد الفحص','Checking')];
  const found=(st.open||0)+(st.fixed||0);
  const sev=!st.scanned||!st.open?copy('لا يوجد','None'):(st.openHigh?copy('عالية '+st.openHigh,'High '+st.openHigh):'')+(st.openHigh&&st.openLow?' · ':'')+(st.openLow?copy('منخفضة '+st.openLow,'Low '+st.openLow):'');
  const num=(label,value,tone)=>'<div class="dev-num '+(tone||'')+'"><strong>'+value+'</strong><span>'+label+'</span></div>';
  return '<section class="qa-card dev-stage"><div class="dev-stage-head"><h3 class="card-title">'+title+'</h3><span class="pill '+state[0]+'">'+state[1]+'</span></div><div class="dev-nums three">'
    +num(key==='qa'?copy('اختبارات نجحت','Tests passed'):copy('ثغرات أُغلقت','Findings closed'),st.passed||0,st.passed?'good':'')
    +num(key==='qa'?copy('اختبارات فشلت','Tests failed'):copy('قيد التنفيذ','In progress'),st.open||0,st.open?'bad':'good')
    +num(copy('بانتظار موافقة','Awaiting approval'),(st.awaitingHuman?1:0),st.awaitingHuman?'wait':'')
    +'</div><p class="dev-sev">'+copy('الخطورة: ','Severity: ')+sev+'</p></section>';
}

function devReports(){
  const rep=release.reports||{},sec=(release.stages||{}).security||{};
  const tools=[['semgrep','Semgrep',copy('فحص الكود','Code scan'),'⌗'],['trivy','Trivy',copy('المكتبات والأسرار','Libraries and secrets'),'◫']].filter(t=>rep[t[0]]);
  const wait=!tools.length&&sec.scanned;
  if(!tools.length&&!wait)return '';
  const pending=[['semgrep','Semgrep',copy('فحص الكود','Code scan'),'⌗'],['trivy','Trivy',copy('المكتبات والأسرار','Libraries and secrets'),'◫']];
  if(wait)return '<section class="rep-section"><div class="rep-head"><h3 class="card-title">'+copy('نتائج أدوات الأمن السيبراني','Cybersecurity tool results')+'</h3><small>'+copy('التقرير يظهر هنا بعد أول فحص أمني جديد لهذا الطلب.','The report appears here after the next security check of this request.')+'</small></div><div class="dev-stages">'+pending.map(([id,name,what,icon])=>'<div class="qa-card rep-card"><span class="rep-ico">'+icon+'</span><div class="rep-body"><b>'+name+'</b><small>'+what+'</small></div></div>').join('')+'</div></section>';
  const cards=tools.map(([id,name,what,icon])=>{
    const m=rep[id],c=(sec.tools||{})[id]||{total:0,open:0};
    const kb=Math.max(1,Math.round((m.bytes||0)/1024));
    return '<div class="qa-card rep-card"><span class="rep-ico">'+icon+'</span><div class="rep-body"><b>'+name+'</b><small>'+what+' · '+copy(c.open+' من '+c.total+' قيد التنفيذ',c.open+' of '+c.total+' in progress')+'</small><small>'+mon(String(m.commit||'').slice(0,7))+' · '+kb+' KB</small></div>'
      +'<a class="action rep-dl" href="/api/releases/'+encodeURIComponent(release.id)+'/reports/'+id+'" download>'+copy('تنزيل التقرير','Download report')+'</a></div>';
  }).join('');
  return '<section class="rep-section"><div class="rep-head"><h3 class="card-title">'+copy('نتائج أدوات الأمن السيبراني','Cybersecurity tool results')+'</h3><small>'+copy('التقرير كما أصدرته الأداة نفسها، بدون تعديل.','The report exactly as the tool printed it, unchanged.')+'</small></div><div class="dev-stages">'+cards+'</div></section>';
}

function devBelowOld(){
  const d=devData();
  const [tone,title,text]=devNextStep(d);
  const problemRecord=f=>'<b>'+safe(findingName(f))+'</b> '+badge(severityName(f.severity),f.severity==='high'?'bad':'good')+'<br><small>'+safe(f.detail||'—')+'</small> '+action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"');
  const returned=(profile.releases||[]).filter(r=>r.returnReason);
  const inReview=(profile.releases||[]).filter(r=>qaGroup(r)==='review');
  const reqRecord=r=>safe(requestName(r.pr))+' '+action('queue',copy('فتح الطلب','Open request'),'data-id="'+safe(r.id)+'"');
  const metrics='<div class="metric-row five">'
    +metric(copy('مشكلات تحتاج إصلاحك','Problems to fix'),d.open.length,d.open.length?'bad':'',d.open,buildScope(copy('كل مشكلة مع دليلها وشرح يَقِـــظ.','Each problem with its evidence and the Yaqidh explanation.')),problemRecord)
    +metric(copy('مشكلات انحلّت','Problems fixed'),d.fixed.length,'good',d.fixed,buildScope(copy('مشكلات تأكّد النظام من إصلاحها.','Problems the system confirmed as fixed.')),problemRecord)
    +metric(copy('مرات الفحص','Times checked'),d.scans,'',[],buildScope(copy('كل رفع تعديل يعيد يَقِـــظ فحصه تلقائيًا.','Every push is re-checked automatically.')),safe)
    +metric(copy('طلبات أرجعها المراجع','Returned requests'),returned.length,returned.length?'bad':'',returned,copy('طلبات رجعت لك من المراجع.','Requests the reviewer sent back to you.'),reqRecord)
    +metric(copy('طلبات تنتظر المراجع','Requests in review'),inReview.length,inReview.length?'wait':'',inReview,copy('طلبات اختباراتها نجحت وتنتظر قرار المراجع.','Requests whose checks passed and wait for a reviewer.'),reqRecord)+'</div>';
  const next='<section class="qa-card next-step '+tone+'"><span class="eyebrow">'+copy('الخطوة التالية','Next step')+'</span><h3>'+title+'</h3><p>'+text+'</p></section>';
  const group=(titleText,list,kind,openIt)=>list.length?'<details class="req-group '+kind+'"'+(openIt?' open':'')+'><summary><span>'+titleText+'</span><b>'+list.length+'</b></summary><ul>'+list.map(f=>'<li class="req '+kind+'"><span class="req-id">'+safe(f.severity==='high'?copy('عالية','HIGH'):copy('منخفضة','LOW'))+'</span><span class="req-title">'+safe(findingName(f))+'<small>'+safe(f.detail||'')+'</small></span>'+action('finding',copy('التفاصيل','Details'),'data-id="'+safe(f.fingerprint)+'"')+'</li>').join('')+'</ul></details>':'';
  const problems=(d.open.length||d.fixed.length)?'<details class="qa-card qa-reqs-card"'+(d.open.length?' open':'')+'><summary><h3 class="card-title">'+copy('المشكلات والثغرات وشرحها','Findings and their explanation')+'</h3><span>'+(d.open.length+d.fixed.length)+' · '+copy('اضغطي للعرض','tap to view')+'</span></summary>'+group(copy('تحتاج إصلاحك','To fix'),d.open,'bad',true)+group(copy('انحلّت','Fixed'),d.fixed,'good',false)+'</details>':'';
  return problems;
}

function devBelow(){
  return '<div class="dev-stages">'+devStageCard('qa')+devStageCard('security')+'</div>'+devReports()+devFindingsDetail();
}

function devFindingsDetail(){
  const report=release&&release.report;
  if(!report)return devBelowOld();
  const s=report.summary;
  return report.findings.length?'<details class="catalog"'+(s.open_blocking?' open':'')+'><summary><b>'+copy('كل مشكلة أو ثغرة بالتفصيل','Every finding in detail')+'</b><span>'+report.findings.length+' '+copy('مشكلة · اضغط لتفتح القائمة','findings · click to open the list')+'</span></summary><div class="finding-cards">'+report.findings.map(reportCard).join('')+'</div></details>':'<p class="muted">'+copy('لا توجد مشكلات مسجلة.','No findings recorded.')+'</p>';
}
