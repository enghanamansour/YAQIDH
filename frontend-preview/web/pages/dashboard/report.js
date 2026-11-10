/* The developer's report on one release: findings, severity, rounds and how long each took to close.
   The numbers come from the Yaqidh API (GET /releases/{id}/report): plain code over the evidence and the history. */

function reportTime(sec){
  if(sec===null||sec===undefined)return '—';
  if(sec<60)return sec+' '+copy('ثانية','s');
  if(sec<3600)return Math.round(sec/60)+' '+copy('دقيقة','min');
  if(sec<172800)return (sec/3600).toFixed(1)+' '+copy('ساعة','h');
  return (sec/86400).toFixed(1)+' '+copy('يوم','d');
}

function reportDate(value){
  if(!value)return '—';
  return new Date(value).toLocaleString(document.documentElement.lang==='en'?'en-GB':'ar-SA-u-nu-latn',{dateStyle:'short',timeStyle:'short'});
}

const reportStage=stage=>stage==='qa'?copy('الجودة','QA'):copy('الأمن','Security');
const reportSeverity=level=>level==='high'?'<span class="badge" style="color:var(--bad)">'+copy('عالية','High')+'</span>':'<span class="badge" style="color:var(--wait)">'+copy('منخفضة','Low')+'</span>';
const reportLevel=name=>({critical:copy('حرجة','Critical'),high:copy('عالية','High'),medium:copy('متوسطة','Medium'),low:copy('منخفضة','Low'),unknown:copy('غير محددة','Unrated')})[name]||name;
function reportDistribution(report){
  const s=report.summary,order=['critical','high','medium','low','unknown'],byLevel=s.by_reported||{};
  const levels=order.filter(k=>byLevel[k]).map(k=>'<li>'+safe(reportLevel(k))+': <b>'+byLevel[k]+'</b> ('+Math.round(100*byLevel[k]/s.findings)+'%)</li>').join('');
  const tools=Object.entries(s.by_tool||{}).map(([k,v])=>'<li>'+safe(toolName?toolName(k):k)+': <b>'+v+'</b></li>').join('');
  const owasp=Object.entries(s.by_owasp||{}).filter(([k])=>k!=='none').map(([k,v])=>'<li>'+safe(k)+': <b>'+v+'</b></li>').join('');
  return '<div class="report-dist"><div><h3>'+copy('حسب خطورة الأداة','By tool rating')+'</h3><ul class="metric-records">'+levels+'</ul></div><div><h3>'+copy('حسب الأداة','By tool')+'</h3><ul class="metric-records">'+tools+'</ul></div><div><h3>OWASP Top 10</h3><ul class="metric-records">'+(owasp||'<li class="muted">—</li>')+'</ul></div></div>';
}
const reportStatus=row=>row.status==='open'?copy('مفتوحة','Open'):row.status==='excepted'?copy('مستثناة','Excepted'):copy('مغلقة بإثبات','Closed, verified');
const reportNotes={
  elapsed_time:()=>copy('الزمن هو المدة المنقضية بين الفحوصات وتشمل الانتظار، وليس جهد المطوّر.','Time is the elapsed time between scans and includes waiting; it is not the developer’s working time.'),
  scan_resolution:()=>copy('دقة الزمن بحجم الفترة بين فحصين.','Precision equals the gap between two scans.'),
  low_awareness:()=>copy('الملاحظات المنخفضة لا تمنع الدمج، لكنها تُسجَّل وتظهر هنا. «منخفضة» لا تعني «بلا ضرر»: اقرأها وقرر إصلاحها لاحقًا.','Low findings do not block the merge, but they are recorded and shown here. “Low” does not mean “harmless”: read them and plan a fix.'),
  severity_source:()=>copy('الخطورة تأتي من تصنيف الأداة نفسها (حرجة وعالية ومتوسطة ومنخفضة). يقظ يحوّل الحرجة والعالية والمتوسطة إلى «مانعة»، ولا يمرر إلا المنخفضة الصريحة. مرجع التصنيف في CVSS: منخفضة 0.1–3.9، متوسطة 4.0–6.9، عالية 7.0–8.9، حرجة 9.0–10.','Severity comes from the tool’s own rating (critical, high, medium, low). Yaqidh treats critical, high and medium as blocking and lets only an explicit low through. The CVSS bands: low 0.1–3.9, medium 4.0–6.9, high 7.0–8.9, critical 9.0–10.'),
  owasp_source:()=>copy('تصنيف OWASP Top 10 (2021) يُستنتج من رقم CWE بجدول ثابت، ومكتبات الطرف الثالث تُصنَّف «مكونات ضعيفة أو قديمة». الملاحظة بلا CWE معروف تظهر بلا تصنيف.','The OWASP Top 10 (2021) category is taken from the CWE with a fixed table; third-party library findings are “Vulnerable and Outdated Components”. A finding without a known CWE shows no category.'),
  db_origin:()=>copy('الملاحظات الناتجة عن تحديث قاعدة بيانات الثغرات تظهر معلَّمة، ولا تُنسب للمطوّر.','Findings caused by a vulnerability database update are marked and not attributed to the developer.')
};

const reportNames=[
  ['errors_do_not_leak_internals',()=>copy('صفحة الخطأ تكشف تفاصيل داخلية','The error page leaks internals')],
  ['search_resists_sql_injection',()=>copy('حقل البحث يقبل حقن SQL','The search box allows SQL injection')],
  ['unescaped-template-extension',()=>copy('قالب بدون تعقيم للمدخلات','Template without input escaping')],
  ['django-no-csrf-token',()=>copy('نموذج بدون حماية CSRF','Form without CSRF protection')],
  ['debug-enabled',()=>copy('وضع التطوير (debug) شغّال','Debug mode is on')],
  ['github-pat',()=>copy('مفتاح GitHub مكشوف في الكود','GitHub token exposed in the code')],
  ['secret-scan',()=>copy('سر مكتوب داخل الكود','A secret written in the code')]
];
function reportName(row){
  const hit=reportNames.find(([key])=>String(row.rule).includes(key));
  const base=hit?hit[1]():String(row.rule).split('.').pop();
  return row.component?base+' · '+row.component:base;
}
const reportPlace=row=>String(row.location||'').startsWith('qa_checks/')?'':'<br><small>'+mon(row.location)+'</small>';

function reportTile(label,value,tone,note){
  return '<div class="metric report-tile '+tone+'"><strong>'+safe(value)+'</strong><span>'+label+'</span>'+(note?'<small>'+safe(note)+'</small>':'')+'</div>';
}

/* Where the build is, in five steps, and one sentence saying what it needs. */
const reportSteps=()=>[copy('فحص الجودة','QA scan'),copy('موافقة الجودة','QA approval'),copy('فحص الأمن','Security scan'),copy('موافقة الأمن','Security approval'),copy('جاهز للدمج','Ready to merge')];
const reportWhere={
  not_started:[0,'bad'],qa_blocked:[0,'bad'],qa_rejected:[0,'bad'],awaiting_qa_approval:[1,'wait'],
  awaiting_security_scan:[2,'wait'],security_blocked:[2,'bad'],security_rejected:[2,'bad'],awaiting_security_approval:[3,'wait'],ready_to_merge:[4,'good']
};
const reportSentence={
  not_started:()=>copy('لم يبدأ الفحص بعد.','Checking has not started yet.'),
  qa_blocked:()=>copy('فحص الجودة وجد ملاحظات تمنع الدمج. أصلحها وارفع تعديلاً جديداً.','The QA scan found blocking findings. Fix them and push a new change.'),
  qa_rejected:()=>copy('أرجع فريق الجودة البناء. اقرأ السبب وأصلح ثم ارفع تعديلاً.','The QA team returned the build. Read the reason, fix it and push again.'),
  awaiting_qa_approval:()=>copy('اجتاز فحص الجودة، وينتظر موافقة فريق الجودة.','It passed the QA scan and waits for the QA team.'),
  awaiting_security_scan:()=>copy('ينتظر فحص الأمن.','Waiting for the security scan.'),
  security_blocked:()=>copy('فحص الأمن وجد ملاحظات تمنع الدمج. أصلحها وارفع تعديلاً جديداً.','The security scan found blocking findings. Fix them and push a new change.'),
  security_rejected:()=>copy('أرجع فريق الأمن البناء. اقرأ السبب وأصلح ثم ارفع تعديلاً.','The security team returned the build. Read the reason, fix it and push again.'),
  awaiting_security_approval:()=>copy('اجتاز فحص الأمن، وينتظر موافقة فريق الأمن.','It passed the security scan and waits for the security team.'),
  ready_to_merge:()=>copy('كل شيء مكتمل. البناء جاهز للدمج.','Everything is done. The build is ready to merge.')
};

function reportStepper(report){
  const key=report.status.status,pair=reportWhere[key]||[0,'wait'],now=pair[0],tone=pair[1],finished=key==='ready_to_merge';
  const nodes=reportSteps().map((name,i)=>'<li class="step '+(i<now||finished?'done':i===now?'now '+tone:'')+'"><i>'+(i<now||finished?'✓':i+1)+'</i><span>'+name+'</span></li>').join('');
  const say=(reportSentence[key]||(()=>''))();
  return '<ol class="stepper">'+nodes+'</ol><p class="sentence '+tone+'">'+safe(say)+'</p>';
}

function reportBar(s){
  if(!s.findings)return '';
  const open=s.open_blocking+s.open_low,parts=[[s.closed,'good',copy('مغلقة','Closed')],[open,'bad',copy('مفتوحة','Open')],[s.excepted,'wait',copy('مستثناة','Excepted')]];
  let x=0;
  const rects=parts.filter(p=>p[0]).map(p=>{const w=100*p[0]/s.findings,r='<rect class="'+p[1]+'" x="'+x.toFixed(2)+'" width="'+w.toFixed(2)+'" height="10"><title>'+safe(p[2]+': '+p[0])+'</title></rect>';x+=w;return r}).join('');
  return '<svg class="stack" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="'+safe(copy('توزيع الملاحظات','Findings split'))+'"><rect class="track" width="100" height="10"/>'+rects+'</svg>'
    +'<div class="legend">'+parts.map(p=>'<span class="'+p[1]+'">'+p[2]+' <b>'+p[0]+'</b></span>').join('')+'</div>';
}

function reportRow(row){
  const tip=[row.owasp,reportStage(row.stage),reportDate(row.first_seen)].filter(Boolean).join(' · ');
  const time=row.closed_at?reportTime(row.seconds_to_close):row.seconds_open!==null?reportTime(row.seconds_open)+' · '+copy('مفتوحة','open'):'—';
  return '<tr title="'+safe(tip)+'"><td>'+safe(reportName(row))+reportPlace(row)+'</td><td>'+reportSeverity(row.severity)+'</td><td>'+safe(reportStatus(row))+'</td><td>'+safe(time)+'</td></tr>';
}

function developerReport(){
  const report=release&&release.report;
  const title='<h2>'+copy('تقرير البناء','Build report')+'</h2>';
  if(!report)return '<section class="panel">'+title+'<p class="muted">'+copy('يظهر التقرير عند تشغيل اللوحة على واجهة يقظ الحية.','The report appears when the dashboard runs against the live Yaqidh API.')+'</p></section>';
  const s=report.summary,avg=s.time_to_close.average_seconds;
  const head='<div class="section-head"><div>'+title+'<small>'+safe(requestName(release.pr))+' · '+mon((report.head_commit||'').slice(0,8))+'</small></div></div>';
  const tiles='<div class="metric-row">'
    +reportTile(copy('ملاحظات وُجدت','Findings found'),s.findings,'')
    +reportTile(copy('مغلقة بإثبات','Closed, proven'),s.closed,'good',s.closed_percent==null?'':s.closed_percent+'%')
    +reportTile(copy('تمنع الدمج الآن','Blocking now'),s.open_blocking,s.open_blocking?'bad':'good')
    +reportTile(copy('متوسط زمن الإغلاق','Average time to close'),reportTime(avg),'wait',s.time_to_close.count?copy('الأطول: ','longest: ')+reportTime(s.time_to_close.max_seconds):copy('لا إغلاقات بعد','nothing closed yet'))
    +'</div>';
  const blockers=report.findings.filter(r=>r.status==='open'&&r.severity==='high');
  const blocking=blockers.length?'<div class="blockers"><h3>'+copy('وش يمنع الدمج؟','What blocks the merge?')+'</h3><ul>'
    +blockers.slice(0,6).map(r=>'<li>'+safe(reportName(r))+reportPlace(r).replace('<br>',' ')+'</li>').join('')
    +(blockers.length>6?'<li class="muted">+ '+(blockers.length-6)+' '+copy('أخرى','more')+'</li>':'')+'</ul></div>':'';
  const rows=report.findings.map(reportRow).join('');
  const table=rows?'<div class="table-wrap"><table class="report-table"><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الخطورة','Severity')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الزمن','Time')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p class="muted">'+copy('لا توجد ملاحظات مسجلة.','No findings recorded.')+'</p>';
  const decided=report.approvals.length?report.approvals.map(item=>safe(reportStage(item.stage))+': '+(item.decision==='approve'?copy('وافق','approved'):copy('أرجع','returned'))+' · '+safe(item.by)).join(' · '):copy('لا قرارات بشرية بعد','No human decisions yet');
  const waits=s.approval_waits.map(item=>safe(reportStage(item.stage))+': '+safe(reportTime(item.seconds))).join(' · ');
  const notes=report.notes.map(code=>reportNotes[code]?reportNotes[code]():'').filter(Boolean).map(text=>'<li>'+safe(text)+'</li>').join('');
  const more='<details class="more-details"><summary>'+copy('كيف تُحسب هذه الأرقام؟ وتفاصيل التصنيف','How are these numbers worked out? Classification details')+'</summary>'
    +(s.findings?reportDistribution(report):'')+(waits?'<p class="muted">'+copy('انتظار الموافقة بعد نجاح الفحص: ','Wait for approval after a passing scan: ')+waits+'</p>':'')+'<ul class="report-notes">'+notes+'</ul></details>';
  return '<section class="panel report">'+head+reportStepper(report)+tiles+reportBar(s)+blocking+table+'<p class="muted decided">'+decided+'</p>'+more+'</section>';
}
