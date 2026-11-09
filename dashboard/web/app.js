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
function metric(label,value,tone='',rows=[],scope='',format=safe){
  const key=String(metricDetails.size);
  metricDetails.set(key,{label,value,rows,scope,format});
  return '<button type="button" class="metric '+tone+'" data-action="metric" data-id="'+key+'"><strong>'+value+'</strong><span>'+label+'</span><small>'+copy('عرض التفاصيل','View details')+'</small></button>';
}
function showMetric(key){
  hideMetricTip();
  const entry=metricDetails.get(key);
  if(!entry)return;
  const body=entry.rows.length?'<ul class="metric-records">'+entry.rows.map(row=>'<li>'+entry.format(row)+'</li>').join('')+'</ul>':'<p class="muted">'+copy('لا توجد سجلات مطابقة لهذا المؤشر.','No records match this metric.')+'</p>';
  modal(entry.label,'<p class="metric-scope">'+safe(entry.scope)+'</p><p><b>'+copy('القيمة المعروضة','Displayed value')+'</b> '+safe(entry.value)+'</p>'+body);
}
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
function header(){
  const nav=(href,label)=>'<a href="'+href+'"'+(location.pathname===href?' aria-current="page"':'')+'>'+label+'</a>';
  const ar=document.documentElement.lang==='ar', theme=document.documentElement.dataset.theme;
  const toggle=(id,label,active)=>action(id,label,'aria-pressed="'+active+'"');
  return '<header class="top"><div class="top-navigation"><a class="top-logo" href="/" aria-label="'+copy('يقظ · الرئيسية','YAQIDH · Home')+'"><img class="brand" alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"></a><nav aria-label="'+copy('التنقل العام','Main navigation')+'">'+nav('/',copy('الرئيسية','Home'))+nav('/about',copy('عن يقظ','About YAQIDH'))+'</nav></div>'
    +'<div class="toolbar"><div class="top-control" role="group" aria-label="'+copy('اللغة','Language')+'">'+toggle('ar',copy('العربية','Arabic'),ar)+toggle('en',copy('الإنجليزية','English'),!ar)+'</div>'
    +'<div class="top-control" role="group" aria-label="'+copy('المظهر','Appearance')+'">'+toggle('light',copy('☀ فاتح','☀ Light'),theme==='light')+toggle('dark',copy('☾ غامق','☾ Dark'),theme==='dark')+'</div></div></header>';
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

function authClose(){
  return '<a class="auth-close" href="/" aria-label="'+copy('إلغاء والعودة إلى الرئيسية','Cancel and return home')+'" title="'+copy('إلغاء والعودة إلى الرئيسية','Cancel and return home')+'">×</a>';
}
function login(){
  const requested=new URLSearchParams(location.search).get('account')||'';
  const accounts=['developer','qa','security','company-admin'].map(id=>'<option '+(id===requested?'selected ':'')+'value="'+id+'">'+roleNames(id)+'</option>').join('');
  return '<section class="login">'+authClose()+'<h1>'+copy('تسجيل الدخول إلى يقظ','Sign in to YAQIDH')+'</h1><p class="muted">'+copy('معاينة محلية بحسابات وبيانات تجريبية','Local preview with demo accounts and data')+'</p>'
    +'<form id="sign-in"><label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" autocomplete="username" value="'+safe(requested)+'" required></label><label class="field">'+copy('حساب عرض (اختياري)','Demo account (optional)')+'<select id="demo-account"><option value="">—</option>'+accounts+'</select></label>'
    +'<label class="field">'+copy('كلمة المرور','Password')+'<input name="password" type="password" required autocomplete="current-password"></label>'
    +'<button class="primary">'+copy('تسجيل الدخول','Sign in')+'</button></form><p>'+copy('كلمة مرور العرض','Demo password')+' '+mon('YaqidhDemo-2026')+'</p><a href="/signup">'+copy('إنشاء حساب جديد','Create an account')+'</a></section>';
}
function introduction(){
  return '<section class="intro"><div><h1>'+roleNames(profile.role)+'</h1><small>'+copy('معاينة محلية · بيانات تشغيل ومستخدمون تجريبيون','Local preview · Demo runs and users')+'</small></div>'+badge(safe(accountName(profile.role)))+'</section>';
}
let adminProject='all',adminRole='all',adminActive='all',adminStage='all';
function adminSelect(id,label,current,options){
  return '<label>'+label+'<select id="'+id+'"><option value="all">'+copy('الكل','All')+'</option>'+options.map(([value,text])=>'<option value="'+value+'" '+(current===value?'selected':'')+'>'+text+'</option>').join('')+'</select></label>';
}
function adminAudit(){
  return '<section class="panel"><h2>'+copy('سجل تغييرات الصلاحيات','Access change log')+'</h2>'
    +(profile.audit.length?profile.audit.slice().reverse().map(item=>'<p>'+safe(accountName(item.target))+' · '+roleNames(item.role)+' · '+(item.action==='deleted'?copy('حُذف الحساب','Account deleted'):item.active?copy('نشط','Active'):copy('معطّل','Disabled'))+' · '+(item.assigned?copy('مسند إلى المشروع','Assigned to project'):copy('أُلغي الإسناد','Unassigned'))+' · '+mon(item.at.slice(0,16).replace('T',' '))+'</p>').join(''):'<p>'+copy('لا توجد تغييرات مسجّلة.','No changes recorded.')+'</p>')+'</section>';
}
function landing(){
  return '<main class="landing"><div><img alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"><div class="actions"><a class="action primary" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a><a class="action" href="/signup">'+copy('إنشاء حساب','Create account')+'</a></div></div><footer>'+ (profile?'<a href="'+(profile.role==='company-admin'?'/admin':'/dashboard')+'">'+copy('لوحة المتابعة','Dashboard')+'</a> · ':'')+'<a href="/about">'+copy('عن يقظ','About YAQIDH')+'</a></footer></main>';
}
function signup(){
  return '<section class="login">'+authClose()+'<h1>'+copy('إنشاء حساب','Create account')+'</h1><p>'+copy('يراجع مسؤول الشركة طلبك قبل تفعيل الحساب.','Your company admin reviews your request before activation.')+'</p><form id="sign-up">'
    +'<label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" required autocomplete="username" placeholder="example-user"></label>'
    +'<label class="field">'+copy('كلمة المرور (١٠ أحرف على الأقل)','Password (10 characters minimum)')+'<input type="password" name="password" minlength="10" maxlength="128" required autocomplete="new-password"></label>'
    +'<label class="field">'+copy('الدور المطلوب','Requested role')+'<select name="role">'+['developer','qa','security'].map(id=>'<option value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'
    +'<label class="field">'+copy('رمز دعوة الشركة','Company invitation code')+'<input name="invitation" required></label><button class="primary">'+copy('إرسال طلب الحساب','Submit account request')+'</button></form><p class="muted">'+copy('رمز دعوة المعاينة','Demo invitation code')+' '+mon('YAQIDH-DEMO')+'</p><a href="/login">'+copy('تسجيل الدخول','Sign in')+'</a></section>';
}
function registrationQueue(){
  return '<section class="panel"><div class="section-head"><h2>'+copy('طلبات إنشاء الحساب','Account requests')+'</h2>'+badge(profile.requests.length+' '+copy('معلّقة','pending'),'wait')+'</div>'
    +(profile.requests.map(item=>'<div class="request-row"><div>'+mon(item.name)+' · '+roleNames(item.role)+'</div><div class="actions">'
    +action('account-approve',copy('تفعيل وإسناد للمشروع','Activate and assign'),'class="primary" data-id="'+safe(item.name)+'"')
    +action('account-reject',copy('رفض الطلب','Reject request'),'data-id="'+safe(item.name)+'"')+'</div></div>').join('')||'<p>'+copy('لا توجد طلبات معلقة.','No pending requests.')+'</p>')+'</section>';
}
function developerPriority(){
  const returned=profile.releases.filter(item=>item.returnReason);
  return '<section class="panel dev-priority"><h2>'+copy('يحتاج إجراء منك','Needs your action')+'</h2>'
    +(returned.length?returned.map(item=>'<article class="note dev-return"><div><b>'+safe(requestName(item.pr))+'</b> · '+safe(stageText(item.active))+'<p>'+safe(demoText(item.returnReason))+'</p><small>'+copy('عالج الملاحظة وارفع التعديل لإعادة الفحص.','Address the finding and resubmit the change for checking.')+'</small></div>'
    +action('returned-build',copy('عرض سبب الإرجاع','View return reason'),'data-id="'+safe(item.id)+'"')+'</article>').join(''):'<p>'+copy('لا توجد تعديلات معادة إليك.','No changes have been returned to you.')+'</p>')+'</section>';
}
function assignedBuildTable(rows){
  return '<section class="panel"><h2>'+copy('التعديلات المسندة','Assigned changes')+'</h2><div class="table-wrap"><table><thead><tr><th>'+copy('طلب الدمج','Pull request')+'</th><th>'+copy('البناء','Build')+'</th><th>'+copy('المرحلة','Stage')+'</th><th>'+copy('الإجراء','Action')+'</th></tr></thead><tbody>'+rows.map(item=>'<tr><td>'+safe(requestName(item.pr))+'</td><td>'+safe(buildName(item.build))+'</td><td>'+safe(stageText(item.active))+'</td><td>'+action('queue',copy('عرض الملاحظات','View findings'),'data-id="'+safe(item.id)+'"')+'</td></tr>').join('')+'</tbody></table></div>'+(rows.length?'':'<p>'+copy('لا توجد تعديلات مطابقة.','No matching changes.')+'</p>')+'</section>';
}

function developerView(){
  if(!release)return '<section class="panel">'+copy('لا توجد تعديلات مسندة إلى حسابك.','No changes are assigned to your account.')+'</section>';
  const pending=matched().filter(f=>findingGroup(f)==='open');
  const fixed=matched().filter(f=>findingGroup(f)==='fixed');
  const dated=profile.releases.filter(item=>developerDay==='all'||item.day===developerDay);
  const assigned=dated.filter(item=>developerOutcome==='all'||(item.outcome||'pending')===developerOutcome);
  const returns=assigned.filter(item=>item.returnReason);
  const requests=[...new Map(assigned.map(item=>[item.pr,item])).values()];
  const counts=['pass','fail',null].map(id=>({state:id==='pass'?'completed':id==='fail'?'error':'pending',count:dated.filter(item=>item.outcome===id).length}));
  const rows=matched().map(f=>'<tr><td>'+safe(findingName(f))+'<br><small>'+mon(f.location)+'</small></td><td>'+findingState(f)+'</td><td>'+action('finding',copy('فتح الدليل','Open evidence'),'data-id="'+safe(f.fingerprint)+'"')+'</td></tr>').join('');
  return '<div class="developer-workspace">'+developerPriority()
    +'<section class="panel filters"><label>'+copy('طلب الدمج والبناء','Pull request and build')+'<select id="release-select">'+profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+safe(buildName(item.build))+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',copy('قيد التنفيذ','In progress')],['fixed',copy('مغلقة','Closed')],['excepted',copy('مستثناة','Excepted')]])
    +action('sample-issue',copy('تعديل معاد','Returned change'))+action('sample-ready',copy('تعديل عولج','Remediated change'))+action('decisions',copy('عرض قرار المراجع','View reviewer decision'))+'</section>'+chipRow([['finding',findingFilter,copy('حالة المعالجة','Remediation status')],['developer-outcome',developerOutcome,copy('نتائج الأبنية','Build outcomes')],['developer-day',developerDay,copy('اليوم','Day')+' · '+developerDay]],'clear')
    +'<div class="metric-row">'+metric(copy('طلبات الدمج المسندة','Assigned pull requests'),requests.length,'',requests,copy('طلبات دمج مميزة ضمن الأبنية المسندة المطابقة.','Distinct pull requests in the matching assigned builds.'),buildRecord)+metric(copy('تعديلات معادة للمعالجة','Returned changes'),returns.length,'bad',returns,copy('أبنية مسندة آخر قرار لها الإرجاع.','Assigned builds whose latest decision was a return.'),buildRecord)+metric(copy('تنتظر إعادة الفحص','Awaiting recheck'),pending.length,'wait',pending,buildScope(copy('ملاحظات مطابقة لم يثبت إغلاقها.','Matching findings awaiting verified closure.')),findingRecord)+metric(copy('إغلاقات مثبتة','Verified closures'),fixed.length,'good',fixed,buildScope(copy('ملاحظات مطابقة ثبت إغلاقها.','Matching findings with verified closure.')),findingRecord)+'</div>'
    +'<div class="role-charts">'+qaChart(matched(),copy('حالات المعالجة','Remediation status'))+toolRunChart(counts.flatMap(item=>Array.from({length:item.count},()=>item)),true)+'</div>'+adminTimeline(profile.releases.filter(item=>item.day&&(developerOutcome==='all'||(item.outcome||'pending')===developerOutcome)).map(item=>({day:item.day,state:item.outcome==='fail'?'error':item.outcome==='pass'?'completed':'pending'})),true)+assignedBuildTable(assigned)
    +'<section class="panel"><h2>'+copy('أدلة المعالجة','Remediation evidence')+'</h2>'+(rows?'<div class="table-wrap"><table><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الدليل','Evidence')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>'+copy('لا توجد ملاحظات مطابقة.','No matching findings.')+'</p>')+'</section></div>';
}

function adminTimeline(runs,developer=false){
  const heading=developer?copy('اتجاه نتائج الأبنية المسندة','Assigned build trend'):copy('اتجاه تشغيل الفحوصات','Check run trend');
  const totalLabel=developer?copy('إجمالي الأبنية','Total builds'):copy('إجمالي التشغيلات','Total runs');
  const failureLabel=developer?copy('أبنية أخفقت','Failed builds'):copy('تشغيلات متعطلة','Failed runs');
  const actionName=developer?'developer-day':'admin-day';
  const selectedDay=developer?developerDay:adminDay;
  const days=[...new Set(runs.map(run=>run.day).filter(Boolean))].sort();
  if(!days.length)return '<section class="panel admin-trend"><h2>'+heading+'</h2><p class="muted">'+copy('لا توجد تشغيلات مؤرخة في النطاق المحدد.','No dated runs match the selected scope.')+'</p></section>';
  const totals=days.map(day=>runs.filter(run=>run.day===day).length);
  const errors=days.map(day=>runs.filter(run=>run.day===day&&run.state==='error').length);
  const max=Math.max(2,...totals);
  const x=i=>days.length===1?300:43+i*518/(days.length-1);
  const y=n=>162-132*n/max;
  const poly=counts=>counts.map((n,i)=>x(i)+','+y(n)).join(' ');
  const scale=[0,Math.ceil(max/2),max].filter((value,index,list)=>list.indexOf(value)===index);
  return '<section class="panel admin-trend"><div class="section-head"><h2>'+heading+'</h2>'+badge(copy('سجل تجريبي مؤرخ','Dated demo history'))+'</div>'
    +'<p class="muted">'+ (developer?copy('الأبنية المسندة يوميًا حسب تاريخ سجل المعاينة. اختر يومًا لتصفية قائمة الأبنية.','Assigned builds by dated demo record. Select a day to filter the build list.'):copy('عدد التشغيلات يوميًا ضمن المشروع والمرحلة المختارين','Daily runs in the selected project and stage'))+'</p>'
    +'<svg class="admin-line" viewBox="0 0 600 202" role="img" aria-label="'+copy('التشغيلات والمتعطل حسب اليوم','Daily runs and failures')+'">'
    +scale.map(n=>'<path class="line-grid" d="M43 '+y(n)+'H561"/><text x="30" y="'+(y(n)+4)+'">'+n+'</text>').join('')
    +(days.length>1?'<polygon class="line-area" points="'+x(0)+',162 '+poly(totals)+' '+x(days.length-1)+',162"/>':'')
    +'<polyline class="line-total" points="'+poly(totals)+'"/><polyline class="line-errors" points="'+poly(errors)+'"/>'
    +days.map((day,i)=>'<g class="line-point" role="button" data-action="'+actionName+'" data-id="'+day+'" aria-pressed="'+(selectedDay===day)+'" tabindex="0" aria-label="'+day+' · '+totalLabel+' '+totals[i]+' · '+failureLabel+' '+errors[i]+'"><title>'+day+' · '+totalLabel+' '+totals[i]+' · '+failureLabel+' '+errors[i]+'</title><circle class="line-dot total" cx="'+x(i)+'" cy="'+y(totals[i])+'" r="4"/><circle class="line-dot error" cx="'+x(i)+'" cy="'+y(errors[i])+'" r="3"/><text x="'+x(i)+'" y="186">'+day.slice(5)+'</text></g>').join('')
    +'</svg><div class="actions"><span class="trend-key">'+totalLabel+'</span><span class="trend-key errors">'+failureLabel+'</span></div></section>';
}
function adminRunList(runs){
  const rows=runs.slice().sort((a,b)=>(b.day||'').localeCompare(a.day||'')).map(r=>
    '<tr><td>'+safe(toolName(r.tool))+'</td><td>'+safe(stageText(r.stage))+'</td><td>'+safe(projectName(r.project))+'</td><td>'
    +badge(statusText(r.state),r.state==='completed'?'good':r.state==='error'?'bad':'wait')+'</td><td>'+mon(r.day||'—')+'</td><td>'+action('admin-message',copy('مراسلة المطور','Message developer'),'data-id="'+safe(r.release)+'"')+'</td></tr>').join('');
  return '<section class="panel"><div class="section-head"><h2>'+copy('سجل التشغيلات المطابقة','Matching run records')+'</h2>'
    +badge(runs.length+' '+copy('تشغيل','runs'))+'</div><p class="muted">'+copy('مرتّب من الأحدث إلى الأقدم وفق الفلاتر الحالية.','Newest first, within the active filters.')+'</p>'
    +(rows?'<div class="table-wrap run-table"><table><thead><tr><th>'+copy('الأداة','Tool')+'</th><th>'+copy('المرحلة','Stage')+'</th><th>'+copy('المشروع','Project')+'</th><th>'+copy('حالة التشغيل','Run status')+'</th><th>'+copy('التاريخ','Date')+'</th><th>'+copy('التواصل','Communication')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>'+copy('لا توجد تشغيلات مطابقة.','No matching runs.')+'</p>')+'</section>';
}

function adminStatus(runs){
  const stageStatus=stage=>{
    const scoped=runs.filter(run=>run.stage===stage);
    const done=scoped.filter(run=>run.state==='completed').length;
    return scoped.length?done+' / '+scoped.length+' '+copy('تشغيلات مكتملة','runs completed'):copy('لا توجد تشغيلات مسجلة','No recorded runs');
  };
  return '<section class="panel"><h2>'+copy('متابعة الأنظمة والمراحل','Systems and stage monitoring')+'</h2><div class="admin-status-grid">'
    +'<div class="note"><b>'+copy('واجهة بيانات يقظ المحلية','Local YAQIDH API')+'</b><p>'+badge(copy('استجابت للطلب الحالي','Responded to this request'),'good')+'</p><small>'+safe(profile.apiStatus.checkedAt.slice(0,16).replace('T',' '))+' UTC</small></div>'
    +'<div class="note"><b>'+copy('مسار الجودة','QA pipeline')+'</b><p>'+stageStatus('qa')+'</p></div>'
    +'<div class="note"><b>'+copy('مسار الأمن','Security pipeline')+'</b><p>'+stageStatus('security')+'</p></div>'
    +'<div class="note"><b>'+copy('ربط مستودع الكود','Repository integration')+'</b><p>'+badge(copy('غير مربوط','Unconnected'),'wait')+'</p></div></div></section>';
}
function adminView(){
  const accounts=profile.accounts.filter(a=>(adminProject==='all'||a.projects.includes(adminProject))&&(adminRole==='all'||a.role===adminRole)&&(adminActive==='all'||String(a.active)===adminActive));
  const scopedRuns=profile.runSummary.filter(run=>(adminProject==='all'||run.project===adminProject)&&(adminStage==='all'||run.stage===adminStage));
  const runs=scopedRuns.filter(run=>(adminDay==='all'||run.day===adminDay)&&(runFilter==='all'||run.state===runFilter));
  const missing=profile.projects.filter(project=>(adminProject==='all'||project===adminProject)&&['qa','security'].some(role=>!profile.accounts.some(a=>a.active&&a.role===role&&a.projects.includes(project))));
  const active=accounts.filter(a=>a.active),failed=runs.filter(run=>run.state==='error');
  const rows=accounts.map(a=>'<tr><td>'+safe(accountName(a.name))+'</td><td>'+roleNames(a.role)+'</td><td>'+(safe(a.projects.map(projectName).join(', '))||'—')+'</td><td>'+ (a.active?copy('نشط','Active'):copy('معطّل','Disabled'))+'</td><td>'+(a.name!=='company-admin'?'<div class="actions">'+action('edit-account',copy('تعديل','Edit'),'data-id="'+safe(a.name)+'"')+(!a.active?action('delete-account',copy('حذف','Delete'),'class="danger-action" data-id="'+safe(a.name)+'"'):'')+'</div>':'—')+'</td></tr>').join('');
  return '<div class="admin-workspace"><div class="metric-row">'+metric(copy('الحسابات النشطة','Active accounts'),active.length,'',active,copy('الحسابات النشطة ضمن فلاتر الحسابات.','Active accounts within account filters.'),a=>safe(accountName(a.name))+' · '+roleNames(a.role))
    +metric(copy('مشاريع ينقصها مراجع','Projects missing a reviewer'),missing.length,'wait',missing,copy('مشاريع لا يتوفر لها مراجع جودة أو أمن نشط.','Projects without an active QA or security reviewer.'),project=>safe(projectName(project)))
    +metric(copy('تشغيلات متعطلة في العرض','Failed demo runs'),failed.length,'bad',failed,copy('التشغيلات المتعطلة ضمن نطاق التشغيل المصفّى.','Failed runs in the filtered run scope.'),runRecord)
    +metric(copy('ربط مستودع الكود','GitHub integration'),copy('غير مربوط','Unconnected'),'wait',[],copy('لم تُربط المعاينة بمستودع خارجي.','The preview is not connected to an external repository.'))+'</div>'
    +'<section class="panel filters"><label>'+copy('المشروع','Project')+'<select id="admin-project"><option value="all">'+copy('كل المشاريع','All projects')+'</option>'+profile.projects.map(id=>'<option '+(adminProject===id?'selected ':'')+'value="'+safe(id)+'">'+safe(projectName(id))+'</option>').join('')+'</select></label><label>'+copy('الدور','Role')+'<select id="admin-role"><option value="all">'+copy('كل الأدوار','All roles')+'</option>'+['developer','qa','security','company-admin'].map(id=>'<option '+(adminRole===id?'selected ':'')+'value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'+adminSelect('admin-active',copy('حالة الحساب','Account status'),adminActive,[['true',copy('نشط','Active')],['false',copy('معطّل','Disabled')]])+adminSelect('admin-stage',copy('المرحلة','Stage'),adminStage,[['qa',copy('الجودة','QA')],['security',copy('الأمن','Security')]])+'</section>'
    +'<div class="admin-analytics">'+adminTimeline(scopedRuns.filter(r=>runFilter==='all'||r.state===runFilter))+toolRunChart(scopedRuns.filter(r=>adminDay==='all'||r.day===adminDay))+'</div>'+chipRow([['day',adminDay,copy('اليوم','Day')+' · '+adminDay],['run',runFilter,statusText(runFilter)]],'admin-clear')+adminStatus(runs)+adminRunList(runs)+registrationQueue()+'<section class="panel"><h2>'+copy('الحسابات حسب الدور','Accounts by role')+'</h2>'+['developer','qa','security','company-admin'].map(id=>{const count=accounts.filter(a=>a.role===id).length;return '<div class="bar-row good"><span>'+roleNames(id)+' <b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(1,accounts.length)+'"></progress></div>'}).join('')+'</section>'
    +'<section class="panel" id="accounts"><h2>'+copy('الحسابات والأدوار ونطاق المشاريع','Accounts, roles, and project scope')+'</h2><p class="muted">'+copy('عدّل أدوار حسابات المعاينة وإسنادها. التغييرات تُحفظ طوال تشغيل المعاينة.','Manage demo roles and assignments. Changes last for this demo session.')+'</p>'
    +'<div class="table-wrap"><table><thead><tr><th>'+copy('الحساب','Account')+'</th><th>'+copy('الدور','Role')+'</th><th>'+copy('المشاريع','Projects')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الإجراء','Action')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'+adminAudit()+'</div>';
}
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
function releaseHeader(){
  const options=profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+buildName(item.build)+' · '+requestName(item.pr)+'</option>').join('');
  return '<section class="intro"><div><h2>'+stageText(release.stage)+'</h2><small>'+safe(projectName(release.project))+' · '+safe(requestName(release.pr))+' · '+safe(buildName(release.build))+' · '+safe(branchName(release.branch))+' · '+mon(release.commit)+'</small></div>'
    +'<label class="field">'+copy('البناء المصرّح به','Authorized build')+'<select id="release-select">'+options+'</select></label></section>'
    +'<section class="panel actions" aria-label="'+copy('عينات المراجعة','Review samples')+'"><b>'+copy('جرّب حالة','Try a scenario')+'</b>'+action('sample-issue',profile.role==='qa'?copy('مشكلة جودة','QA issue'):copy('ثغرة مانعة','Blocking vulnerability'),'aria-pressed="'+(release.id===sampleBuild('issue'))+'"')+action('sample-ready',profile.role==='qa'?copy('جاهز لمراجعة الجودة','Ready for QA review'):copy('صفر ملاحظات · جاهز للمراجعة','Zero findings · ready for review'),'aria-pressed="'+(release.id===sampleBuild('ready'))+'"')+action('sample-approved',profile.role==='qa'?copy('موافقة جودة مسجّلة','QA approval recorded'):copy('جاهز للإطلاق · معتمد أمنيًا','Ready for release · approved'),'aria-pressed="'+(release.id===sampleBuild('approved'))+'"')+'</section>'
    +'<section class="summary '+(release.outcome?.result==='fail'?'bad':release.outcome?.result==='pass'?'good':'wait')+'"><div><b>'+copy('نتيجة محرك القواعد','Policy outcome')+' · '+outcomeText()+'</b><p>'
    +(release.outcome?.reasons.map(displayReason).join(' · ')||copy('تتوفر النتائج بعد اكتمال الفحوصات المطلوبة.','Results are available once required checks complete.'))+'</p></div>'
    +'<div><small>'+copy('القرار البشري','Human decision')+'</small><p>'+decisionText()+'</p></div></section>';
}
function findingState(f){return f.closure?.result==='closed'?copy('إغلاق مثبت','Verified closed'):f.closure?.result==='still_open'?copy('ما زالت تحتاج معالجة','Still needs remediation'):statusText(f.status)}
function findingGroup(f){return f.closure?.result==='closed'?'fixed':f.status==='excepted'?'excepted':'open'}
function matched(){return release.findings.filter(f=>(runFilter==='all'||release.runs.filter(run=>run.tool===f.tool).length===1&&release.runs.some(run=>run.tool===f.tool&&run.state===runFilter))&&(findingFilter==='all'||findingGroup(f)===findingFilter)&&(tool==='all'||tool===f.tool)&&(severity==='all'||severity===f.severity))}
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
function toolRunChart(runs,developer=false){
  const keys=developer?['pass','fail','pending']:['completed','error','pending'];
  const labels=developer?[copy('اجتاز','Passed'),copy('أخفق','Failed'),copy('قيد الانتظار','Pending')]:stateLabels().map(([,label])=>label);
  const selected=developer?developerOutcome:runFilter;
  const act=developer?'developer-outcome':'run-state';
  const states=['completed','error','pending'];
  const bins=states.map((state,i)=>[keys[i],labels[i],['good','bad','wait'][i],runs.filter(run=>run.state===state).length]);
  let offset=0;
  const segments=bins.map(([id,label,tone,count])=>{
    if(!count)return '';
    const length=count/runs.length*100;
    const tip=label+' · '+fraction(count,runs.length);
    const result='<circle class="chart-ring '+tone+'" role="button" data-action="'+act+'" data-id="'+id+'" aria-pressed="'+(selected===id)+'" tabindex="0" aria-label="'+tip+'" cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="'+length+' '+(100-length)+'" stroke-dashoffset="'+(-offset)+'"><title>'+tip+'</title></circle>';
    offset+=length;
    return result;
  }).join('');
  const selectedCount=bins.find(([id])=>id===selected)?.[3];
  return '<section class="panel"><h2>'+(developer?copy('نتائج الأبنية المسندة','Assigned build outcomes'):copy('اكتمال تشغيل الأدوات','Tool run completion'))+'</h2><div class="chart-ring-layout">'
    +'<svg viewBox="0 0 108 108" class="chart-donut" role="group" aria-label="'+copy('توزيع الحالات','Status distribution')+'"><circle class="chart-ring-track" cx="54" cy="54" r="39"/>'+segments+'<text x="54" y="58">'+(selectedCount??runs.length)+'</text></svg>'
    +'<div>'+bins.map(([id,label,tone,count])=>'<p>'+action(act,label+' · '+count,'class="badge '+tone+'" data-id="'+id+'" aria-pressed="'+(selected===id)+'" title="'+label+' · '+fraction(count,runs.length)+'"')+'</p>').join('')+'</div></div>'
    +'<small>'+(runs.length?(developer?copy('التوزيع لكل الأبنية المسندة؛ الرقم يبيّن الحالة المختارة.','Distribution of all assigned builds; the number reflects the selection.'):copy('اكتمال التشغيل منفصل عن اجتياز الفحص.','Run completion is separate from passing a check.')):copy('لا توجد تشغيلات في النطاق المحدد.','No runs in the selected scope.'))+'</small></section>';
}

function shieldChart(){
  const tone=release.outcome?.result==='pass'?'good':release.outcome?.result==='fail'?'bad':'wait';
  return '<section class="panel"><h2>'+copy('درع نتيجة المرحلة','Stage outcome shield')+'</h2>'
    +'<div class="shield-chart '+tone+'"><svg viewBox="0 0 140 145" aria-hidden="true"><path class="shield-outer" d="M70 6 131 26v46c0 35-26 53-61 68C35 125 9 107 9 72V26Z"/><path class="shield-inner" d="M70 15 122 32v40c0 30-22 46-52 59C40 118 18 102 18 72V32Z"/></svg>'
    +'<div class="shield-content"><strong>'+outcomeText()+'</strong><small>'+safe(buildName(release.build))+'</small></div></div><small>'+copy('محرك القواعد · البناء كاملًا','Policy engine · full build')+'</small></section>';
}
function findingLabel(key){return ({open:copy('قيد التنفيذ','In progress'),fixed:copy('مغلقة','Closed'),excepted:copy('مستثناة','Excepted')})[key]||''}
function bugChart(rows){
  const counts=[['open',copy('قيد التنفيذ','In progress'),'bad'],['fixed',copy('مغلقة','Closed'),'good'],['excepted',copy('مستثناة','Excepted'),'wait']];
  return '<section class="panel"><h2>'+(profile.role==='qa'?copy('حالة ملاحظات الجودة','QA finding status'):copy('حالة الثغرات والملاحظات','Vulnerability and finding status'))+'</h2><div class="bug-chart">'
    +'<svg viewBox="0 0 230 140" preserveAspectRatio="none" aria-hidden="true"><path d="M41 51 20 39H5m36 32H5m36 25-21 14H5m184-59 21-12h15m-36 32h36m-36 25 21 14h15M55 25h120l14 15v72l-14 15H55l-14-15V40Z"/><path class="bug-head" d="M89 24 101 8h28l12 16v16H89Z"/></svg><b class="bug-total" title="'+copy('إجمالي الملاحظات المطابقة','Total matching findings')+'">'+rows.length+'</b><div class="bug-counts">'
    +counts.map(([key,label,tone])=>'<button type="button" data-action="finding-group" data-id="'+key+'" class="'+tone+'" aria-pressed="'+(findingFilter===key)+'" title="'+label+' · '+fraction(rows.filter(f=>findingGroup(f)===key).length,rows.length)+'"><span>'+label+'</span><progress value="'+rows.filter(f=>findingGroup(f)===key).length+'" max="'+Math.max(rows.length,1)+'"></progress><b>'+rows.filter(f=>findingGroup(f)===key).length+'</b></button>').join('')
    +'</div></div><small>'+copy('تتغير مع فلتر الأداة والخطورة','Updates with tool and severity filters')+'</small></section>';
}
function qaChart(rows,title=copy('حالة ملاحظات الجودة','QA finding status')){
  const resolved=rows.filter(f=>f.closure?.result==='closed').length;
  const groups=[[copy('تحتاج معالجة','Needs remediation'),rows.filter(f=>f.status!=='excepted'&&f.closure?.result!=='closed').length,'bad'],
    [copy('إغلاق مثبت','Verified closed'),resolved,'good'],
    [copy('مستثناة','Excepted'),rows.filter(f=>f.status==='excepted'&&f.closure?.result!=='closed').length,'wait']];
  return '<section class="panel"><h2>'+title+'</h2>'
    +groups.map(([label,count,tone])=>'<div class="bar-row '+tone+'"><span>'+label+' <b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(1,rows.length)+'"></progress></div>').join('')
    +'<small>'+copy('يعرض الملاحظات المطابقة للفلاتر الحالية','Shows findings matching the active filters')+'</small></section>';
}
function stageCharts(){
  const runs=release.runs.filter(run=>tool==='all'||run.tool===tool);
  return '<div class="role-charts three">'+shieldChart()+bugChart(matched())+toolRunChart(runs)+'</div>';
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
    +action('new-thread',copy('فتح نقاش','Start discussion'))+action('runs',copy('سجل تشغيل الأدوات','Tool runs'))+action('evidence',copy('ملف الأدلة','Evidence'))+action('decisions',copy('سجل القرارات','Decision log'))
    +(profile.role==='security'?action('previous-qa',copy('موافقة الجودة السابقة','Previous QA approval')):'')+(release.prior?action('prior',copy('البناء السابق','Previous build')):'')
    +(release.canReject?action('reject',copy('إرجاع مع السبب','Return with reason')):'')
    +(release.canApprove?action('approve',copy('تسجيل الموافقة','Record approval'),'class="primary"'):'')
    +'</div></div></section>'+findingsView()+'<section class="panel"><h2>'+copy('اتجاه النتائج عبر الزمن','Results over time')+'</h2><p class="muted">'+copy('لا يتوفر سجل أحداث مؤرخ كافٍ لرسم الاتجاه.','There is not enough dated event history to plot a trend.')+'</p></section>';
}
let threads=[],selectedThread=null;
const unreadCount=()=>threads.filter(thread=>thread.unread).length;
function sidebar(){
  const nav=(href,label,mark)=>'<a href="'+href+'" '+(location.pathname===href?'aria-current="page"':'')+'><span aria-hidden="true">'+mark+'</span>'+label+'</a>';
  return '<aside class="sidebar"><a href="/" aria-label="'+copy('يقظ','YAQIDH')+'"><img class="brand" alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"></a><nav aria-label="'+copy('التنقل','Navigation')+'">'
    +nav(profile?.role==='company-admin'?'/admin':'/dashboard',copy('لوحة المتابعة','Dashboard'),'▦')
    +(profile?nav('/communication',copy('التواصل','Communication')+(unreadCount()?' · '+unreadCount():''),'◌'):'')
    +(profile?.role==='company-admin'?nav('/admin#accounts',copy('إدارة الحسابات','Account administration'),'◇'):'')
    +'</nav><div class="sidebar-account">'+(profile?'<b>'+roleNames(profile.role)+'</b>'+action('logout',copy('تسجيل الخروج','Sign out')):'<a class="action" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a>')+'</div></aside>';
}
function aboutView(){
  const steps=[
    [copy('رفع التعديل','Submit change'),copy('المطور يرفع طلب دمج ويعالج الملاحظات عند الإرجاع.','The developer opens a pull request and addresses returned findings.')],
    [copy('فحوصات الجودة','QA checks'),copy('يقظ يشغّل أدوات الجودة، ومراجع الجودة يسجّل قراره.','YAQIDH runs QA tools and the QA reviewer records a decision.')],
    [copy('فحوصات الأمن','Security checks'),copy('الوكيل نفسه يشغّل أدوات الأمن على البناء في فرع ما قبل الإطلاق.','The same agent runs security tools on the staging build.')],
    [copy('قرار المراجع الأمني','Security decision'),copy('يراجع السايبر الأدلة ويسجّل الموافقة أو الإرجاع مع السبب.','The reviewer examines evidence and approves or returns the build with a reason.')]
  ];
  return '<main><section class="panel home-hero"><small>'+copy('الجاهزية الأمنية للإصدارات','Security readiness for releases')+'</small><h1>'+copy('يقظ يربط الفحص بالقرار','YAQIDH connects checks to decisions')+'</h1><p>'+copy('وكيل واحد يرافق التعديل في مرحلتَي الجودة والأمن. يشرح نتائج الأدوات ويحفظها في ملف أدلة يراجعه الإنسان قبل اتخاذ القرار.','One agent follows the change across QA and security. It explains tool results and records evidence for human review.')+'</p><a class="action primary" href="/dashboard">'+copy('فتح لوحة المتابعة','Open dashboard')+'</a></section><div class="metric-row">'
    +steps.map(([title,text],index)=>'<article class="panel"><small>'+copy('الخطوة','Step')+' '+(index+1)+'</small><h2>'+title+'</h2><p>'+text+'</p></article>').join('')+'</div><section class="panel workflow-loop"><b>↶ '+copy('عند الإخفاق أو الإرجاع','When a check fails or a change is returned')+'</b><p>'+copy('يرجع التعديل للمطور، ثم يعاد الفحص على التعديل الجديد. يحتفظ ملف الأدلة بنتائج كل جولة.','The developer updates the change and the checks run again. Evidence retains the result of each round.')+'</p></section></main>';
}
function threadText(value){
  return ({
    'developer-inbox-demo':copy('إرجاع تعديل الجودة','QA change returned'),
    'developer-message-demo':copy('لم يظهر تأكيد الطلب بعد الإرسال. عالج الملاحظة وارفع التعديل لإعادة الفحص.','Order confirmation did not appear after submission. Address the finding and resubmit for verification.'),
    'deadline-demo':copy('طلب مهلة إضافية لمعالجة ملاحظة أمنية','Extension request for security remediation'),
    'deadline-reason-demo':copy('وقت إضافي لإكمال المعالجة وإعادة التحقق.','Extra time to complete remediation and reverification.'),
    'deadline-message-demo':copy('هل يمكن توضيح خطوات إعادة الفحص المتبقية قبل الموعد المطلوب؟','Can you clarify which verification steps remain before the requested date?')
  })[value]||value;
}
function communicationView(){
  const thread=threads.find(item=>item.id===selectedThread);
  const cards=threads.map(item=>'<button type="button" class="thread-card" data-action="thread" data-id="'+safe(item.id)+'" aria-pressed="'+(item.id===selectedThread)+'"><b>'+safe(threadText(item.subject))+'</b><small>'+safe(buildName(item.build))+(item.unread?' · '+copy('غير مقروء','Unread'):'')+'</small></button>').join('');
  let details='<p class="muted">'+copy('اختر محادثة لعرض الرسائل.','Select a conversation to view messages.')+'</p>';
  if(thread){
    details='<h2>'+safe(threadText(thread.subject))+'</h2><p>'+safe(buildName(thread.build))+' · '+thread.members.map(member=>safe(accountName(member))).join(' · ')+'</p>'
      +(thread.finding?'<small>'+copy('بصمة الملاحظة','Finding fingerprint')+' '+mon(thread.finding)+'</small>':'')
      +(thread.evidenceAllowed?'<p><a href="/dashboard?build='+encodeURIComponent(thread.release)+'">'+copy('فتح بناء الدليل','Open evidence build')+'</a></p>':'')
      +(thread.deadline?'<div class="details-grid">'+detail(copy('الموعد المعتمد','Approved deadline'),mon(thread.deadline.original))
        +detail(copy('الموعد المطلوب','Requested deadline'),mon(thread.deadline.requested))
        +detail(copy('حالة الطلب','Request status'),copy('بانتظار المراجعة','Pending review'))
        +detail(copy('سبب طلب المهلة','Extension reason'),safe(threadText(thread.deadline.reason)))+'</div>':'')
      +'<div class="messages">'+thread.messages.map(message=>'<article class="note"><small>'+safe(accountName(message.by))+' · '+roleNames(message.role)+' · '+mon(message.at.slice(0,16).replace('T',' '))+'</small><p>'+safe(threadText(message.text))+'</p></article>').join('')+'</div>'
      +'<form id="thread-reply" data-id="'+safe(thread.id)+'"><label class="field">'+copy('اكتب ردًا أو اطلب توضيحًا','Write a reply or ask for clarification')+'<textarea name="message" maxlength="1500" required></textarea></label><button class="primary">'+copy('إرسال الرد','Send reply')+'</button></form>';
  }
  return '<main><h1>'+copy('التواصل','Communication')+'</h1><div class="communication-grid"><section class="panel thread-list"><h2>'+copy('المحادثات','Conversations')+'</h2>'+ (cards||'<p>'+copy('لا توجد محادثات في نطاقك.','No conversations in your scope.')+'</p>')+'</section><section class="panel">'+details+'</section></div></main>';
}
function startThread(finding,releaseId=release.id){
  const destination=profile.role==='developer'?stageText(release.stage):copy('المطور المسند إليه التعديل','Assigned developer');
  modal(copy('فتح نقاش مرتبط بالبناء','Start a build discussion'),
    '<form id="thread-new" data-finding="'+safe(finding)+'" data-release="'+safe(releaseId)+'"><div class="note"><b>'+copy('المرسل','Sender')+'</b> '+safe(accountName(profile.account))+' · '+roleNames(profile.role)+'<br><b>'+copy('التوجيه التلقائي','Automatically routed to')+'</b> '+destination+'</div>'
    +'<label class="field">'+copy('موضوع النقاش','Subject')+'<input name="subject" required maxlength="100"></label>'
    +'<label class="field">'+copy('الرسالة أو سبب طلب المهلة','Message or extension reason')+'<textarea name="message" required maxlength="1500"></textarea></label><div class="details-grid"><label class="field">'+copy('الموعد المعتمد (اختياري)','Approved deadline (optional)')+'<input type="date" name="original"></label><label class="field">'+copy('الموعد المطلوب (اختياري)','Requested deadline (optional)')+'<input type="date" name="requested"></label></div><button class="primary">'+copy('إرسال','Send')+'</button></form>');
}
function confirmAccountDeletion(id){
  const account=profile.accounts.find(item=>item.name===id);
  if(!account||account.active||account.role==='company-admin')return;
  modal(copy('حذف حساب معطّل','Delete disabled account'),
    '<p>'+copy('هل تريد حذف هذا الحساب؟ تبقى الرسائل والقرارات السابقة في السجل.','Delete this account? Existing messages and decisions remain in the record.')+'</p><p>'+mon(id)+'</p>'
    +'<form id="account-delete" data-id="'+safe(id)+'"><button class="danger-action">'+copy('تأكيد حذف الحساب','Confirm account deletion')+'</button></form>');
}
function editAccount(id){
  const account=profile.accounts.find(item=>item.name===id);
  if(!account||id==='company-admin')return;
  modal(copy('تعديل صلاحية الحساب','Edit account access'),
    '<form id="account-edit" data-id="'+safe(id)+'"><p>'+safe(accountName(id))+'</p>'
    +'<label class="field">'+copy('الدور','Role')+'<select name="role">'+['developer','qa','security'].map(role=>'<option value="'+role+'" '+(role===account.role?'selected':'')+'>'+roleNames(role)+'</option>').join('')+'</select></label>'
    +'<label><input type="checkbox" name="active" '+(account.active?'checked':'')+'> '+copy('الحساب نشط','Account active')+'</label><br>'
    +profile.projects.map(project=>'<label><input type="checkbox" name="projects" value="'+safe(project)+'" '+(account.projects.includes(project)?'checked':'')+'> '+safe(projectName(project))+'</label>').join('')
    +'<button class="primary">'+copy('حفظ الصلاحية','Save access')+'</button></form>');
}
function reviewQueue(){
  const rows=profile.releases.filter(item=>item.active===profile.role).slice().sort((a,b)=>Number(b.pendingReview)-Number(a.pendingReview)||Number(b.outcome==='fail')-Number(a.outcome==='fail'));
  return '<section class="panel"><div class="section-head"><h2>'+copy('قائمة المراجعة','Review queue')+'</h2><small>'+rows.filter(item=>item.pendingReview).length+' '+copy('بانتظار الموافقة','awaiting approval')+'</small></div>'
    +'<div class="actions">'+rows.map(item=>action('queue',safe(buildName(item.build))+' · '+(item.outcome==='fail'?copy('أخفق','Failed'):item.pendingReview?copy('ينتظر قرارك','Awaiting your decision'):item.outcome==='pass'?copy('اجتاز','Passed'):copy('بانتظار الفحص','Awaiting checks')),'data-id="'+safe(item.id)+'"')).join('')+'</div></section>';
}

function render(){
  hideMetricTip();
  metricDetails.clear();
  const page=location.pathname;
  if(page==='/'){app.innerHTML=header()+landing();return}
  const content=page==='/about'?aboutView():page==='/signup'?signup():!profile?login():page==='/communication'?communicationView():'<main>'+introduction()+(profile.role==='company-admin'?adminView():profile.role==='developer'?developerView():reviewView())+'</main>';
  app.innerHTML=header()+(profile?sidebar():'')+'<div class="'+(profile?'shell':'public-shell')+'">'+content+'</div>';
}
async function selectRelease(id){
  const turn=++requestNumber;
  const next=await api('/api/releases/'+encodeURIComponent(id));
  if(turn!==requestNumber)return;
  release=next;tool='all';severity='all';findingFilter='all';runFilter='all';render();
}
async function load(){
  try{profile=await api('/api/dashboard')}catch(e){if(!['401','403'].includes(e.message))throw e;profile=null;if(!['/','/about','/login','/signup'].includes(location.pathname))history.replaceState(null,'','/login'+location.search)}
  if(profile&&['/login','/dashboard','/admin'].includes(location.pathname)){const destination=profile.role==='company-admin'?'/admin':'/dashboard';if(location.pathname!==destination)history.replaceState(null,'',destination+location.search)}
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
    +'<p>'+action('new-thread',copy('ناقش هذه الملاحظة','Discuss this finding'),'data-id="'+safe(f.fingerprint)+'"')+'</p>'
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
  if(id==='queue'||id==='returned-build'){if(dialog.open)dialog.close();await selectRelease(button.dataset.id);if(id==='returned-build')modal(copy('سبب الإرجاع','Return reason'),decisionList());return}
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
load().catch(()=>notify(copy('تعذر تحميل الداشبورد','Dashboard could not be loaded')));
