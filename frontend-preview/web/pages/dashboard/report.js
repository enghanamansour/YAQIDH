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
const reportStatus=row=>row.status==='open'?copy('مفتوحة','Open'):row.status==='excepted'?copy('مستثناة','Excepted'):copy('مغلقة بإثبات','Closed, verified');
const reportNotes={
  elapsed_time:()=>copy('الزمن هو المدة المنقضية بين الفحوصات وتشمل الانتظار، وليس جهد المطوّر.','Time is the elapsed time between scans and includes waiting; it is not the developer’s working time.'),
  scan_resolution:()=>copy('دقة الزمن بحجم الفترة بين فحصين.','Precision equals the gap between two scans.'),
  db_origin:()=>copy('الملاحظات الناتجة عن تحديث قاعدة بيانات الثغرات تظهر معلَّمة، ولا تُنسب للمطوّر.','Findings caused by a vulnerability database update are marked and not attributed to the developer.')
};

function reportTile(label,value,tone,note){
  return '<div class="metric report-tile '+tone+'"><strong>'+safe(value)+'</strong><span>'+label+'</span>'+(note?'<small>'+safe(note)+'</small>':'')+'</div>';
}

function reportRow(row){
  const name=row.component?row.rule+' · '+row.component:String(row.rule).split('.').pop();
  const origin=row.origin==='new_from_db_update'?' <span class="badge">'+copy('من تحديث قاعدة البيانات','From a database update')+'</span>':'';
  return '<tr><td>'+safe(name)+origin+'<br><small>'+mon(row.location)+' · '+safe(reportStage(row.stage))+'</small></td><td>'+reportSeverity(row.severity)+'</td><td>'+safe(reportStatus(row))+'</td>'
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
    +reportTile(copy('جولات الفحص','Scan rounds'),s.rounds.qa+' / '+s.rounds.security,'',copy('الجودة / الأمن','QA / Security'))
    +'</div>';
  const rows=report.findings.map(reportRow).join('');
  const table=rows?'<div class="table-wrap"><table class="report-table"><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الخطورة','Severity')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('أول ظهور','First seen')+'</th><th>'+copy('الإغلاق','Closed')+'</th><th>'+copy('الزمن','Time')+'</th><th>'+copy('الجولات','Rounds')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p class="muted">'+copy('لا توجد ملاحظات مسجلة.','No findings recorded.')+'</p>';
  const approvals=report.approvals.length?'<ul class="metric-records">'+report.approvals.map(item=>'<li>'+safe(reportStage(item.stage))+' · '+(item.decision==='approve'?copy('موافقة','Approved'):copy('إرجاع','Returned'))+' · '+safe(item.by)+' · '+safe(reportDate(item.at))+(item.reason?' · '+safe(item.reason):'')+'</li>').join('')+'</ul>':'<p class="muted">'+copy('لا توجد قرارات بشرية بعد.','No human decisions yet.')+'</p>';
  const waits=s.approval_waits.map(item=>safe(reportStage(item.stage))+': '+safe(reportTime(item.seconds))).join(' · ');
  const notes=report.notes.map(code=>reportNotes[code]?reportNotes[code]():'').filter(Boolean).map(text=>'<li>'+safe(text)+'</li>').join('');
  return '<section class="panel report">'+title+'<p class="muted">'+safe(requestName(report.pr))+' · '+mon((report.head_commit||'').slice(0,8))+' · '+safe(report.status.status)+'</p>'+tiles+table
    +'<h3>'+copy('القرارات البشرية','Human decisions')+'</h3>'+approvals+(waits?'<p class="muted">'+copy('انتظار الموافقة بعد نجاح الفحص: ','Wait for approval after a passing scan: ')+waits+'</p>':'')
    +'<ul class="report-notes">'+notes+'</ul></section>';
}
