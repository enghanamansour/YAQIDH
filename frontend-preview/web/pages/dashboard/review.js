function reviewQueue(){
  const rows=profile.releases.filter(item=>item.active===profile.role).slice().sort((a,b)=>Number(b.pendingReview)-Number(a.pendingReview)||Number(b.outcome==='fail')-Number(a.outcome==='fail'));
  return '<section class="panel"><div class="section-head"><h2>'+copy('قائمة المراجعة','Review queue')+'</h2><small>'+rows.filter(item=>item.pendingReview).length+' '+copy('بانتظار الموافقة','awaiting approval')+'</small></div>'
    +'<div class="actions">'+rows.map(item=>action('queue',safe(buildName(item.build))+' · '+(item.outcome==='fail'?copy('أخفق','Failed'):item.pendingReview?copy('ينتظر قرارك','Awaiting your decision'):item.outcome==='pass'?copy('اجتاز','Passed'):copy('بانتظار الفحص','Awaiting checks')),'data-id="'+safe(item.id)+'"')).join('')+'</div></section>';
}

function releaseHeader(){
  const options=profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+buildName(item.build)+' · '+requestName(item.pr)+'</option>').join('');
  return '<section class="intro"><div><h2>'+stageText(release.stage)+'</h2><small>'+safe(projectName(release.project))+' · '+safe(requestName(release.pr))+' · '+safe(buildName(release.build))+' · '+safe(branchName(release.branch))+' · '+mon(release.commit)+'</small></div>'
    +'<label class="field">'+copy('البناء المصرّح به','Authorized build')+'<select id="release-select">'+options+'</select></label></section>'
    +'<section class="panel actions" aria-label="'+copy('عينات المراجعة','Review samples')+'"><b>'+copy('جرّب حالة','Try a scenario')+'</b>'+action('sample-issue',profile.role==='qa'?copy('مشكلة جودة','QA issue'):copy('ثغرة مانعة','Blocking vulnerability'),'aria-pressed="'+(release.id===sampleBuild('issue'))+'"')+action('sample-ready',profile.role==='qa'?copy('جاهز لمراجعة الجودة','Ready for QA review'):copy('صفر ملاحظات · جاهز للمراجعة','Zero findings · ready for review'),'aria-pressed="'+(release.id===sampleBuild('ready'))+'"')+action('sample-approved',profile.role==='qa'?copy('موافقة جودة مسجّلة','QA approval recorded'):copy('جاهز للإطلاق · معتمد أمنيًا','Ready for release · approved'),'aria-pressed="'+(release.id===sampleBuild('approved'))+'"')+'</section>'
    +'<section class="summary '+(release.outcome?.result==='fail'?'bad':release.outcome?.result==='pass'?'good':'wait')+'"><div><b>'+copy('نتيجة محرك القواعد','Policy outcome')+' · '+outcomeText()+'</b><p>'
    +(release.outcome?.reasons.map(displayReason).join(' · ')||copy('تتوفر النتائج بعد اكتمال الفحوصات المطلوبة.','Results are available once required checks complete.'))+'</p></div>'
    +'<div><small>'+copy('القرار البشري','Human decision')+'</small><p>'+decisionText()+'</p></div></section>';
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

function reviewView(){
  if(!release)return '<section class="panel">'+copy('لا يوجد بناء في نطاق الحساب','No builds in this account scope')+'</section>';
  const open=matched().filter(f=>findingGroup(f)==='open');
  const blockers=release.findings.filter(f=>(release.blockerIds||[]).includes(f.fingerprint));
  const closed=matched().filter(f=>f.closure?.result==='closed');
  const visibleRuns=release.runs.filter(r=>(tool==='all'||r.tool===tool)&&(runFilter==='all'||r.state===runFilter));
  const completed=visibleRuns.filter(r=>r.state==='completed');
  const unread=threads.filter(thread=>thread.release===release.id&&thread.unread);

  return reviewQueue()+releaseHeader()
    +'<div class="metric-row">'+(profile.role==='security'?metric(copy('ملاحظات مانعة','Blocking findings'),release.outcome?blockers.length:'—',blockers.length?'bad':'',blockers,buildScope(release.outcome?.reasons.map(displayReason).join(' · ')||copy('بانتظار نتيجة محرك القواعد.','Awaiting a policy outcome.')),findingRecord):metric(copy('ملاحظات تنتظر إعادة الفحص','Findings awaiting recheck'),open.length,open.length?'wait':'',open,buildScope(copy('الملاحظات المطابقة التي تحتاج متابعة.','Matching findings that need follow-up.')),findingRecord))
    +metric(copy('إغلاقات مثبتة','Verified closures'),closed.length,'good',closed,buildScope(copy('الإغلاقات المثبتة ضمن الفلاتر الحالية.','Verified closures within active filters.')),findingRecord)
    +metric(copy('تشغيلات مكتملة في السجل','Completed recorded runs'),visibleRuns.length?fraction(completed.length,visibleRuns.length):'—','',visibleRuns,buildScope(copy('المكتمل من التشغيلات المطابقة للأداة وحالة التشغيل.','Completed runs out of those matching tool and run-state filters.')),runRecord)
    +metric(copy('محادثات تنتظر الاطلاع','Unread conversations'),unread.length,'',unread,buildScope(copy('المحادثات غير المقروءة لهذا البناء.','Unread conversations for this build.')),thread=>'<a href="/communication?thread='+encodeURIComponent(thread.id)+'">'+safe(threadText(thread.subject))+'</a>')+'</div>'
    +'<section class="panel"><div class="section-head"><h2>'+copy('أدلة المرحلة والإجراءات','Stage evidence and actions')+'</h2><div class="actions">'
    +(profile.role==='qa'?action('new-thread',copy('فتح نقاش','Start discussion')):'')+action('runs',copy('سجل تشغيل الأدوات','Tool runs'))+action('evidence',copy('ملف الأدلة','Evidence'))+action('decisions',copy('سجل القرارات','Decision log'))
    +(profile.role==='security'?action('previous-qa',copy('موافقة الجودة السابقة','Previous QA approval')):'')+(release.prior?action('prior',copy('البناء السابق','Previous build')):'')
    +(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')
    +(release.canApprove?action('approve',profile.role==='security'?copy('اعتماد البناء','Approve build'):copy('تسجيل الموافقة','Record approval'),'class="primary"'):'')
    +'</div></div></section>'+findingsView()+'<section class="panel"><h2>'+copy('اتجاه النتائج عبر الزمن','Results over time')+'</h2><p class="muted">'+copy('لا يتوفر سجل أحداث مؤرخ كافٍ لرسم الاتجاه.','There is not enough dated event history to plot a trend.')+'</p></section>';
}
