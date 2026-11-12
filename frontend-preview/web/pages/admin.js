function adminSelect(id,label,current,options){
  return '<label>'+label+'<select id="'+id+'"><option value="all">'+copy('الكل','All')+'</option>'+options.map(([value,text])=>'<option value="'+value+'" '+(current===value?'selected':'')+'>'+text+'</option>').join('')+'</select></label>';
}

function adminAudit(){
  return '<section class="panel"><h2>'+copy('سجل تغييرات الصلاحيات','Access change log')+'</h2>'
    +(profile.audit.length?profile.audit.slice().reverse().map(item=>'<p>'+safe(accountName(item.target))+' · '+roleNames(item.role)+' · '+(item.action==='deleted'?copy('حُذف الحساب','Account deleted'):item.active?copy('نشط','Active'):copy('معطّل','Disabled'))+' · '+copy('بواسطة','By')+' '+safe(accountName(item.by))+' · '+mon(item.at.slice(0,16).replace('T',' ')+' UTC')+'</p>').join(''):'<p>'+copy('لا توجد تغييرات مسجّلة.','No changes recorded.')+'</p>')+'</section>';
}

function adminView(){
  const roles=['developer','qa','security','company-admin'];
  const query=adminQuery.toLowerCase();
  const accounts=profile.accounts.filter(a=>(adminActive==='all'||String(a.active)===adminActive)
    && (a.name.toLowerCase().includes(query)||accountName(a.name).toLowerCase().includes(query)));
  const active=accounts.filter(a=>a.active);
  const disabled=accounts.filter(a=>!a.active);
  const formatAccount=a=>safe(accountName(a.name))+' · '+roleNames(a.role);
  const scope=copy('ضمن فلاتر الحسابات الحالية.','Within the current account filters.');
  const rows=accounts.map(a=>'<tr><td>'+safe(accountName(a.name))+'</td><td>'+roleNames(a.role)+'</td><td>'+(a.active?copy('نشط','Active'):copy('معطّل','Disabled'))+'</td><td>'+(a.role!=='company-admin'?'<div class="actions">'+action('edit-account',copy('تعديل','Edit'),'data-id="'+safe(a.name)+'"')+(!a.active?action('delete-account',copy('حذف','Delete'),'class="danger-action" data-id="'+safe(a.name)+'"'):'')+'</div>':'—')+'</td></tr>').join('');
  return '<div class="admin-workspace"><div class="metric-row">'
    +metric(copy('إجمالي الحسابات','Total accounts'),accounts.length,'',accounts,scope,formatAccount)
    +metric(copy('الحسابات النشطة','Active accounts'),active.length,'good',active,scope,formatAccount)
    +metric(copy('الحسابات المعطّلة','Disabled accounts'),disabled.length,'wait',disabled,scope,formatAccount)
    +metric(copy('مراقبة وكيل يَقِـــظ','YAQIDH agent monitoring'),copy('غير متصلة','Disconnected'),'wait',[],copy('المعاينة المحلية لا تستقبل حالة تشغيل الوكيل.','The local preview does not receive agent health data.'))
    +'</div>'
    +'<section class="panel filters"><form id="admin-search" class="actions" role="search">'
    +'<label>'+copy('بحث باسم المستخدم','Search by username')+'<input type="search" name="query" value="'+safe(adminQuery)+'"></label>'
    +'<button type="submit">'+copy('بحث','Search')+'</button>'
    +(adminQuery?action('clear-admin-search',copy('مسح البحث','Clear search')):'')+'</form>'
    +adminSelect('admin-active',copy('حالة الحساب','Account status'),adminActive,[['true',copy('نشط','Active')],['false',copy('معطّل','Disabled')]])+'</section>'
    +'<section class="panel"><h2>'+copy('الحسابات حسب الدور','Accounts by role')+'</h2>'+roles.map(id=>{const count=accounts.filter(a=>a.role===id).length;return '<div class="bar-row good"><span>'+roleNames(id)+' <b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(1,accounts.length)+'"></progress></div>'}).join('')+'</section>'
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
