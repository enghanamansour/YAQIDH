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
const reportStatus=row=>row.status==='open'?copy('مفتوحة','Open'):row.status==='excepted'?copy('مستثناة','Excepted'):copy('أُغلقت','Closed');
const reportNotes={
  elapsed_time:()=>copy('الزمن هو المدة المنقضية بين الفحوصات وتشمل الانتظار، وليس جهد المطوّر.','Time is the elapsed time between scans and includes waiting; it is not the developer’s working time.'),
  scan_resolution:()=>copy('دقة الزمن بحجم الفترة بين فحصين.','Precision equals the gap between two scans.'),
  low_awareness:()=>copy('الثغرات المنخفضة لا تمنع الدمج، لكنها تُسجَّل وتظهر هنا. «منخفضة» لا تعني «بلا ضرر»: اقرأها وقرر إصلاحها لاحقًا.','Low findings do not block the merge, but they are recorded and shown here. “Low” does not mean “harmless”: read them and plan a fix.'),
  severity_source:()=>copy('الخطورة تأتي من تصنيف الأداة نفسها (حرجة وعالية ومتوسطة ومنخفضة). يَقِـــظ يحوّل الحرجة والعالية والمتوسطة إلى «مانعة»، ولا يمرر إلا المنخفضة الصريحة. مرجع التصنيف في CVSS: منخفضة 0.1–3.9، متوسطة 4.0–6.9، عالية 7.0–8.9، حرجة 9.0–10.','Severity comes from the tool’s own rating (critical, high, medium, low). Yaqidh treats critical, high and medium as blocking and lets only an explicit low through. The CVSS bands: low 0.1–3.9, medium 4.0–6.9, high 7.0–8.9, critical 9.0–10.'),
  owasp_source:()=>copy('تصنيف OWASP Top 10 (2021) يُستنتج من رقم CWE بجدول ثابت، ومكتبات الطرف الثالث تُصنَّف «مكونات ضعيفة أو قديمة». الثغرة بلا CWE معروف تظهر بلا تصنيف.','The OWASP Top 10 (2021) category is taken from the CWE with a fixed table; third-party library findings are “Vulnerable and Outdated Components”. A finding without a known CWE shows no category.'),
  db_origin:()=>copy('الثغرات الناتجة عن تحديث قاعدة بيانات الثغرات تظهر معلَّمة، ولا تُنسب للمطوّر.','Findings caused by a vulnerability database update are marked and not attributed to the developer.')
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
const reportTone=level=>({critical:'bad',high:'bad',medium:'wait',low:'good'})[level]||'wait';
const reportRated=row=>reportLevel(String(row.reported_as||'unknown').toLowerCase());


/* An icon by kind of finding, so a key, a library and a piece of code look different at a glance. */
const reportIcons={
  key:'<circle cx="8" cy="12" r="3.5"/><path d="M11.5 12H21M17 12v3M20 12v2"/>',
  lib:'<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  code:'<path d="M9 8l-5 4 5 4M15 8l5 4-5 4"/>',
  web:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18"/>',
  shield:'<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/>'
};
function reportKind(row){
  const rule=String(row.rule).toLowerCase();
  if(rule.includes('github-pat')||rule.includes('secret'))return 'key';
  if(row.component)return 'lib';
  if(rule.includes('csrf')||rule.includes('template'))return 'web';
  if(rule.includes('sql')||rule.includes('debug'))return 'code';
  return 'shield';
}
const reportIcon=row=>'<span class="fc-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+reportIcons[reportKind(row)]+'</svg></span>';
function reportTitle(row){
  if(row.component&&/^CVE-/i.test(String(row.rule))){
    const pkg=String(row.component).split('==')[0];
    return copy('ثغرة في مكتبة ','Vulnerability in the library ')+pkg;
  }
  const hit=reportNames.find(([key])=>String(row.rule).includes(key));
  return hit?hit[1]():String(row.rule).split('.').pop();
}
function reportChips(row){
  const chips=[];
  if(row.component){const version=String(row.component).split('==')[1];if(version)chips.push(copy('النسخة ','version ')+version);}
  if(/^CVE-/i.test(String(row.rule)))chips.push(String(row.rule));
  if(row.location&&!String(row.location).startsWith('qa_checks/'))chips.push(String(row.location).replace(/^__pycache__\//,''));
  return chips.map(c=>'<span class="fc-chip">'+safe(c)+'</span>').join('');
}

function reportTile(label,value,tone,note){
  return '<div class="metric report-tile '+tone+'"><strong>'+safe(value)+'</strong><span>'+label+'</span>'+(note?'<small>'+safe(note)+'</small>':'')+'</div>';
}

/* Where the build is, in five steps, and one sentence saying what it needs. */
const reportSteps=()=>[copy('فحص الجودة','QA check'),copy('موافقة الجودة','QA approval'),copy('الفحص الأمني','Security check'),copy('موافقة الأمن','Security approval'),copy('جاهز للدمج','Ready to merge')];
const reportWhere={
  not_started:[0,'bad'],qa_blocked:[0,'bad'],qa_rejected:[0,'bad'],awaiting_qa_approval:[1,'wait'],
  awaiting_security_scan:[2,'wait'],security_blocked:[2,'bad'],security_rejected:[2,'bad'],awaiting_security_approval:[3,'wait'],ready_to_merge:[4,'good']
};
const reportSentence={
  not_started:()=>copy('لم يبدأ الفحص بعد.','Checking has not started yet.'),
  qa_blocked:()=>copy('فحص الجودة وجد مشكلات تمنع الدمج. أصلحها وارفع تعديلاً جديداً.','The QA check found blocking findings. Fix them and push a new change.'),
  qa_rejected:()=>copy('أرجع فريق الجودة البناء. اقرأ السبب وأصلح ثم ارفع تعديلاً.','The QA team returned the build. Read the reason, fix it and push again.'),
  awaiting_qa_approval:()=>copy('اجتاز فحص الجودة، وينتظر موافقة فريق الجودة.','It passed the QA check and waits for the QA team.'),
  awaiting_security_scan:()=>copy('ينتظر الفحص الأمني.','Waiting for the security check.'),
  security_blocked:()=>copy('الفحص الأمني وجد ثغرات تمنع الدمج. أصلحها وارفع تعديلاً جديداً.','The security check found blocking findings. Fix them and push a new change.'),
  security_rejected:()=>copy('أرجع فريق الأمن البناء. اقرأ السبب وأصلح ثم ارفع تعديلاً.','The security team returned the build. Read the reason, fix it and push again.'),
  awaiting_security_approval:()=>copy('اجتاز الفحص الأمني، وينتظر موافقة فريق الأمن.','It passed the security check and waits for the security team.'),
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
  return '<svg class="stack" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="'+safe(copy('توزيع المشكلات والثغرات','Findings split'))+'"><rect class="track" width="100" height="10"/>'+rects+'</svg>'
    +'<div class="legend">'+parts.map(p=>'<span class="'+p[1]+'">'+p[2]+' <b>'+p[0]+'</b></span>').join('')+'</div>';
}

/* The share of each rating the tool gave (critical, high, medium, low): always visible. */
function reportRatings(s){
  const order=['critical','high','medium','low','unknown'],by=s.by_reported||{};
  const chips=order.filter(k=>by[k]).map(k=>'<span class="rating '+reportTone(k)+'"><b>'+Math.round(100*by[k]/s.findings)+'%</b> '+safe(reportLevel(k))+' <small>('+by[k]+')</small></span>').join('');
  return chips?'<div class="ratings"><small class="muted">'+copy('نسبة الخطورة حسب تصنيف الأداة','Severity share, by the tool’s rating')+'</small>'+chips+'</div>':'';
}

/* One finding, explained: what it is, how serious, when it closed and how long it took. */
function reportCard(row){
  const closed=row.closed_at!==null&&row.closed_at!==undefined;
  const state=closed?'good':row.status==='excepted'?'wait':'bad';
  const time=closed?reportTime(row.seconds_to_close):row.seconds_open!==null?reportTime(row.seconds_open)+' · '+copy('ما زالت مفتوحة','still open'):'—';
  const fact=(label,value)=>value?'<div><small>'+label+'</small><b>'+value+'</b></div>':'';
  const exc=row.exception?'<div class="exc"><small>'+copy('استثناء من الأمن','Security exception')+'</small><b>'+safe(row.exception.approved_by)+' · '+safe(reportDate(row.exception.at))+'</b><p>'+safe(row.exception.justification)+'</p></div>':'';
  const tone=reportTone(String(row.reported_as||'').toLowerCase());
  const stateIcon=closed?'✓ ':row.status==='excepted'?'◐ ':'● ';
  return '<details class="finding-card '+state+'"><summary>'+reportIcon(row)
    +'<span class="fc-main"><b class="fc-title">'+safe(reportTitle(row))+'</b><span class="fc-chips">'+reportChips(row)+'</span></span>'
    +'<span class="badge fc-rating '+tone+'">'+safe(reportRated(row))+'</span>'
    +'<span class="fc-state '+state+'">'+stateIcon+safe(reportStatus(row))+'</span>'
    +'<span class="fc-time">⏱ '+safe(time)+'</span></summary>'
    +'<div class="fc-body">'+(row.explanation?'<p class="fc-explain">'+safe(row.explanation)+'</p>':'')
    +'<h4 class="flow-label">'+copy('كيف صُنّف الخطر','How the risk was rated')+'</h4>'+riskFlow(row)
    +'<h4 class="flow-label">'+copy('الخط الزمني','Timeline')+'</h4>'+timeFlow(row)
    +'<div class="facts">'
    +fact('OWASP',safe(row.owasp))+fact('CWE',safe(row.cwe))
    +fact(copy('النسخة المصلحة','Fixed version'),safe(row.fixed_version))
    +'</div>'+exc+'</div></details>';
}


/* How one finding was rated, step by step: the tool's rating, Yaqidh's rule, a person's decision if any, where it stands. */
function hnode(label,value,tone,sub){
  return '<div class="hnode '+tone+'"><small>'+label+'</small><b>'+value+'</b>'+(sub?'<span>'+sub+'</span>':'')+'</div>';
}
const harrow=()=>'<i class="harrow" aria-hidden="true"></i>';

function riskFlow(row){
  const level=String(row.reported_as||'unknown').toLowerCase(),blocks=row.severity==='high';
  const closed=row.closed_at!==null&&row.closed_at!==undefined;
  const nodes=[
    hnode(copy('الأداة صنّفتها','The tool rated it'),safe(reportLevel(level)),reportTone(level),safe(toolName(row.tool))),
    hnode(copy('قاعدة يَقِـــظ','Yaqidh rule'),blocks?copy('تمنع الدمج','Blocks the merge'):copy('تمر بتوعية','Passes with awareness'),blocks?'bad':'good',blocks?copy('غير «المنخفضة» تمنع','anything but “low” blocks'):copy('تظهر وتُسجَّل','shown and recorded'))
  ];
  if(row.exception)nodes.push(hnode(copy('قرار الأمن','Security decision'),copy('استثناء مقبول','Exception accepted'),level==='medium'?'wait':'bad',safe(row.exception.approved_by)));
  nodes.push(hnode(copy('حالتها الآن','Where it stands'),safe(reportStatus(row)),closed?'good':row.status==='excepted'?'wait':'bad',''));
  return '<div class="hflow" role="group" aria-label="'+safe(copy('مسار تصنيف الخطر','Risk classification path'))+'">'+nodes.join(harrow())+'</div>';
}

/* How long it lived: first seen, the scan rounds, closed. */
function timeFlow(row){
  const closed=row.closed_at!==null&&row.closed_at!==undefined;
  const nodes=[
    hnode(copy('أول ظهور','First seen'),safe(reportDate(row.first_seen)),'accent',safe(reportStage(row.stage))),
    hnode(copy('جولات الفحص','Check rounds'),safe(row.rounds),'wait',''),
    closed?hnode(copy('أُغلقت','Closed'),safe(reportDate(row.closed_at)),'good',copy('بعد ','after ')+safe(reportTime(row.seconds_to_close)))
          :hnode(copy('لم تُغلق','Not closed yet'),row.seconds_open!==null?safe(reportTime(row.seconds_open)):'—','bad',copy('مفتوحة منذ ظهورها','open since it appeared'))
  ];
  return '<div class="hflow" role="group" aria-label="'+safe(copy('الخط الزمني','Timeline'))+'">'+nodes.join(harrow())+'</div>';
}

function developerReport(){
  const report=release&&release.report;
  const title='<h2>'+copy('تقرير البناء','Build report')+'</h2>';
  if(!report)return '<section class="panel">'+title+'<p class="muted">'+copy('يظهر التقرير عند تشغيل اللوحة على واجهة يَقِـــظ الحية.','The report appears when the dashboard runs against the live Yaqidh API.')+'</p></section>';
  const s=report.summary,avg=s.time_to_close.average_seconds;
  const picker=profile.releases.length>1?'<label class="field">'+copy('البناء','Build')+'<select id="release-select">'+profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+safe(buildName(item.build))+'</option>').join('')+'</select></label>':'';
  const head='<div class="section-head"><div>'+title+'<small>'+safe(requestName(release.pr))+' · '+mon((report.head_commit||'').slice(0,8))+'</small></div>'+picker+'</div>';
  const tiles='<div class="metric-row">'
    +reportTile(copy('مشكلات وثغرات وُجدت','Findings found'),s.findings,'')
    +reportTile(copy('أُغلقت','Closed'),s.closed,'good',s.closed_percent==null?'':s.closed_percent+'%')
    +reportTile(copy('تمنع الدمج الآن','Blocking now'),s.open_blocking,s.open_blocking?'bad':'good')
    +reportTile(copy('متوسط زمن الإغلاق','Average time to close'),reportTime(avg),'wait',s.time_to_close.count?copy('الأطول: ','longest: ')+reportTime(s.time_to_close.max_seconds):copy('لا إغلاقات بعد','nothing closed yet'))
    +'</div>';
  const cards=report.findings.length?'<details class="catalog"'+(s.open_blocking?' open':'')+'><summary><b>'+copy('كل مشكلة أو ثغرة بالتفصيل','Every finding in detail')+'</b><span>'+report.findings.length+' '+copy('مشكلة · اضغط لتفتح القائمة','findings · click to open the list')+'</span></summary><div class="finding-cards">'+report.findings.map(reportCard).join('')+'</div></details>':'<p class="muted">'+copy('لا توجد مشكلات مسجلة.','No findings recorded.')+'</p>';
  const decided=report.approvals.length?report.approvals.map(item=>safe(reportStage(item.stage))+': '+(item.decision==='approve'?copy('وافق','approved'):copy('أرجع','returned'))+' · '+safe(item.by)).join(' · '):copy('لا قرارات بشرية بعد','No human decisions yet');
  const waits=s.approval_waits.map(item=>safe(reportStage(item.stage))+': '+safe(reportTime(item.seconds))).join(' · ');
  const notes=report.notes.map(code=>reportNotes[code]?reportNotes[code]():'').filter(Boolean).map(text=>'<li>'+safe(text)+'</li>').join('');
  const more='<details class="more-details"><summary>'+copy('كيف تُحسب هذه الأرقام؟','How are these numbers worked out?')+'</summary>'
    +(waits?'<p class="muted">'+copy('انتظار الموافقة بعد نجاح الفحص: ','Wait for approval after a passing check: ')+waits+'</p>':'')+'<ul class="report-notes">'+notes+'</ul></details>';
  return '<section class="panel report">'+head+reportStepper(report)+tiles+reportBar(s)+reportRatings(s)+cards+'<p class="muted decided">'+decided+'</p>'+more+'</section>';
}
