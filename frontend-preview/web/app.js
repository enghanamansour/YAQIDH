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

const requestedSample=new URLSearchParams(location.search).get('sample');
const FINDINGS_SHOWN=8;let showAllFindings=false;let booting=true; // until the session is known, a private page shows a loading line, not the login form
let profile=null,release=null,tool='all',severity='all',findingFilter='all',runFilter='all',adminDay='all',developerOutcome='all',developerDay='all';
let requestNumber=0;
const roleNames=role=>({
  developer:copy('المطور','Developer'),
  qa:copy('مراجع الجودة','QA reviewer'),
  security:copy('مراجع الأمن السيبراني','Security reviewer'),'company-admin':copy('مسؤول إدارة الشركة','Company admin'),
}[role]||role);
const projectName=id=>id==='portal'?copy('بوابة الخدمات','Services Portal'):id==='research'?copy('مشروع المختبر','Lab project'):id;
const toolName=id=>({semgrep:copy('سيم غريب','Semgrep'),trivy:copy('تريفي','Trivy'),playwright:copy('بلاي رايت','Playwright')}[id]||id);
const severityName=id=>({
  high:copy('مرتفعة','HIGH'),low:copy('منخفضة','LOW'),medium:copy('متوسطة','Medium'),
  critical:copy('حرجة','Critical'),info:copy('معلومة','Info'),unknown:copy('غير محددة','Unknown')
}[id]||'—');
const accountName=id=>({
  developer:copy('حساب المطور التجريبي','developer'),
  qa:copy('حساب الجودة التجريبي','qa'),
  security:copy('حساب الأمن التجريبي','security'),
  'company-admin':copy('حساب إدارة الشركة التجريبي','company-admin'),

}[id]||id);
const versionName=id=>({
  'semgrep-rules':copy('قواعد سيم غريب','Semgrep rules'),
  'trivy-db':copy('قاعدة بيانات تريفي','Trivy database'),
  trivy:toolName('trivy')
}[id]||id);
const versionValue=value=>['demo-rules','demo-db'].includes(value)?copy('نسخة تجريبية',value):value;
const buildName=id=>copy('البناء رقم '+id,'Build #'+id);
const requestName=id=>copy('طلب الدمج رقم '+id,'PR #'+id);
const branchName=id=>id==='staging'?copy('فرع ما قبل الإطلاق','staging'):id;
const findingName=f=>({
  'demo.sql-query':copy('استعلام يستخدم مدخلات الطلب','Query uses request input'),
  'demo.order-confirmation':copy('لم يظهر تأكيد الطلب','Order confirmation missing'),
  'DEMO-ADVISORY-01':copy('ملاحظة في مكتبة مستخدمة','Dependency finding'),
  'DEMO-ADVISORY-02':copy('ملاحظة مستثناة في مكتبة','Excepted dependency finding')
}[f.rule]||f.rule||f.fingerprint);
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
  document.title=copy('يقظ','YAQIDH');
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

function introduction(){
  return '<section class="intro"><div class="hello"><div><h1>'+roleNames(profile.role)+'</h1><small>'+copy('معاينة محلية · بيانات تشغيل ومستخدمون تجريبيون','Local preview · Demo runs and users')+'</small></div>'+'</div>'+badge(safe(accountName(profile.role)))+'</section>';
}
let adminProject='all',adminRole='all',adminActive='all',adminStage='all';



function outcomeText(){return release.outcome?(release.outcome.result==='pass'?copy('اجتاز','PASS'):copy('أخفق','FAIL')):release.runs.some(run=>run.state==='error')?copy('تعطل فحص مطلوب','Required check failed to run'):copy('بانتظار نتيجة صالحة','Awaiting a valid result')}
function stageText(stage){return stage==='qa'?copy('مسار الجودة · المرحلة الأولى','QA pipeline · Stage 1'):copy('مسار الأمن · المرحلة الثانية','Security pipeline · Stage 2')}
function statusText(status){return ({
  open:copy('تحتاج معالجة','Needs remediation'),fixed:copy('مُصلحة','Fixed'),excepted:copy('مستثناة','Excepted'),
  completed:copy('مكتمل','Completed'),error:copy('تعطل','Failed to run'),
  approve:copy('موافقة مسجلة','Approval recorded'),reject:copy('إرجاع مع السبب','Returned with reason')
})[status]||copy('بانتظار القرار','Awaiting decision')}
function lastDecision(){return release.decisions.at(-1)}
function decisionText(){return statusText(lastDecision()?.decision)}
function displayReason(reason){
  if(reason==='no blocking findings')return copy('لا توجد ملاحظات مانعة وفق السياسة','No blocking findings');
  const count=reason.match(/^(\d+) high open$/);
  return count?copy(count[1]==='1'?'ملاحظة واحدة مرتفعة الخطورة تمنع التقدّم':count[1]+' ملاحظات مرتفعة الخطورة تمنع التقدّم',count[1]+' blocking HIGH findings'):safe(reason);
}
function sampleBuild(sample){if(profile.role==='developer')return sample==='issue'?'portal-133':'portal-129';if(sample==='approved')return profile.role==='qa'?'portal-129':'portal-135';return profile.role==='qa'?(sample==='issue'?'portal-133':'portal-132'):(sample==='issue'?'portal-128':'portal-134')}
function findingState(f){return f.closure?.result==='closed'?copy('إغلاق مثبت','Verified closed'):f.closure?.result==='still_open'?copy('ما زالت تحتاج معالجة','Still needs remediation'):statusText(f.status)}
function findingGroup(f){return f.closure?.result==='closed'?'fixed':f.status==='excepted'?'excepted':'open'}
function matched(){return release.findings.filter(f=>(runFilter==='all'||release.runs.filter(run=>run.tool===f.tool).length===1&&release.runs.some(run=>run.tool===f.tool&&run.state===runFilter))&&(findingFilter==='all'||findingGroup(f)===findingFilter)&&(tool==='all'||tool===f.tool)&&(severity==='all'||severity===f.severity))}


let threads=[],selectedThread=null;
const unreadCount=()=>threads.filter(thread=>thread.unread).length;

function render(){
  hideMetricTip();
  metricDetails.clear();
  const page=location.pathname;
  if(booting&&!['/','/signup','/login'].includes(page)){app.innerHTML=header()+'<div class="public-shell"><main><p class="muted">'+copy('جارٍ التحميل…','Loading…')+'</p></main></div>';return}
  if(page==='/'){app.innerHTML=header()+landing();if(location.hash==='#about')document.getElementById('about').scrollIntoView();return}
  const content=page==='/signup'?signup():!profile?login():page==='/communication'?communicationView():page==='/exceptions'?exceptionsView():'<main>'+introduction()+(profile.role==='company-admin'?adminView():dashboardView())+'</main>';
  app.innerHTML=header()+(profile?sidebar():'')+'<div class="'+(profile?'shell':'public-shell')+'">'+content+'</div>';
}
async function selectRelease(id){
  const turn=++requestNumber;
  const next=await api('/api/releases/'+encodeURIComponent(id));
  if(turn!==requestNumber)return;
  release=next;tool='all';severity='all';findingFilter='all';runFilter='all';showAllFindings=false;render();
}
async function load(){
  if(location.pathname==='/about')history.replaceState(null,'','/#about');
  try{profile=await api('/api/dashboard')}catch(e){if(!['401','403'].includes(e.message))throw e;profile=null;if(!['/','/about','/login','/signup'].includes(location.pathname))history.replaceState(null,'','/login'+location.search)}
  if(profile&&['/login','/dashboard','/admin'].includes(location.pathname)){const destination=profile.role==='company-admin'?'/admin':'/dashboard';if(location.pathname!==destination)history.replaceState(null,'',destination+location.search)}
  booting=false;
  threads=profile?await api('/api/threads'):[];
  if(location.pathname==='/communication'){selectedThread=new URLSearchParams(location.search).get('thread')||threads[0]?.id||null;render();return}
  if(profile?.releases?.length){
    const preferred=sampleBuild(requestedSample==='ready'?'ready':requestedSample==='issue'?'issue':profile.role==='qa'?'ready':'issue');
    await selectRelease((profile.releases.find(r=>r.id===new URLSearchParams(location.search).get('build'))||profile.releases.find(r=>r.id===preferred)||profile.releases[0]).id);
  }else{release=null;render()}
}
function openRuns(){
  const records=release.runs.map(r=>'<p>'+safe(toolName(r.tool))+' · '+badge(statusText(r.state),r.state==='completed'?'good':'bad')+' · '+copy('سجل تشغيل تجريبي','Demo run record')+'</p>').join('');
  modal(copy('تشغيلات الأدوات','Tool runs'),records||'<p>'+copy('لا توجد سجلات تشغيل لهذه المرحلة.','No run records for this stage.')+'</p>');
}
function decisionList(){
  return release.decisions.map(d=>'<p><b>'+statusText(d.decision)+'</b> · '+safe(accountName(demoText(d.by)))+' · '+mon(d.timestamp.slice(0,16))+'<br>'+safe(demoText(d.reason))+'</p>').join('')||'<p>'+copy('لا يوجد قرار مسجّل.','No decision recorded.')+'</p>';
}
function findingModal(id){
  const f=release.findings.find(item=>item.fingerprint===id);
  if(!f)return;
  const flags={closed:copy('إغلاق مثبت','Verified closure'),still_open:copy('ما زالت تحتاج معالجة','Still needs remediation'),new:copy('ملاحظة جديدة','New finding'),new_from_db_update:copy('جديدة بسبب تحديث قاعدة تريفي','New after Trivy DB update'),reopened:copy('عادت بعد الإغلاق','Reopened')};
  const history=Object.entries(flags).filter(([key])=>release.verification?.[key]?.includes(id)).map(([,label])=>label).join(' · ');
  modal(copy('دليل الملاحظة','Finding evidence'),'<div class="details-grid">'
    +detail(copy('البصمة','Fingerprint'),mon(f.fingerprint))+(profile.role==='developer'?'':detail(copy('الأداة','Tool'),safe(toolName(f.tool))))
    +detail(copy('خطورة يقظ / التصنيف الأصلي','YAQIDH severity / original rating'),safe(severityName(f.severity)+' / '+severityName(f.reported_as)))
    +detail(copy('القاعدة والموقع','Rule and location'),mon(f.rule)+' · '+mon(f.location))
    +detail(copy('المكوّن وإصداره','Component and version'),mon(f.component||'—'))
    +detail(copy('حالة الملاحظة','Finding status'),safe(statusText(f.status)))
    +detail(copy('إعادة التحقق','Reverification'),safe(history||(f.closure?findingState(f):copy('لا يوجد دليل إعادة فحص','No rescan evidence'))))
    +detail(copy('قبل / بعد','Before / after'),release.prior&&history?mon('#'+release.prior.build+' → #'+release.build):'—')+'</div>'
    +(id==='playwright-demo-001'?'<p class="note">'+copy('المتوقع: يظهر تأكيد الطلب بعد الإرسال. الفعلي: لم يظهر التأكيد في عينة الاختبار.','Expected: order confirmation appears after submission. Actual: the confirmation was absent in the demo run.')+'</p>':'')
    +(f.closure?'<p>'+copy('وقت تحقق الإغلاق','Verification time')+' '+mon(f.closure.timestamp)+'</p>':'')
    +(f.exception?'<p class="note"><b>'+copy('استثناء مسجل','Recorded exception')+'</b><br>'+safe(demoText(f.exception.justification))+' · '+safe(demoText(f.exception.approved_by))+'</p>':'')
    +(profile.role==='security'||(profile.role==='developer'&&release.stage==='security'&&!release.blockerIds.includes(f.fingerprint))?'':'<p>'+action('new-thread',release.stage==='security'?copy('طلب تمديد المهلة','Request deadline extension'):copy('ناقش هذه الملاحظة','Discuss this finding'),'data-id="'+safe(f.fingerprint)+'"')+'</p>')
    +(f.explanation?'<p class="note"><b>'+copy('شرح يقظ','YAQIDH explanation')+'</b><br>'+safe(demoText(f.explanation.text))+'</p>':''));
}
async function handleAction(button){
  const id=button.dataset.action;
  if(id==='close')return dialog.close();
  if(id==='metric')return showMetric(button.dataset.id);
  if(id==='run-state'){runFilter=chartPick(button.dataset.id);refreshChart(button);return}
  if(id==='developer-outcome'){developerOutcome=developerOutcome===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='developer-day'){developerDay=developerDay===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='admin-day'){adminDay=adminDay===button.dataset.id?'all':button.dataset.id;refreshChart(button);return}
  if(id==='admin-clear'){adminDay=runFilter=adminProject=adminRole=adminActive=adminStage='all';render();return}
  if(id==='remove-filter'){const key=button.dataset.id;if(key==='tool')tool='all';if(key==='severity')severity='all';if(key==='finding')findingFilter='all';if(key==='run')runFilter='all';if(key==='day')adminDay='all';if(key==='developer-outcome')developerOutcome='all';if(key==='developer-day')developerDay='all';render();return}
  if(['ar','en','light','dark'].includes(id)){changeAppearance(id);return}
  if(id==='logout'){await api('/api/logout',{});requestNumber++;profile=release=null;threads=[];selectedThread=null;history.replaceState(null,'','/');render();return}
  if(id==='thread'){
    const key=button.dataset.id;
    selectedThread=key;
    const thread=threads.find(item=>item.id===key);
    if(thread)thread.unread=false;
    render();
    await api('/api/threads/'+encodeURIComponent(key)+'/read',{});
    return;
  }
  if(id==='account-approve'||id==='account-reject'){await api('/api/company/requests',{account:button.dataset.id,decision:id==='account-approve'?'approve':'reject'});await load();return}
  if(id==='delete-account')return confirmAccountDeletion(button.dataset.id);
  if(id==='admin-message')return startThread('',button.dataset.id);
  if(id==='edit-account')return editAccount(button.dataset.id);
  if(!release)return;
  if(id==='jump'){document.getElementById(button.dataset.target)?.scrollIntoView({behavior:'smooth',block:'start'});return}
  if(id==='toggle-findings'){showAllFindings=!showAllFindings;render();return}
  if(id==='queue'||id==='returned-build'){if(dialog.open)dialog.close();await selectRelease(button.dataset.id);if(id==='queue')document.querySelector('.summary')?.scrollIntoView({behavior:'smooth',block:'start'});if(id==='returned-build')modal(copy('سبب الإرجاع','Return reason'),decisionList());return}
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
  if(id==='approve'||id==='reject'){
    return modal(id==='approve'?copy('تسجيل الموافقة','Record approval'):copy('إرجاع التعديل','Return change'),
      '<p>'+safe(buildName(release.build))+' · '+mon(release.commit)+'</p><form id="decision-form" data-choice="'+id+'" data-release="'+safe(release.id)+'" data-commit="'+safe(release.commit)+'">'
      +'<label class="field">'+copy('السبب','Reason')+'<textarea name="reason" required minlength="3" maxlength="1000"></textarea></label>'
      +'<button class="primary">'+copy('حفظ القرار التجريبي','Save demo decision')+'</button></form>');
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
  if(button)handleAction(button).catch(()=>notify(copy('تعذّر تنفيذ الإجراء','Action could not be completed')));
});
document.addEventListener('keydown',event=>{
  const target=event.target.closest('svg [data-action]');
  if(target&&(event.key==='Enter'||event.key===' ')){event.preventDefault();handleAction(target).catch(()=>notify(copy('تعذّر تنفيذ الإجراء','Action could not be completed')))}
});
app.addEventListener('change',event=>{
  const input=event.target;
  if(input.id==='demo-account'&&input.value)$('#sign-in input[name=account]').value=input.value;
  if(['admin-project','admin-role','admin-active','admin-stage'].includes(input.id)){if(input.id==='admin-project')adminProject=input.value;else if(input.id==='admin-role')adminRole=input.value;else if(input.id==='admin-active')adminActive=input.value;else adminStage=input.value;render();$('#'+input.id)?.focus()}
  if(input.id==='release-select')selectRelease(input.value).catch(()=>notify(copy('تعذر فتح البناء','Build could not be loaded')));
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
    if(form.id==='sign-up'){await api('/api/signup',data);form.reset();notify(copy('أُرسل طلبك إلى مسؤول الشركة للمراجعة.','Your request was submitted for company approval.'));return}
    if(form.id==='sign-in'){await api('/api/login',data);history.replaceState(null,'','/dashboard');await load()}
    if(form.id==='thread-reply'){await api('/api/threads/'+encodeURIComponent(form.dataset.id),data);threads=await api('/api/threads');render()}
    if(form.id==='thread-new'){const result=await api('/api/threads',{...data,release:form.dataset.release,finding:form.dataset.finding});location.href='/communication?thread='+encodeURIComponent(result.id)}
    if(form.id==='account-delete'){await api('/api/company/accounts/delete',{account:form.dataset.id});dialog.close();await load();notify(copy('حُذف الحساب من قائمة المستخدمين.','The account was removed from the user list.'))}
    if(form.id==='account-edit'){await api('/api/company/accounts',{account:form.dataset.id,role:data.role,active:data.active==='on',assigned:new FormData(form).getAll('projects').length>0,projects:new FormData(form).getAll('projects')});dialog.close();await load()}
    if(form.id==='exception-form'){
      const key=form.dataset.release;
      const updated=await api('/api/releases/'+encodeURIComponent(key)+'/exception',{fingerprints:new FormData(form).getAll('finding'),justification:data.justification});
      if(release?.id===key){release=updated;render()}
      notify(copy('سُجّل قرار الاستثناء مع تبريرك','The exception decision was recorded with your reason'));
    }
    if(form.id==='decision-form'){
      const key=form.dataset.release;
      const updated=await api('/api/releases/'+encodeURIComponent(key)+'/decision',{decision:form.dataset.choice,reason:data.reason,commit:form.dataset.commit});
      if(release?.id===key){release=updated;dialog.close();render()}
      notify(copy('تم تسجيل القرار التجريبي','Demo decision recorded'));
    }
  }catch(e){
    notify(e.message==='401'?copy('بيانات الدخول غير صحيحة أو انتهت الجلسة','Invalid credentials or expired session'):
      e.message==='409'?copy('القرار غير متاح على هذا التعديل','Decision unavailable for this commit'):copy('تعذر حفظ الطلب','Request could not be saved'));
  }finally{submit.disabled=false}
});
setAppearance();
render();
load().catch(()=>{booting=false;render();notify(copy('تعذر تحميل الداشبورد','Dashboard could not be loaded'))});
