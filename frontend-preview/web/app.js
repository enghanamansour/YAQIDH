'use strict';
const $=selector=>document.querySelector(selector);
const app=$('#app'),dialog=$('#dialog');
const safe=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const copy=(ar,en)=>document.documentElement.lang==='en'?en:ar;
const demoText=value=>({
  'qa-return-demo':copy('لم يظهر تأكيد الطلب. أصلح السيناريو وأعد الفحص.','Order confirmation was missing. Fix it and rerun the check.'),
  'ready-demo':copy('اكتملت الفحوصات وراجعت أدلة البناء.','Required checks completed and evidence was reviewed.'),
  'Fixture: QA checks completed for this commit.':copy('اكتملت فحوصات الجودة التجريبية لهذا التعديل.','Demo QA checks completed for this commit.'),
  'Demo: the order confirmation did not appear after submission.':copy('في المثال، لم يظهر تأكيد الطلب بعد الإرسال.','Demo: the order confirmation did not appear after submission.'),
  'A query builds SQL from request input. Review the reported location.':copy('يُنشأ استعلام قاعدة البيانات من مدخلات الطلب. راجع الموقع المحدد.','A query builds SQL from request input. Review the reported location.'),
  'Isolated demo dependency pending replacement.':copy('مكتبة تجريبية معزولة بانتظار الاستبدال.','Isolated demo dependency pending replacement.'),
  'Demo QA reviewer':copy('مراجع الجودة التجريبي','Demo QA reviewer'),
  'Demo reviewer':copy('مراجع تجريبي','Demo reviewer')
}[value]||value);
const mon=value=>'<bdi class="mono">'+safe(value)+'</bdi>';

const isLive=()=>Boolean(profile&&profile.live);
const requestedSample=new URLSearchParams(location.search).get('sample');
let profile=null,release=null,tool='all',severity='all',findingFilter='all',runFilter='all',developerOutcome='all',developerDay='all';
let requestNumber=0;
const roleNames=role=>({
  developer:copy('المطوّر','Developer'),
  qa:copy('مراجع الجودة','QA reviewer'),
  security:copy('مراجع الأمن السيبراني','Security reviewer'),'company-admin':copy('مسؤول إدارة الشركة','Company admin'),
}[role]||role);
const projectName=id=>id==='portal'?copy('بوابة الخدمات','Services Portal'):id==='research'?copy('مشروع المختبر','Lab project'):id;
const toolName=id=>({semgrep:'Semgrep',trivy:'Trivy',playwright:'Playwright'}[id]||id);
const severityName=id=>({
  high:copy('مرتفعة','HIGH'),low:copy('منخفضة','LOW'),medium:copy('متوسطة','Medium'),
  critical:copy('حرجة','Critical'),info:copy('معلومة','Info'),unknown:copy('غير محددة','Unknown')
}[id]||'—');
const accountName=id=>({
  developer:copy('حساب المطوّر التجريبي','developer'),
  qa:copy('مراجع الجودة','QA reviewer'),
  security:copy('حساب الأمن التجريبي','security'),
  'company-admin':copy('حساب إدارة الشركة التجريبي','company-admin'),

}[id]||id);
const versionName=id=>({
  'semgrep-rules':copy('قواعد سيم غريب','Semgrep rules'),
  'trivy-db':copy('قاعدة بيانات تريفي','Trivy database'),
  trivy:toolName('trivy')
}[id]||id);
const versionValue=value=>['demo-rules','demo-db'].includes(value)?copy('نسخة تجريبية',value):value;
const buildName=id=>copy('الطلب #'+id,'Request #'+id);
const requestName=id=>copy('الطلب #'+id,'Request #'+id);
const branchName=id=>id==='staging'?copy('فرع ما قبل الإطلاق','staging'):id;
const findingName=f=>{
  const check=((typeof release!=='undefined'&&release&&release.qaChecks)||[]).find(c=>c.finding===f.fingerprint);
  if(check)return copy(check.titleAr,check.titleEn);
  return findingNameMap(f);
};
const findingNameMap=f=>({
  'demo.sql-query':copy('استعلام يستخدم مدخلات الطلب','Query uses request input'),
  'demo.order-confirmation':copy('لم يظهر تأكيد الطلب','Order confirmation missing'),
  'DEMO-ADVISORY-01':copy('ثغرة في مكتبة مستخدمة','Dependency finding'),
  'DEMO-ADVISORY-02':copy('ثغرة مستثناة في مكتبة','Excepted dependency finding')
}[f.rule]||f.title||f.rule||f.fingerprint);
const logo=()=>'/assets/yaqidh-'+document.documentElement.dataset.theme+'-transparent.png';
const action=(name,label,extra='')=>'<button type="button" data-action="'+name+'" '+extra+'>'+label+'</button>';
const badge=(label,tone='')=>'<span class="badge '+tone+'">'+label+'</span>';
const detail=(label,value)=>'<div><small>'+label+'</small><br>'+value+'</div>';
const metricDetails=new Map();
const findingRecord=f=>safe(findingName(f))+' · '+safe(findingState(f))+' '+action('finding',copy('فتح الدليل','Open evidence'),'data-id="'+safe(f.fingerprint)+'"');
const buildRecord=b=>safe(requestName(b.pr))+' · '+safe(buildName(b.build))+' '+action('queue',copy('فتح البناء','Open build'),'data-id="'+safe(b.id)+'"');
const runRecord=r=>safe(toolName(r.tool))+' · '+safe(statusText(r.state))+(r.day?' · '+safe(r.day):'');
const fraction=(n,total)=>n+'/'+total;
const stateLabels=()=>[['completed',copy('اكتمل','Completed')],['error',copy('تعطل','Failed to run')],['pending',copy('قيد الانتظار','Pending')]];
function buildScope(text){return buildName(release.build)+' · '+text}
function chipRow(filters,clearAction){
  const active=filters.filter(([,value])=>value!=='all');
  return active.length?'<div class="chips active-filters">'+active.map(([key,value,label])=>action('remove-filter',safe(label)+' ×','data-id="'+key+'"')).join('')+action(clearAction,copy('مسح الكل','Clear all'))+'</div>':'';
}
function chartPick(state){return runFilter===state?'all':state}
function refreshChart(button){
  const key=button.dataset.action,id=button.dataset.id;
  render();
  app.querySelector('[data-action="'+key+'"][data-id="'+CSS.escape(id||'')+'"]')?.focus({preventScroll:true});
}
function preference(name,fallback){try{return localStorage.getItem(name)||fallback}catch{return fallback}}
function setPreference(name,value){try{localStorage.setItem(name,value)}catch{}}
function setAppearance(){
  const root=document.documentElement;
  root.lang=preference('yaqidh-role-lang','ar')==='en'?'en':'ar';
  root.dir=root.lang==='en'?'ltr':'rtl';
  document.title=copy('يَقِـــظ','YAQIDH');
  root.dataset.theme=preference('yaqidh-role-theme','dark')==='light'?'light':'dark';
}
async function api(path,data){
  const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(!response.ok)throw new Error(String(response.status));
  return response.json();
}
function notify(text){$('#notice').textContent=text;clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('#notice').textContent='',5500)}
function modal(title,body){
  if(dialog.open)dialog.close();
  dialog.innerHTML='<h2>'+title+'</h2>'+body+'<div class="actions">'+action('close',copy('إغلاق','Close'))+'</div>';
  dialog.showModal();
}
function changeAppearance(id){
  const form=app.querySelector('#sign-in, #sign-up');
  const values=form?Array.from(form.elements).filter(field=>field.name||field.id).map(field=>[field.name||field.id,field.value,Boolean(field.name)]):[];
  const buttonSelector='.top [data-action="'+id+'"]';
  const hadFocus=document.activeElement===app.querySelector(buttonSelector);
  if(id==='ar'||id==='en')setPreference('yaqidh-role-lang',id);
  else setPreference('yaqidh-role-theme',id);
  setAppearance();
  render();
  const current=app.querySelector('#sign-in, #sign-up');
  if(current)for(const [key,value,byName] of values){
    const field=byName?current.elements.namedItem(key):document.getElementById(key);
    if(field)field.value=value;
  }
  if(hadFocus)app.querySelector(buttonSelector)?.focus({preventScroll:true});
}

const liveWarning=()=>profile&&profile.liveError?'<section class="panel" role="alert"><b>'+copy('تعذّر قراءة البيانات الحقيقية','Could not read the real data')+'</b><p>'+safe(profile.liveError)+'</p></section>':'';
function introduction(){
  return liveWarning()+'<section class="intro"><div><h1>'+roleNames(profile.role)+'</h1><small>'+(isLive()?copy('بيانات حقيقية من خادم يَقِـــظ','Live data from the Yaqidh server'):copy('معاينة محلية · بيانات تشغيل ومستخدمون تجريبيون','Local preview · Demo runs and users'))+'</small></div>'+'<div class="actions">'+action('refresh',copy('تحديث','Refresh'))+badge(safe(accountName(profile.role)))+'</div></section>';
}
let adminQuery='',adminActive='all';



function outcomeText(){return release.outcome?(release.outcome.result==='pass'?copy('نجح','PASS'):copy('فشل','FAIL')):release.runs.some(run=>run.state==='error')?copy('تعطل فحص مطلوب','Required check failed to run'):copy('بانتظار نتيجة صالحة','Awaiting a valid result')}
function stageText(stage){return stage==='qa'?copy('فحص الجودة','Quality check'):copy('الفحص الأمني','Security check')}
function statusText(status){return ({
  open:copy('قيد التنفيذ','In progress'),fixed:copy('أُغلقت','Closed'),excepted:copy('مستثناة','Excepted'),
  completed:copy('مكتمل','Completed'),error:copy('تعطل','Failed to run'),
  approve:copy('موافقة مسجلة','Approval recorded'),reject:copy('إرجاع مع السبب','Returned with reason')
})[status]||copy('بانتظار القرار','Awaiting decision')}
function lastDecision(){return release.decisions.at(-1)}
function decisionText(){return statusText(lastDecision()?.decision)}
function displayReason(reason){
  if(reason==='no blocking findings')return copy('لا توجد مشكلات مانعة وفق السياسة','No blocking findings');
  const count=reason.match(/^(\d+) high open$/);
  return count?copy(count[1]==='1'?'مشكلة واحدة عالية الخطورة تمنع التقدّم':count[1]+' مشكلات عالية الخطورة تمنع التقدّم',count[1]+' blocking HIGH findings'):safe(reason);
}
function sampleBuild(sample){if(profile.role==='developer')return sample==='issue'?'portal-133':'portal-129';if(sample==='approved')return profile.role==='qa'?'portal-129':'portal-135';return profile.role==='qa'?(sample==='issue'?'portal-133':'portal-132'):(sample==='issue'?'portal-128':'portal-134')}
function findingState(f){return f.closure?.result==='closed'?copy('أُغلقت','Closed'):f.closure?.result==='still_open'?copy('ما زالت قيد التنفيذ','Still in progress'):statusText(f.status)}
function findingGroup(f){return f.closure?.result==='closed'?'fixed':f.status==='excepted'?'excepted':'open'}
function matched(){return release.findings.filter(f=>(runFilter==='all'||release.runs.filter(run=>run.tool===f.tool).length===1&&release.runs.some(run=>run.tool===f.tool&&run.state===runFilter))&&(findingFilter==='all'||findingGroup(f)===findingFilter)&&(tool==='all'||tool===f.tool)&&(severity==='all'||severity===f.severity))}


let threads=[],selectedThread=null;
const unreadCount=()=>threads.filter(thread=>thread.unread).length;

function render(){
  hideMetricTip();
  metricDetails.clear();
  const page=location.pathname;
  if(page==='/'){app.innerHTML=header()+landing();startTyping();if(location.hash==='#about')document.getElementById('about').scrollIntoView();return}
  const content=page==='/signup'?signup():!profile?login():page==='/communication'?communicationView():page==='/exceptions'?exceptionsView():'<main>'+(['qa','developer','security'].includes(profile.role)?'':introduction())+(profile.role==='company-admin'?adminView():dashboardView())+'</main>';
  app.innerHTML=header()+(hasSidebar()?sidebar():'')+'<div class="'+(profile?(hasSidebar()?'shell':'shell no-side')+(profile.guide?' demo-pad':''):'public-shell')+'">'+demoBannerHtml()+content+'</div>'+demoGuideHtml();
  demoAfterRender();
}
async function selectRelease(id){
  const turn=++requestNumber;
  const next=await api('/api/releases/'+encodeURIComponent(id));
  if(turn!==requestNumber)return;
  release=next;tool='all';severity='all';findingFilter='all';runFilter='all';render();
}
async function load(){
  const infoPromise=demoInfo?null:api('/api/demo/info').catch(()=>({enabled:false})); // asked together with the dashboard, not before it
  if(location.pathname==='/about')history.replaceState(null,'','/#about');
  try{profile=await api('/api/dashboard')}catch(e){if(!['401','403'].includes(e.message))throw e;profile=null;if(!['/','/about','/login','/signup'].includes(location.pathname))history.replaceState(null,'','/login'+location.search)}
  if(profile&&['/login','/dashboard','/admin'].includes(location.pathname)){const destination=profile.role==='company-admin'?'/admin':'/dashboard';if(location.pathname!==destination)history.replaceState(null,'',destination+location.search)}
  if(infoPromise)demoInfo=await infoPromise;
  threads=profile?await api('/api/threads'):[];
  if(location.pathname==='/communication'){selectedThread=new URLSearchParams(location.search).get('thread')||threads[0]?.id||null;render();return}
  if(profile?.releases?.length){
    const preferred=sampleBuild(requestedSample==='ready'?'ready':requestedSample==='issue'?'issue':profile.role==='qa'?'ready':'issue');
    await selectRelease((profile.releases.find(r=>r.id===new URLSearchParams(location.search).get('build'))||profile.releases.find(r=>r.id===preferred)||profile.releases[0]).id);
  }else{release=null;render()}
}
function openRuns(){
  const records=release.runs.map(r=>'<p>'+safe(toolName(r.tool))+' · '+badge(statusText(r.state),r.state==='completed'?'good':'bad')+' '+(isLive()?'':'· '+copy('سجل تشغيل تجريبي','Demo run record'))+'</p>').join('');
  modal(copy('تشغيلات الأدوات','Tool runs'),records||'<p>'+copy('لا توجد سجلات تشغيل لهذه المرحلة.','No run records for this stage.')+'</p>');
}
const eventName=id=>({
  commit_received:copy('وصل commit جديد','New commit received'),event:copy('حدث من GitHub','GitHub event'),
  scan:copy('فحص','Scan'),rescan:copy('إعادة فحص','Re-scan'),policy_decision:copy('قرار السياسة','Policy decision'),
  explanation:copy('شرح من يَقِـــظ','Explanation by YAQIDH'),human_decision:copy('قرار بشري','Human decision'),
  exception:copy('استثناء','Exception'),agent_run:copy('تشغيل الوكيل','Agent run'),gate_checked:copy('فحص البوابة','Gate check'),
  scan_results_received:copy('وصلت نتائج CI','CI results received'),github_published:copy('نشر على GitHub','Posted to GitHub'),
  github_post_failed:copy('فشل النشر على GitHub','GitHub post failed'),scan_results_not_applied:copy('نتائج CI لم تُطبّق','CI results not applied')
}[id]||id);
function eventDetail(e){
  const d=e.data||{};
  if(e.event==='scan')return (d.stage||'')+' · '+copy(d.stage==='security'?'ثغرات':'مشكلات','findings')+' '+d.findings;
  if(e.event==='rescan')return (d.stage||'')+' · '+copy('أُغلقت','closed')+' '+(d.closed||[]).length+' · '+copy('لسا مفتوح','still open')+' '+(d.still_open||[]).length+' · '+copy('جديد','new')+' '+(d.new||[]).length;
  if(e.event==='policy_decision')return (d.stage||'')+' · '+(d.result==='pass'?copy('نجح','PASS'):copy('فشل','FAIL'));
  if(e.event==='human_decision')return (d.stage||'')+' · '+statusText(d.decision)+(d.reason?' · '+d.reason:'');
  if(e.event==='explanation')return (d.stage||'')+' · '+(d.fingerprint||'');
  if(e.event==='agent_run')return (d.stopped||'')+' · '+copy('خطوات','steps')+' '+(d.steps??'');
  return d.commit?String(d.commit).slice(0,7):(d.error||'');
}
function historyTrend(){
  const scans=((release.log||{}).entries||[]).filter(e=>e.event==='scan'||e.event==='rescan');
  return scans.map((e,i)=>{const d=e.data||{};const n=e.event==='scan'?d.findings:(d.still_open||[]).length+(d.new||[]).length;return '<p>'+copy('الفحص','Scan')+' '+(i+1)+' · '+safe(d.stage||'')+': <b>'+n+'</b> '+copy(d.stage==='security'?'ثغرة مفتوحة':'مشكلة مفتوحة','open findings')+' <small>'+mon(String(d.commit||'').slice(0,7)||'—')+'</small></p>'}).join('');
}
function historyView(){
  const log=release.log;
  if(!log)return '<p class="muted">'+copy('لا يتوفر سجل أحداث مؤرخ كافٍ لرسم الاتجاه.','There is not enough dated event history to plot a trend.')+'</p>';
  const ok=log.verified&&log.verified.ok;
  const badgeHtml=ok?badge(copy('سلسلة السجل سليمة','History chain intact')+' · '+log.verified.entries,'good'):badge(copy('السلسلة مكسورة','History chain broken')+(log.verified&&log.verified.broken_at?' · #'+log.verified.broken_at:''),'bad');
  const rows=log.entries.slice().reverse().map(e=>'<tr><td>'+mon(String(e.time).slice(0,16).replace('T',' '))+'</td><td>'+safe(eventName(e.event))+'</td><td>'+safe(e.actor)+'</td><td>'+safe(eventDetail(e))+'</td></tr>').join('');
  return '<p>'+badgeHtml+'</p>'+historyTrend()+(rows?'<div class="table-wrap"><table><thead><tr><th>'+copy('الوقت','Time')+'</th><th>'+copy('الحدث','Event')+'</th><th>'+copy('من','By')+'</th><th>'+copy('التفاصيل','Details')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'');
}
function decisionList(){
  return release.decisions.map(d=>'<p><b>'+statusText(d.decision)+'</b> · '+safe(accountName(demoText(d.by)))+' · '+mon(d.timestamp.slice(0,16))+'<br>'+safe(demoText(d.reason))+'</p>').join('')||'<p>'+copy('لا يوجد قرار مسجّل.','No decision recorded.')+'</p>';
}
function findingModal(id){
  const f=release.findings.find(item=>item.fingerprint===id);
  if(!f)return;
  const flags={closed:copy('أُغلقت','Closed'),still_open:copy('ما زالت قيد التنفيذ','Still in progress'),new:copy('مشكلة جديدة','New finding'),new_from_db_update:copy('جديدة بسبب تحديث قاعدة تريفي','New after Trivy DB update'),reopened:copy('عادت بعد الإغلاق','Reopened')};
  const history=Object.entries(flags).filter(([key])=>release.verification?.[key]?.includes(id)).map(([,label])=>label).join(' · ');
  modal(copy(f.tool==='playwright'?'دليل المشكلة':'دليل الثغرة','Finding evidence'),'<div class="details-grid">'
    +detail(copy('البصمة','Fingerprint'),mon(f.fingerprint))+(profile.role==='developer'?'':detail(copy('الأداة','Tool'),safe(toolName(f.tool))))
    +'<div class="sev-big '+(f.severity==='high'?'bad':'good')+'"><small>'+copy('مستوى الخطورة','Severity')+'</small><strong>'+severityName(f.severity)+'</strong><span>'+(f.severity==='high'?copy('تمنع الإطلاق حتى تنحل','Blocks the release until fixed'):copy('لا تمنع الإطلاق','Does not block the release'))+'</span></div>'
    +detail(copy('القاعدة والموقع','Rule and location'),mon(f.rule)+' · '+mon(f.location))
    +(profile.role==='security'?detail(copy('المكوّن وإصداره','Component and version'),mon(f.component||'—')):'')
    +(f.fixed_version?detail(copy('النسخة المصلحة','Fixed version'),mon(f.fixed_version)):'')
    +(f.cwe?detail(copy('التصنيف (CWE)','CWE'),mon(f.cwe)):'')
    +(f.confidence?detail(copy('ثقة الأداة','Tool confidence'),safe(({high:copy('عالية','High'),medium:copy('متوسطة','Medium'),low:copy('منخفضة (قد تكون إنذارًا كاذبًا)','Low (may be a false alarm)')}[f.confidence])||f.confidence)):'')
    +(f.detail&&!f.explanation?detail(copy('رسالة الأداة','Tool message'),safe(f.detail)):'')
    +detail(copy('حالة الطلب','Request status'),safe(statusText(f.status)))
    +detail(copy('إعادة التحقق','Reverification'),safe(history||(f.closure?findingState(f):copy('لا يوجد دليل إعادة فحص','No rescan evidence'))))
    +(profile.role==='security'?detail(copy('قبل / بعد','Before / after'),release.prior&&history?mon('#'+release.prior.build+' → #'+release.build):'—'):'')+'</div>'
    +((profile.role==='developer'||profile.role==='security')&&release.reports&&release.reports[f.tool]?'<p><a class="action rep-dl" href="/api/releases/'+encodeURIComponent(release.id)+'/reports/'+encodeURIComponent(f.tool)+'" download>'+copy('تنزيل تقرير ','Download the report of ')+safe(toolName(f.tool))+'</a></p>':'')
    +rescanHistory(f)
    +(id==='playwright-demo-001'?'<p class="note">'+copy('المتوقع: يظهر تأكيد الطلب بعد الإرسال. الفعلي: لم يظهر التأكيد في عينة الاختبار.','Expected: order confirmation appears after submission. Actual: the confirmation was absent in the demo run.')+'</p>':'')
    +(f.closure?'<p>'+copy('وقت تحقق الإغلاق','Verification time')+' '+mon(f.closure.timestamp)+'</p>':'')
    +(f.exception?'<p class="note"><b>'+copy('استثناء مسجل','Recorded exception')+'</b><br>'+safe(demoText(f.exception.justification))+' · '+safe(demoText(f.exception.approved_by))+'</p>':'')
    +(profile.role==='security'||(profile.role==='developer'&&release.stage==='security'&&!release.blockerIds.includes(f.fingerprint))?'':'<p>'+action('new-thread',release.stage==='security'?copy('طلب تمديد المهلة','Request deadline extension'):(profile.role==='qa'?copy('مراسلة المطوّر عن هذه المشكلة','Message the developer about this problem'):copy(f.tool==='playwright'?'ناقش هذه المشكلة':'ناقش هذه الثغرة','Discuss this finding')),'data-id="'+safe(f.fingerprint)+'"')+'</p>')
    +(profile.role==='developer'&&f.status==='open'?'<p>'+action(release.exceptionEligible.includes(f.fingerprint)?'new-exception':'exception-refused',copy('طلب استثناء','Request an exception'),'data-id="'+safe(f.fingerprint)+'"')+'</p>':'')
    +(f.explanation?'<div class="note explain"><b>'+copy('شرح يَقِـــظ للمطوّر','YAQIDH explanation for the developer')+'</b><br>'+safe(demoText(f.explanation.text))+'</div>':'')
    +(isLive()&&profile.role==='security'&&release.stage==='security'&&(release.exceptionEligible||[]).includes(f.fingerprint)&&f.status==='open'?'<p>'+action('exception',copy('منح استثناء','Grant exception'),'data-id="'+safe(f.fingerprint)+'"')+'</p>':''));
}
const gateStatusText=code=>({
  not_started:copy('لم يبدأ الفحص','Not started'),qa_blocked:copy('الجودة: فيه مشكلات مانعة، يرجع للمطوّر','QA: blocking findings, back to the developer'),
  awaiting_qa_approval:copy('الجودة نجحت، بانتظار موافقة مراجع الجودة','QA passed, waiting for the QA reviewer'),
  qa_rejected:copy('مراجع الجودة أرجع الطلب','The QA reviewer returned the request'),
  awaiting_security_scan:copy('وافقت الجودة، الفحص الأمني لم يعمل بعد','QA approved, security not scanned yet'),
  security_blocked:copy('الأمن: فيه ثغرات مانعة، يرجع للمطوّر','Security: blocking findings, back to the developer'),
  awaiting_security_approval:copy('الأمن نجح، بانتظار موافقة مراجع الأمن','Security passed, waiting for the security reviewer'),
  security_rejected:copy('مراجع الأمن أرجع الطلب','The security reviewer returned the request'),
  ready_to_merge:copy('اكتمل كل شي، الدمج مسموح','Everything passed and was approved: merge allowed')}[code]||code);
function statusPanel(){
  const g=release&&release.gate;
  if(!g)return '';
  const row=(label,ok)=>'<p>'+badge(ok?copy('مسموح','Allowed'):copy('ممنوع','Blocked'),ok?'good':'bad')+' '+label+'</p>';
  return '<section class="panel gate"><h2>'+copy('حالة الطلب','Request status')+'</h2><p><b>'+safe(gateStatusText(g.status))+'</b></p>'
    +row(copy('الدمج على staging','Merge to staging'),g.staging)+row(copy('الدمج على main','Merge to main'),g.main)
    +(g.reasons&&g.reasons.length?'<p class="muted">'+g.reasons.map(r=>safe(displayReason(r))).join(' · ')+'</p>':'')+'</section>';
}
async function refreshData(manual){
  if(!profile||location.pathname!=='/dashboard'||dialog.open)return;
  try{
    const before=JSON.stringify([profile,release]);
    profile=await api('/api/dashboard');
    const wanted=(release&&profile.releases?.some(r=>r.id===release.id))?release.id:profile.releases?.[0]?.id;
    release=wanted?await api('/api/releases/'+encodeURIComponent(wanted)):null;
    if(manual||JSON.stringify([profile,release])!==before)render();
    if(manual)notify(copy('تم التحديث','Updated'));
  }catch(e){
    if(e.message==='401'){profile=release=null;threads=[];selectedThread=null;history.replaceState(null,'','/login');render();return}
    if(manual)notify(copy('تعذر التحديث','Could not refresh'))
  }
}
async function handleAction(button){
  const id=button.dataset.action;
  if(id==='close')return dialog.close();
  if(id==='refresh')return refreshData(true);
  if(id==='demo-guide-toggle'){demoGuideOpen=!demoGuideOpen;const guide=document.querySelector('.demo-guide');if(guide)guide.outerHTML=demoGuideHtml();return}
  if(id==='demo-enter'){const out=await api('/api/demo/enter',{role:'developer'});history.replaceState(null,'','/dashboard');demoApply(out);return}
  if(id==='demo-role'){demoWorking(button);try{demoApply(await api('/api/demo/role',{role:button.dataset.id}))}finally{demoBusy=false}return}
  if(id==='demo-push'){demoWorking(button);try{demoApply(await api('/api/demo/push',{}))}finally{demoBusy=false}return}
  if(id==='demo-reset'){demoWorking(button);try{demoApply(await api('/api/demo/reset',{}))}finally{demoBusy=false}return}
  if(id==='go-back'){const same=document.referrer&&new URL(document.referrer).origin===location.origin;if(history.length>1&&same)history.back();else location.href='/';return}
  if(id==='exception'){
    return modal(copy('منح استثناء','Grant exception'),'<p>'+copy('للثغرات المتوسطة فقط. تحتاج تبريرًا مكتوبًا، وسياسة يَقِـــظ هي التي تقرر هل يكفي.','Medium findings only. A written justification is required and the policy decides whether it is enough.')+'</p>'
      +'<form id="exception-form" data-release="'+safe(release.id)+'" data-finding="'+safe(button.dataset.id)+'"><label class="field">'+copy('التبرير','Justification')+'<textarea name="justification" required minlength="3" maxlength="1000"></textarea></label>'
      +'<button class="primary">'+copy('حفظ الاستثناء','Save exception')+'</button></form>');
  }
  if(id==='metric')return showMetric(button.dataset.id);
  if(id==='run-state'){runFilter=chartPick(button.dataset.id);refreshChart(button);return}
  if(id==='developer-outcome'){developerOutcome=developerOutcome===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='developer-day'){developerDay=developerDay===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='remove-filter'){const key=button.dataset.id;if(key==='tool')tool='all';if(key==='severity')severity='all';if(key==='finding')findingFilter='all';if(key==='run')runFilter='all';if(key==='developer-outcome')developerOutcome='all';if(key==='developer-day')developerDay='all';render();return}
  if(['ar','en','light','dark'].includes(id)){changeAppearance(id);return}
  if(id==='rail-approve'){qaTab=null;await selectRelease(button.dataset.id);app.querySelector('[data-action="approve"]')?.click();return}
  if(id==='qa-tab'){qaTab=button.dataset.id;render();return}
  if(id==='req')return reqModal(button.dataset.id);
  if(id==='account-menu'){const menu=button.nextElementSibling;menu.hidden=!menu.hidden;button.setAttribute('aria-expanded',String(!menu.hidden));return}
  if(id==='logout'){try{await api('/api/logout',{})}catch{/* the session is already gone: leave anyway */}requestNumber++;profile=release=null;threads=[];selectedThread=null;history.replaceState(null,'','/');render();return}
  if(id==='thread'){
    const key=button.dataset.id;
    selectedThread=key;
    const thread=threads.find(item=>item.id===key);
    if(thread)thread.unread=false;
    render();
    await api('/api/threads/'+encodeURIComponent(key)+'/read',{});
    return;
  }
  if(id==='delete-account')return confirmAccountDeletion(button.dataset.id);
  if(id==='edit-account')return editAccount(button.dataset.id);
  if(id==='clear-admin-search'){adminQuery='';render();app.querySelector('#admin-search input')?.focus();return}
  if(id==='new-admin-thread')return startAdminThread();
  if(id==='adjust-review-deadline')return adjustReviewDeadline(button.dataset.id);
  if(id==='approve-review-request'||id==='reject-review-request'){
    button.disabled=true;
    try{
      await api('/api/threads/'+encodeURIComponent(button.dataset.id)+'/review-decision',{decision:id==='approve-review-request'?'approve':'reject'});
      threads=await api('/api/threads');
      render();
    }finally{button.disabled=false}
    return;
  }
  if(!release)return;
  if(id==='queue'||id==='returned-build'){qaTab=null;if(dialog.open)dialog.close();await selectRelease(button.dataset.id);if(id==='returned-build')modal(copy('سبب الإرجاع','Return reason'),decisionList());return}
  if(id==='new-exception')return startExceptionRequest(button.dataset.id);
  if(id==='exception-refused'){
    const f=release.findings.find(x=>x.fingerprint===button.dataset.id);
    const why=f&&f.severity==='high'?copy('هذي ثغرة عالية الخطورة، وما تُستثنى. عالجها وارفع تعديلًا على نفس الطلب، ويعيد يَقِـــظ الفحص تلقائيًا.','This is a high-severity finding and cannot be excepted. Fix it and push a change to the same request; Yaqidh re-checks automatically.')
      :copy('هذي ثغرة منخفضة الخطورة، وما تمنع الإطلاق، فما تحتاج استثناء.','This is a low-severity finding. It does not block the release, so it needs no exception.');
    return modal(copy('طلب استثناء','Request an exception'),'<p>'+why+'</p><p class="muted">'+copy('الاستثناء متاح فقط للثغرات المتوسطة، وقراره لمراجع الأمن.','Exceptions are only for medium findings, and the security reviewer decides.')+'</p>');
  }
  if(id==='new-thread')return startThread(button.dataset.id||'');
  if(id==='sample-approved')return selectRelease(sampleBuild('approved'));
  if(id==='sample-issue'||id==='sample-ready')return selectRelease(sampleBuild(id==='sample-issue'?'issue':'ready'));
  if(id==='clear'||id==='bar'||id==='finding-group'){if(id==='clear'){tool='all';severity='all';findingFilter='all';runFilter='all';developerOutcome='all';developerDay='all'}else if(id==='bar')severity=severity===button.dataset.id?'all':button.dataset.id;else findingFilter=findingFilter===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='finding')return findingModal(button.dataset.id);
  if(id==='runs')return openRuns();
  if(id==='next-stage')return modal(copy('مرحلة الأمن','Security stage'),'<p>'+copy('تعرض لوحة الجودة فحوصات المرحلة الأولى وقرارها. يتابع مراجع الأمن فحوصات المرحلة الثانية بعد انتقال التعديل.','The QA dashboard shows first-stage checks and the QA decision. The security reviewer handles second-stage checks after the change advances.')+'</p>');
  if(id==='decisions')return modal(copy('سجل القرار البشري','Human decision log'),decisionList());
  if(id==='build')return modal(copy('هوية البناء','Build identity'),'<p>'+mon('PR #'+release.pr+' · Build #'+release.build+' · '+release.commit)+'</p>');
  if(id==='previous-qa'){
    const qa=release.previousQA;
    return modal(copy('موافقة الجودة للقراءة','Read-only QA decision'),qa?'<p>'+statusText(qa.decision)+' · '+safe(demoText(qa.by))+' · '+mon(release.commit)+'</p><p>'+safe(demoText(qa.reason))+'</p>':'<p>—</p>');
  }
  if(id==='prior')return selectRelease(release.prior.id);
  if(id==='evidence'){
    return modal(copy('ملف الأدلة','Evidence')+' · '+safe(buildName(release.build)),'<p>'+stageText(release.stage)+' · '+outcomeText()+'</p><p>'+mon(release.commit)+'</p>'
      +'<p>'+Object.entries(release.toolVersions).map(([key,value])=>safe(versionName(key))+' · '+mon(versionValue(value))).join(' ')+'</p>'
      +'<a class="action" href="/api/releases/'+encodeURIComponent(release.id)+'/evidence">'+copy('تصدير الأدلة المصرّح بها','Export authorized evidence')+'</a>');
  }
  if(id==='approve'){
    const key=release.id;
    const updated=await api('/api/releases/'+encodeURIComponent(key)+'/decision',{decision:'approve',reason:copy('موافقة','Approved'),commit:release.commit});
    if(release?.id===key){release=updated;render()}
    notify(copy('تمت الموافقة','Approved'));
    return;
  }
  if(id==='reject'){
    return modal(id==='approve'?copy('موافقة','Approve'):copy('إرجاع الطلب','Return request'),
      '<p>'+safe(requestName(release.pr))+' · '+mon(release.commit)+'</p><form id="decision-form" data-choice="'+id+'" data-release="'+safe(release.id)+'" data-commit="'+safe(release.commit)+'">'
      +'<label class="field">'+copy('السبب','Reason')+'<textarea name="reason" required minlength="3" maxlength="1000"></textarea></label>'
      +'<button class="primary">'+(id==='reject'?copy('إرجاع الطلب','Return request'):copy('حفظ القرار','Save decision'))+'</button></form>');
  }
}
const metricTip=document.createElement('div');
metricTip.id='metric-tooltip';
metricTip.className='metric-tooltip';
metricTip.setAttribute('role','tooltip');
metricTip.hidden=true;
document.body.append(metricTip);
let tipTarget=null;
function hideMetricTip(){
  tipTarget?.removeAttribute('aria-describedby');
  tipTarget=null;
  metricTip.hidden=true;
}
function showMetricTip(button){
  const item=metricDetails.get(button.dataset.id);
  if(!item||dialog.open)return;
  if(tipTarget&&tipTarget!==button)hideMetricTip();
  tipTarget=button;
  metricTip.innerHTML='<b>'+safe(item.label)+'</b><span>'+copy('القيمة','Value')+' · '+safe(item.value)+'</span><span>'+safe(item.scope)+'</span>'
    +(item.rows.length?'<span>'+copy('السجلات المعروضة في التفاصيل','Records in the details')+' · '+item.rows.length+'</span>':'<span>'+copy('لا توجد سجلات في التفاصيل.','No records in the details.')+'</span>')
    +'<small>'+copy('اضغط لعرض التفاصيل','Select to view details')+'</small>';
  metricTip.hidden=false;
  button.setAttribute('aria-describedby',metricTip.id);
  const rect=button.getBoundingClientRect();
  const width=metricTip.offsetWidth,height=metricTip.offsetHeight;
  metricTip.style.left=Math.max(8,Math.min(rect.left+(rect.width-width)/2,innerWidth-width-8))+'px';
  metricTip.style.top=Math.max(8,rect.bottom+height+10<innerHeight?rect.bottom+8:rect.top-height-8)+'px';
}
app.addEventListener('pointerover',event=>{
  const button=event.target.closest('.metric[data-action="metric"]');
  if(button&&!button.contains(event.relatedTarget))showMetricTip(button);
});
app.addEventListener('pointerout',event=>{
  const button=event.target.closest('.metric[data-action="metric"]');
  if(button===tipTarget&&!button?.contains(event.relatedTarget)&&document.activeElement!==button)hideMetricTip();
});
app.addEventListener('focusin',event=>{
  const button=event.target.closest('.metric[data-action="metric"]');
  if(button)showMetricTip(button);
});
app.addEventListener('focusout',event=>{if(event.target===tipTarget)hideMetricTip()});
window.addEventListener('scroll',hideMetricTip,{passive:true});
window.addEventListener('resize',hideMetricTip);
document.addEventListener('keydown',event=>{if(event.key==='Escape')hideMetricTip()});

document.addEventListener('click',event=>{
  const button=event.target.closest('[data-action]');
  if(!button)return;
  button.setAttribute('aria-busy','true'); // the press shows at once, before the server answers
  handleAction(button).catch(()=>notify(copy('تعذّر تنفيذ الإجراء','Action could not be completed'))).finally(()=>{button.removeAttribute('aria-busy');if(profile&&profile.guide&&!String(button.dataset.action).startsWith('demo-'))demoPollNow()});
});
document.addEventListener('keydown',event=>{
  const target=event.target.closest('svg [data-action]');
  if(target&&(event.key==='Enter'||event.key===' ')){event.preventDefault();handleAction(target).catch(()=>notify(copy('تعذّر تنفيذ الإجراء','Action could not be completed')))}
});
app.addEventListener('change',event=>{
  const input=event.target;
  if(input.id==='demo-account'&&input.value)$('#sign-in input[name=account]').value=input.value;
  if(input.id==='admin-active'){adminActive=input.value;render();$('#'+input.id)?.focus()}
  if((input.id==='release-select'||input.classList.contains('request-pick'))&&input.value){qaTab=null;selectRelease(input.value).catch(()=>notify(copy('تعذر فتح البناء','Build could not be loaded')));}
  if(['tool-filter','severity-filter','finding-filter','run-filter'].includes(input.id)){
    if(input.id==='tool-filter')tool=input.value;else if(input.id==='severity-filter')severity=input.value;else if(input.id==='run-filter')runFilter=input.value;else findingFilter=input.value;
    render();$('#'+input.id)?.focus();
  }
});
document.addEventListener('submit',async event=>{
  event.preventDefault();
  const form=event.target;
  const data=Object.fromEntries(new FormData(form));
  const submit=form.querySelector('button');
  submit.disabled=true;
  try{
    if(form.id==='admin-search'){adminQuery=data.query.trim();render();app.querySelector('#admin-search input')?.focus();return}
    if(form.id==='sign-up'){await api('/api/signup',data);location.href='/login?account='+encodeURIComponent(data.account);return}
    if(form.id==='sign-in'){await api('/api/login',data);history.replaceState(null,'','/dashboard');await load()}
    if(form.id==='thread-reply'){await api('/api/threads/'+encodeURIComponent(form.dataset.id),data);threads=await api('/api/threads');render()}
    if(form.id==='admin-thread-new'){const result=await api('/api/threads',data);location.href='/communication?thread='+encodeURIComponent(result.id)}
    if(form.id==='exception-new'){
      const result=await api('/api/threads',{...data,subject:copy('طلب استثناء أمني','Security exception request'),requestType:'exception',release:form.dataset.release,finding:form.dataset.finding});
      location.href='/communication?thread='+encodeURIComponent(result.id);
    }
    if(form.id==='thread-new'){const result=await api('/api/threads',{...data,release:form.dataset.release,finding:form.dataset.finding});location.href='/communication?thread='+encodeURIComponent(result.id)}
    if(form.id==='account-delete'){await api('/api/company/accounts/delete',{account:form.dataset.id});dialog.close();await load();notify(copy('حُذف الحساب من قائمة المستخدمين.','The account was removed from the user list.'))}
    if(form.id==='account-edit'){await api('/api/company/accounts',{account:form.dataset.id,role:data.role,active:data.active==='on'});dialog.close();await load()}
    if(form.id==='review-deadline-form'){
      await api('/api/threads/'+encodeURIComponent(form.dataset.id)+'/review-decision',{decision:'approve',approvedDeadline:data.approvedDeadline});
      threads=await api('/api/threads');
      dialog.close();
      render();
    }
    if(form.id==='exception-form'){
      const key=form.dataset.release;
      const picked=form.dataset.finding?[form.dataset.finding]:new FormData(form).getAll('finding');
      if(!picked.length){notify(copy('اختاري ثغرة واحدة على الأقل','Pick at least one finding'));return}
      let updated=null;
      for(const fingerprint of picked)updated=await api('/api/releases/'+encodeURIComponent(key)+'/exception',{fingerprint,justification:data.justification||copy('قبلها مراجع الأمن','Accepted by the security reviewer')});
      if(release?.id===key){release=updated;dialog.close();render()}
      notify(copy('تم تسجيل الاستثناء','Exception recorded'));
    }
    if(form.id==='decision-form'){
      const key=form.dataset.release;
      const updated=await api('/api/releases/'+encodeURIComponent(key)+'/decision',{decision:form.dataset.choice,reason:data.reason,commit:form.dataset.commit});
      if(release?.id===key){release=updated;dialog.close();render()}
      notify(copy('تم تسجيل القرار','Decision recorded'));
    }
  }catch(e){
    if(form.id==='sign-up'){notify(e.message==='409'?copy('اسم المستخدم مستخدم، اختاري غيره.','That username is taken. Choose another one.'):copy('تأكدي: اسم المستخدم 3 أحرف أو أكثر (إنجليزي وأرقام وـ - _ .)، وكلمة المرور 10 أحرف أو أكثر.','Check: username 3+ characters (English letters, digits, - _ .) and password 10+ characters.'));submit.disabled=false;return}
    notify(e.message==='401'?copy('بيانات الدخول غير صحيحة أو انتهت الجلسة','Invalid credentials or expired session'):
      e.message==='409'?copy('القرار غير متاح على هذا التعديل','Decision unavailable for this commit'):copy('تعذر حفظ الطلب','Request could not be saved'));
  }finally{submit.disabled=false}
});
setAppearance();
render();
load().catch(()=>notify(copy('تعذر تحميل الداشبورد','Dashboard could not be loaded')));
setInterval(refreshQAReviewAlerts,10000);
setInterval(()=>refreshData(false),20000);

function rescanHistory(f){
  if(profile.role!=='qa')return '';
  const events=((release.log||{}).entries||[]).filter(e=>(e.event==='scan'||e.event==='rescan')&&(e.data||{}).stage==='qa');
  if(!events.length)return '';
  const state=(e,i)=>{const d=e.data||{};
    if(e.event==='scan')return copy('ظهرت المشكلة','Problem found');
    if((d.closed||[]).includes(f.fingerprint))return copy('انحلّت','Fixed');
    if((d.still_open||[]).includes(f.fingerprint))return copy('ما زالت مفتوحة','Still open');
    if((d.new||[]).includes(f.fingerprint))return copy('ظهرت من جديد','Appeared again');
    return '—'};
  const times=events.length;
  return '<div class="note"><b>'+copy('إعادة الفحص','Re-checks')+'</b><p>'+copy('فُحص هذا الطلب','This request was checked')+' '+times+' '+copy(times===1?'مرة':'مرات',times===1?'time':'times')+'. '+copy('نتيجة هذه المشكلة في كل فحص:','This problem in each check:')+'</p><ol>'
    +events.map((e,i)=>'<li>'+copy('الفحص رقم','Check')+' '+(i+1)+' · '+mon(String(e.time).slice(0,16).replace('T',' '))+' · <b>'+safe(state(e,i))+'</b></li>').join('')+'</ol></div>';
}
