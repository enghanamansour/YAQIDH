let reviewBuildFilter='all';

function reviewBuilds(filter=reviewBuildFilter){
  return profile.releases.filter(item=>(profile.role==='security'||item.outcome==='pass')
    &&(filter==='all'||(filter==='pending'&&item.pendingReview)
      ||(filter==='failed'&&item.outcome==='fail')||(filter==='reviewed'&&item.reviewed)));
}

function reviewBuildOptions(rows){
  return rows.map(item=>{
    const label=copy('طلب الدمج','Pull request')+' #'+item.pr+' · '+copy(item.outcome?'النسخة المفحوصة':'النسخة','Build')+' #'+item.build;
    return '<option value="'+safe(item.id)+'" '+(item.id===release?.id?'selected':'')+'>'+safe(label)+'</option>';
  }).join('');
}

function reviewBuildPicker(){
  const rows=reviewBuilds();
  const pending=reviewBuilds('pending').length;
  const filters=[['all',copy('الكل','All')],['pending',copy('بانتظار قرارك','Awaiting your decision')+' ('+pending+')'],
    ...(profile.role==='security'?[['failed',copy('أخفق الفحص','Failed checks')]]:[]),['reviewed',copy('تمت المراجعة','Reviewed')]];
  return '<section class="panel review-build-filters"><h2>'+copy('فلاتر المراجعة','Review filters')+'</h2><h3>'+copy('النسخة للمراجعة','Build to review')+'</h3><div class="qa-review-selection">'
    +'<div class="actions" role="group" aria-label="'+copy('فلتر المراجعة','Review filter')+'">'
    +filters.map(([id,label])=>action('review-build-filter',label,'data-id="'+id+'" aria-pressed="'+(id===reviewBuildFilter)+'"')).join('')+'</div>'
    +'<label class="field qa-review-build-picker">'+copy('النسخة','Build')+'<select id="release-select"'+(rows.length?'':' disabled')+'>'
    +(rows.some(item=>item.id===release?.id)?'':'<option value="" selected disabled>'+copy('اختر نسخة','Select a build')+'</option>')
    +reviewBuildOptions(rows)+'</select></label></div>'
    +(!rows.length?'<p class="muted">'+(reviewBuildFilter==='pending'?copy('لا توجد نسخ بانتظار قرارك','No builds awaiting your decision'):copy('لا توجد نسخ مطابقة لهذا الفلتر','No builds match this filter'))+'</p>':'')
    +'</section>';
}

function reviewSamples(){
  return '<section class="panel actions" aria-label="'+copy('عينات المراجعة','Review samples')+'"><b>'+copy('جرّب حالة','Try a scenario')+'</b>'+action('sample-issue',copy('ثغرة مانعة','Blocking vulnerability'),'aria-pressed="'+(release.id===sampleBuild('issue'))+'"')+action('sample-ready',copy('صفر ملاحظات · جاهز للمراجعة','Zero findings · ready for review'),'aria-pressed="'+(release.id===sampleBuild('ready'))+'"')+action('sample-approved',copy('جاهز للإطلاق · معتمد أمنيًا','Ready for release · approved'),'aria-pressed="'+(release.id===sampleBuild('approved'))+'"')+'</section>';
}

function releaseHeader(){
  const details='<details class="review-build-details"><summary>'+copy('تفاصيل النسخة','Build details')+'</summary><div class="details-grid">'
    +detail(copy('المشروع','Project'),safe(projectName(release.project)))
    +detail(copy('الفرع','Branch'),safe(branchName(release.branch)))
    +detail(copy('معرّف التعديل','Commit'),mon(release.commit))+'</div></details>';
  return '<section class="summary '+(release.outcome?.result==='fail'?'bad':release.outcome?.result==='pass'?'good':'wait')+'"><div>'+'<h2 class="'+roleColor(release.stage)+'">'+stageText(release.stage)+'</h2>'+'<b>'+copy('نتيجة محرك القواعد','Policy outcome')+' · '+outcomeText()+'</b><p>'
    +(release.outcome?.reasons.map(displayReason).join(' · ')||copy('تتوفر النتائج بعد اكتمال الفحوصات المطلوبة.','Results are available once required checks complete.'))+'</p>'+details+'</div>'
    +'<div><small>'+copy('القرار البشري','Human decision')+'</small><p>'+decisionText()+'</p>'+reviewDecisionActions()+'</div></section>';
}

function reviewEvidenceFilters(){
  const sources=[...new Set([...release.runs.map(r=>r.tool),...release.findings.map(f=>f.tool)])];
  const options=sources.map(id=>'<option class="'+toolColor(id)+'" value="'+safe(id)+'" '+(tool===id?'selected':'')+'>'+safe(toolName(id))+'</option>').join('');
  const isQA=profile.role==='qa';
  return '<section class="panel review-evidence-filters"><h2>'+copy('أدلة النسخة المحددة','Selected build evidence')+'</h2><div class="filters">'
    +'<label>'+copy('أداة الفحص','Scan tool')+'<select id="tool-filter" class="'+toolColor(tool)+'"><option value="all">'+copy('جميع الأدوات','All tools')+'</option>'+options+'</select></label>'
    +'<label>'+copy('خطورة الملاحظة','Finding severity')+'<select id="severity-filter"><option value="all">'+copy('جميع التصنيفات','All severities')+'</option>'
    +['high','low'].map(id=>'<option value="'+id+'" '+(id===severity?'selected':'')+'>'+severityName(id)+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',findingLabel('open')],['fixed',copy('مغلقة','Closed')],['excepted',copy('مستثناة','Excepted')]])
     +(isQA?'':adminSelect('run-filter',copy('حالة التشغيل','Run state'),runFilter,stateLabels()))+'</div>'+chipRow([['tool',tool,toolName(tool)],['severity',severity,severityName(severity)],['finding',findingFilter,findingFilter==='all'?'':findingLabel(findingFilter)],...(isQA?[]:[['run',runFilter,statusText(runFilter)]])],'clear')+'</section>';
}

function findingsView(){
  const rows=matched(), high=rows.filter(f=>f.severity==='high').length, low=rows.length-high;
  const records=rows.map(f=>'<tr><td>'+safe(findingName(f))+'<br><small>'+safe(f.location)+'</small></td><td>'+toolLabel(f.tool)+'</td><td>'+badge(severityName(f.severity),f.severity==='high'?'bad':'good')+'</td><td>'+safe(findingState(f))+'</td><td>'
    +action('finding',copy('الدليل','Evidence'),'data-id="'+safe(f.fingerprint)+'"')+'</td></tr>').join('');
  const table='<section class="panel"><h2>'+copy('الملاحظات المطابقة','Matching findings')+' · '+rows.length+'</h2>'
    +(records?'<div class="table-wrap"><table><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الأداة','Tool')+'</th><th>'+copy('الخطورة','Severity')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('التفاصيل','Details')+'</th></tr></thead><tbody>'+records+'</tbody></table></div>':'<p class="muted">'+copy('لا توجد ملاحظات مطابقة في السجل المعروض.','No matching findings in this record.')+'</p>')+'</section>';
  const severityChart='<section class="panel"><h2>'+copy('الملاحظات حسب الخطورة','Findings by severity')+'</h2>'
    +[['high',high],['low',low]].map(([id,count])=>'<div class="bar-row '+(id==='high'?'bad':'good')+'"><span>'+action('bar',severityName(id),'data-id="'+id+'" aria-pressed="'+(severity===id)+'"')+'<b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(rows.length,1)+'"></progress></div>').join('')+'</section>';
  return {table,severityChart};
}

function qaReviewAlerts(records){
  return records.length?records.map(item=>'<article class="note"><b>'
    +(item.kind==='exception'?copy('اعتمد الأمن استثناءً','Security approved an exception'):copy('اعتمد الأمن تمديد المهلة','Security approved an extension'))
    +'</b><p>'+safe(buildName(item.build))+' · '+mon(item.commit)+' · '+safe(accountName(item.by))+'</p>'
    +'<p>'+(item.approvedDeadline?copy('الموعد الجديد المعتمد','Approved new deadline')+' '+displayReviewDeadline(item.approvedDeadline)
      :copy('لا يوجد موعد جديد معتمد لهذه الملاحظة.','No new deadline has been approved for this finding.'))+'</p></article>').join('')
    :'<p>'+copy('لا توجد تنبيهات من الأمن السيبراني.','No security decision alerts.')+'</p>';
}

function qaReviewAlertsPanel(){
  return '<section class="panel qa-alerts" aria-label="'+copy('تنبيهات قرارات الأمن السيبراني','Security decision alerts')+'"><h2>'+copy('تنبيهات قرارات الأمن السيبراني','Security decision alerts')+'</h2><div id="qa-review-alerts" aria-live="polite">'+qaReviewAlerts(profile.reviewAlerts)+'</div></section>';
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

function reviewDecisionActions(){
  const reject=release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'';
  const approve=release.canApprove?action('approve',profile.role==='security'?copy('اعتماد البناء','Approve build'):copy('تسجيل الموافقة','Record approval'),'class="primary"'):'';
  return reject||approve?'<div class="actions">'+approve+reject+'</div>':'';
}

function reviewView(){
  const isQA=profile.role==='qa';
  const picker=reviewBuildPicker();
  if(!reviewBuilds().some(item=>item.id===release?.id))return picker+(isQA?qaReviewAlertsPanel():'');
  const open=matched().filter(f=>findingGroup(f)==='open');
  const blockers=release.findings.filter(f=>(release.blockerIds||[]).includes(f.fingerprint));
  const closed=matched().filter(f=>f.closure?.result==='closed');
  const visibleRuns=release.runs.filter(r=>(tool==='all'||r.tool===tool)&&(runFilter==='all'||r.state===runFilter));
  const completed=visibleRuns.filter(r=>r.state==='completed');
  const unread=threads.filter(thread=>thread.release===release.id&&thread.unread);

  const pendingRequests=profile.role==='security'?threads.filter(thread=>thread.release===release.id
    && (thread.exceptionRequest||thread.deadline)?.status==='pending'):[];
  const reviewLinks=pendingRequests.map(thread=>'<a class="action" href="/communication?thread='+encodeURIComponent(thread.id)+'">'
    +(thread.exceptionRequest?copy('مراجعة طلب استثناء','Review exception request'):copy('مراجعة طلب تمديد','Review extension request'))+'</a>').join('');
  const {table,severityChart}=findingsView();
  const metrics='<div class="metric-row">'+(profile.role==='security'?metric(copy('ملاحظات مانعة','Blocking findings'),release.outcome?blockers.length:'—',blockers.length?'bad':'',blockers,buildScope(release.outcome?.reasons.map(displayReason).join(' · ')||copy('بانتظار نتيجة محرك القواعد.','Awaiting a policy outcome.')),findingRecord):metric(copy('ملاحظات تحتاج متابعة','Findings needing follow-up'),open.length,open.length?'wait':'',open,buildScope(copy('الملاحظات المطابقة التي تحتاج متابعة.','Matching findings that need follow-up.')),findingRecord))
    +metric(copy('إغلاقات مثبتة','Verified closures'),closed.length,'good',closed,buildScope(copy('الإغلاقات المثبتة ضمن الفلاتر الحالية.','Verified closures within active filters.')),findingRecord)
    +metric(copy('تشغيلات مكتملة في السجل','Completed recorded runs'),visibleRuns.length?fraction(completed.length,visibleRuns.length):'—','',visibleRuns,buildScope(isQA?copy('المكتمل من تشغيلات أداة الفحص المحددة.','Completed runs for the selected scan tool.'):copy('المكتمل من التشغيلات المطابقة للأداة وحالة التشغيل.','Completed runs out of those matching tool and run-state filters.')),runRecord)
    +metric(copy('محادثات تنتظر الاطلاع','Unread conversations'),unread.length,'',unread,buildScope(copy('المحادثات غير المقروءة لهذا البناء.','Unread conversations for this build.')),thread=>'<a href="/communication?thread='+encodeURIComponent(thread.id)+'">'+safe(threadText(thread.subject))+'</a>')+'</div>';
  const evidenceActions='<section class="panel"><div class="section-head"><h2>'+copy('أدلة المرحلة والإجراءات','Stage evidence and actions')+'</h2><div class="actions">'
    +(profile.role==='qa'?action('new-thread',copy('فتح نقاش','Start discussion')):'')+action('runs',copy('سجل تشغيل الأدوات','Tool runs'))+action('evidence',copy('ملف الأدلة','Evidence'))+action('decisions',copy('سجل القرارات','Decision log'))
    +(profile.role==='security'?action('previous-qa',copy('موافقة الجودة السابقة','Previous QA approval')):'')+(release.prior?action('prior',copy('البناء السابق','Previous build')):'')
     +reviewLinks+'</div></div></section>';
  const supplementary=isQA?qaReviewAlertsPanel():reviewSamples()
    +'<section class="panel"><h2>'+copy('اتجاه النتائج عبر الزمن','Results over time')+'</h2><p class="muted">'+copy('لا يتوفر سجل أحداث مؤرخ كافٍ لرسم الاتجاه.','There is not enough dated event history to plot a trend.')+'</p></section>';
  return picker+releaseHeader()+reviewEvidenceFilters()+table+evidenceActions
    +metrics+stageCharts()+severityChart+supplementary;
}
