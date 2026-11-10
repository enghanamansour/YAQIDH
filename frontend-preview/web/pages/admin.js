function adminSelect(id,label,current,options){
  return '<label>'+label+'<select id="'+id+'"><option value="all">'+copy('الكل','All')+'</option>'+options.map(([value,text])=>'<option value="'+value+'" '+(current===value?'selected':'')+'>'+text+'</option>').join('')+'</select></label>';
}

function adminAudit(){
  return '<section class="panel"><h2>'+copy('سجل تغييرات الصلاحيات','Access change log')+'</h2>'
    +(profile.audit.length?profile.audit.slice().reverse().map(item=>'<p>'+safe(accountName(item.target))+' · <b class="'+roleColor(item.role)+'">'+roleNames(item.role)+'</b> · '+(item.action==='deleted'?copy('حُذف الحساب','Account deleted'):item.active?copy('نشط','Active'):copy('معطّل','Disabled'))+' · '+copy('بواسطة','By')+' '+safe(accountName(item.by))+' · '+mon(item.at.slice(0,16).replace('T',' ')+' UTC')+'</p>').join(''):'<p>'+copy('لا توجد تغييرات مسجّلة.','No changes recorded.')+'</p>')+'</section>';
}

function adminRoleDonut(distribution,total){
  let offset=0;
  const segments=distribution.map(({id,count})=>{
    if(!count)return '';
    const length=count/total*100;
    const start=offset;
    offset+=length;
    return '<circle class="chart-ring '+roleColor(id)+'" cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="'+length+' '+(100-length)+'" stroke-dashoffset="'+(-start)+'"><title>'
      +safe(roleNames(id))+' · '+count+' · '+Math.round(length*10)/10+'%</title></circle>';
  }).join('');
  return '<section class="panel"><h2>'+copy('توزيع الموظفين حسب الدور','Employee distribution by role')+'</h2><div class="chart-ring-layout">'
    +'<svg class="chart-donut" viewBox="0 0 108 108" aria-hidden="true"><circle class="chart-ring-track" cx="54" cy="54" r="39"/>'+segments
    +'<text x="54" y="54">'+total+'</text><text class="admin-donut-caption" x="54" y="67">'+copy('الإجمالي','Total')+'</text></svg>'
    +'<ul class="admin-role-legend">'+distribution.map(({id,count})=>'<li><span class="admin-role-dot '+roleColor(id)+'" aria-hidden="true"></span><span>'
      +safe(roleNames(id))+'</span><b>'+count+'</b></li>').join('')+'</ul></div></section>';
}

const demoAgentHistory=[
  ['2026-11-03',4,0],['2026-11-04',6,1],['2026-11-05',3,0],['2026-11-06',7,2],
  ['2026-11-07',5,0],['2026-11-08',8,1],['2026-11-09',6,0]
];

function adminAgentAlerts(){
  const alerts=demoAgentHistory.filter(([, ,failed])=>failed>=2).slice().reverse();
  return '<section class="panel"><div class="section-head"><h2>'+copy('تنبيهات تحتاج تدخلًا','Alerts requiring attention')+'</h2>'
    +badge(copy('بيانات تجريبية','Demo data'),'wait')+'</div>'
    +(alerts.length?alerts.map(([day,total,failed])=>'<article class="note"><div class="section-head"><div><b>'
      +copy('تكرّر تعطل الوكيل','Repeated agent failures')+'</b><p>'+mon(day)+' · '
      +copy('تشغيلات متعطلة','Failed runs')+' '+mon(failed+'/'+total)+'</p></div>'
      +action('agent-day',copy('عرض تفاصيل اليوم','View day details'),'data-id="'+day+'"')+'</div></article>').join('')
      :'<p>'+copy('لا توجد تنبيهات في سجل المعاينة.','No alerts in the demo history.')+'</p>')+'</section>';
}

function showAgentDay(day){
  const entry=demoAgentHistory.find(([date])=>date===day);
  if(!entry)return;
  const [,total,failed]=entry;
  modal(copy('تشغيل وكيل يقظ في هذا اليوم','YAQIDH agent runs for this day'),'<p>'+mon(day)+' · '+copy('بيانات تجريبية','Demo data')+'</p>'
    +'<div class="details-grid">'+detail(copy('إجمالي التشغيلات','Total runs'),total)
    +detail(copy('التشغيلات المتعطلة','Failed runs'),failed)
    +detail(copy('حالة اليوم','Day status'),failed?copy('حدث تعطل','Failure recorded'):copy('لم يُسجّل تعطل','No failures recorded'))+'</div>');
}

function adminView(){
  const agentRuns=demoAgentHistory.flatMap(([day,total,failed])=>Array.from({length:total},(_,i)=>({day,state:i<failed?'error':'completed'})));
  const roles=['developer','qa','security'];
  const query=adminQuery.toLowerCase();
  const accounts=profile.accounts.filter(a=>roles.includes(a.role)&&(adminActive==='all'||String(a.active)===adminActive)
    && (a.name.toLowerCase().includes(query)||accountName(a.name).toLowerCase().includes(query)));
  const distribution=roles.map(id=>({id,count:accounts.filter(a=>a.role===id).length}));
  const active=accounts.filter(a=>a.active);
  const disabled=accounts.filter(a=>!a.active);
  const formatAccount=a=>safe(accountName(a.name))+' · <b class="'+roleColor(a.role)+'">'+roleNames(a.role)+'</b>';
  const scope=copy('ضمن فلاتر الحسابات الحالية.','Within the current account filters.');
  const rows=accounts.map(a=>'<tr><td>'+safe(accountName(a.name))+'</td><td><b class="'+roleColor(a.role)+'">'+roleNames(a.role)+'</b></td><td>'+(a.active?copy('نشط','Active'):copy('معطّل','Disabled'))+'</td><td>'+(a.role!=='company-admin'?'<div class="actions">'+action('edit-account',copy('تعديل','Edit'),'data-id="'+safe(a.name)+'"')+(!a.active?action('delete-account',copy('حذف','Delete'),'class="danger-action" data-id="'+safe(a.name)+'"'):'')+'</div>':'—')+'</td></tr>').join('');
  return '<div class="admin-workspace"><div class="metric-row">'
    +metric(copy('إجمالي حسابات الموظفين','Total employee accounts'),accounts.length,'',accounts,scope,formatAccount)
    +metric(copy('الحسابات النشطة','Active accounts'),active.length,'good',active,scope,formatAccount)
    +metric(copy('الحسابات المعطّلة','Disabled accounts'),disabled.length,'wait',disabled,scope,formatAccount)
    +metric(copy('مراقبة وكيل يقظ','YAQIDH agent monitoring'),copy('غير متصلة','Disconnected'),'wait',[],copy('المعاينة المحلية لا تستقبل حالة تشغيل الوكيل.','The local preview does not receive agent health data.'),safe,copy('آخر اتصال فعلي غير متاح','Last live contact unavailable'))
    +'</div>'
    +'<section class="panel filters"><form id="admin-search" class="actions" role="search">'
    +'<label>'+copy('بحث باسم المستخدم','Search by username')+'<input type="search" name="query" value="'+safe(adminQuery)+'"></label>'
    +'<button type="submit">'+copy('بحث','Search')+'</button>'
    +(adminQuery?action('clear-admin-search',copy('مسح البحث','Clear search')):'')+'</form>'
    +adminSelect('admin-active',copy('حالة الحساب','Account status'),adminActive,[['true',copy('نشط','Active')],['false',copy('معطّل','Disabled')]])+'</section>'
    +adminAgentAlerts()+adminTimeline(agentRuns)
    +'<div class="admin-role-charts">'+adminRoleDonut(distribution,accounts.length)+'<section class="panel"><h2>'+copy('حسابات الموظفين حسب الدور','Employee accounts by role')+'</h2>'+distribution.map(({id,count})=>{return '<div class="bar-row '+roleColor(id)+'"><span>'+roleNames(id)+' <b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(1,accounts.length)+'"></progress></div>'}).join('')+'</section></div>'
    +'<section class="panel" id="accounts"><h2>'+copy('حسابات الموظفين','Employee accounts')+'</h2>'
    +(rows?'<div class="table-wrap"><table><thead><tr><th>'+copy('الحساب','Account')+'</th><th>'+copy('الدور','Role')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الإجراء','Action')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>'+copy('لا توجد حسابات مطابقة للفلاتر.','No accounts match the filters.')+'</p>')+'</section>'+adminAudit()+'</div>';
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
    +'<button class="primary">'+copy('حفظ الصلاحية','Save access')+'</button></form>');
}
