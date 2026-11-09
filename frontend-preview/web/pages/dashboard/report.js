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
  const s=report.summary,order=['critical','high','medium','low','unknown'];
  const levels=order.filter(k=>s.by_reported[k]).map(k=>'<li>'+safe(reportLevel(k))+': <b>'+s.by_reported[k]+'</b> ('+Math.round(100*s.by_reported[k]/s.findings)+'%)</li>').join('');
  const tools=Object.entries(s.by_tool).map(([k,v])=>'<li>'+safe(toolName?toolName(k):k)+': <b>'+v+'</b></li>').join('');
  const owasp=Object.entries(s.by_owasp).filter(([k])=>k!=='none').map(([k,v])=>'<li>'+safe(k)+': <b>'+v+'</b></li>').join('');
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

function reportTile(label,value,tone,note){
  return '<div class="metric report-tile '+tone+'"><strong>'+safe(value)+'</strong><span>'+label+'</span>'+(note?'<small>'+safe(note)+'</small>':'')+'</div>';
}

function reportRow(row){
  const name=row.component?row.rule+' · '+row.component:String(row.rule).split('.').pop();
  const origin=row.origin==='new_from_db_update'?' <span class="badge">'+copy('من تحديث قاعدة البيانات','From a database update')+'</span>':'';
  return '<tr><td>'+safe(name)+origin+'<br><small>'+mon(row.location)+' · '+safe(reportStage(row.stage))+'</small></td><td>'+reportSeverity(row.severity)+(row.reported_as?'<br><small>'+safe(reportLevel(String(row.reported_as).toLowerCase()))+'</small>':'')+'</td><td><small>'+safe(row.owasp||'—')+'</small></td><td>'+safe(reportStatus(row))+'</td>'
    +'<td>'+safe(reportDate(row.first_seen))+'</td><td>'+safe(reportDate(row.closed_at))+'</td>'
    +'<td>'+safe(row.closed_at?reportTime(row.seconds_to_close):reportTime(row.seconds_open)+(row.seconds_open!==null?' · '+copy('ما زالت مفتوحة','still open'):''))+'</td><td>'+safe(row.rounds)+'</td></tr>';
}

function developerReport(){
  const report=release&&release.report;
  const title='<h2>'+copy('تقرير المطوّر','Developer report')+'</h2>';
  if(!report)return '<section class="panel">'+title+'<p class="muted">'+copy('يظهر التقرير عند تشغيل اللوحة على واجهة يقظ الحية.','The report appears when the dashboard runs against the live Yaqidh API.')+'</p></section>';
  const s=report.summary;
  const avg=s.time_to_close.average_seconds;
  const tiles='<div class="metric-row">'
    +reportTile(copy('ملاحظات مانعة مفتوحة','Open blocking findings'),s.open_blocking,s.open_blocking?'bad':'good',copy('من إجمالي ','of ')+s.findings)
    +reportTile(copy('إغلاقات مثبتة بإعادة الفحص','Closed, proven by a re-scan'),s.closed,'good',s.excepted?copy('مستثناة: ','excepted: ')+s.excepted:'')
    +reportTile(copy('متوسط زمن الإغلاق','Average time to close'),reportTime(avg),'wait',s.time_to_close.count?copy('الأطول: ','longest: ')+reportTime(s.time_to_close.max_seconds):copy('لا إغلاقات بعد','nothing closed yet'))
    +reportTile(copy('نسبة الإغلاق','Closed share'),s.closed_percent===null?'—':s.closed_percent+'%','good',copy('مفتوحة: ','still open: ')+(s.open_blocking+s.open_low))
    +reportTile(copy('منخفضة تمر بتوعية','Low, passes with awareness'),s.open_low,'wait',copy('تمر ولا تُنسى','passes, not forgotten'))
    +reportTile(copy('جولات الفحص','Scan rounds'),s.rounds.qa+' / '+s.rounds.security,'',copy('الجودة / الأمن','QA / Security'))
    +'</div>';
  const rows=report.findings.map(reportRow).join('');
  const table=rows?'<div class="table-wrap"><table class="report-table"><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الخطورة','Severity')+'</th><th>OWASP</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('أول ظهور','First seen')+'</th><th>'+copy('الإغلاق','Closed')+'</th><th>'+copy('الزمن','Time')+'</th><th>'+copy('الجولات','Rounds')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p class="muted">'+copy('لا توجد ملاحظات مسجلة.','No findings recorded.')+'</p>';
  const approvals=report.approvals.length?'<ul class="metric-records">'+report.approvals.map(item=>'<li>'+safe(reportStage(item.stage))+' · '+(item.decision==='approve'?copy('موافقة','Approved'):copy('إرجاع','Returned'))+' · '+safe(item.by)+' · '+safe(reportDate(item.at))+(item.reason?' · '+safe(item.reason):'')+'</li>').join('')+'</ul>':'<p class="muted">'+copy('لا توجد قرارات بشرية بعد.','No human decisions yet.')+'</p>';
  const waits=s.approval_waits.map(item=>safe(reportStage(item.stage))+': '+safe(reportTime(item.seconds))).join(' · ');
  const notes=report.notes.map(code=>reportNotes[code]?reportNotes[code]():'').filter(Boolean).map(text=>'<li>'+safe(text)+'</li>').join('');
  return '<section class="panel report">'+title+'<p class="muted">'+safe(requestName(report.pr))+' · '+mon((report.head_commit||'').slice(0,8))+' · '+safe(report.status.status)+'</p>'+tiles+(s.findings?reportDistribution(report):'')+table
    +'<h3>'+copy('القرارات البشرية','Human decisions')+'</h3>'+approvals+(waits?'<p class="muted">'+copy('انتظار الموافقة بعد نجاح الفحص: ','Wait for approval after a passing scan: ')+waits+'</p>':'')
    +'<ul class="report-notes">'+notes+'</ul></section>';
}
