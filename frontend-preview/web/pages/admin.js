function adminSelect(id,label,current,options){
  return '<label>'+label+'<select id="'+id+'"><option value="all">'+copy('الكل','All')+'</option>'+options.map(([value,text])=>'<option value="'+value+'" '+(current===value?'selected':'')+'>'+text+'</option>').join('')+'</select></label>';
}

function adminAudit(){
  return '<section class="panel"><h2>'+copy('سجل تغييرات الصلاحيات','Access change log')+'</h2>'
    +(profile.audit.length?profile.audit.slice().reverse().map(item=>'<p>'+safe(accountName(item.target))+' · '+roleNames(item.role)+' · '+(item.action==='deleted'?copy('حُذف الحساب','Account deleted'):item.active?copy('نشط','Active'):copy('معطّل','Disabled'))+' · '+(item.assigned?copy('مسند إلى المشروع','Assigned to project'):copy('أُلغي الإسناد','Unassigned'))+' · '+mon(item.at.slice(0,16).replace('T',' '))+'</p>').join(''):'<p>'+copy('لا توجد تغييرات مسجّلة.','No changes recorded.')+'</p>')+'</section>';
}

function registrationQueue(){
  return '<section class="panel"><div class="section-head"><h2>'+copy('طلبات إنشاء الحساب','Account requests')+'</h2>'+badge(profile.requests.length+' '+copy('معلّقة','pending'),'wait')+'</div>'
    +(profile.requests.map(item=>'<div class="request-row"><div>'+mon(item.name)+' · '+roleNames(item.role)+'</div><div class="actions">'
    +action('account-approve',copy('تفعيل وإسناد للمشروع','Activate and assign'),'class="primary" data-id="'+safe(item.name)+'"')
    +action('account-reject',copy('رفض الطلب','Reject request'),'data-id="'+safe(item.name)+'"')+'</div></div>').join('')||'<p>'+copy('لا توجد طلبات معلقة.','No pending requests.')+'</p>')+'</section>';
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
