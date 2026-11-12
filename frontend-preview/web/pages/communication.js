function threadText(value){
  return ({
    'developer-inbox-demo':copy('إرجاع تعديل الجودة','QA change returned'),
    'developer-message-demo':copy('لم يظهر تأكيد الطلب بعد الإرسال. عالج المشكلة وارفع التعديل لإعادة الفحص.','Order confirmation did not appear after submission. Address the finding and resubmit for verification.'),
    'deadline-demo':copy('طلب مهلة إضافية لمعالجة ثغرة أمنية','Extension request for security remediation'),
    'deadline-reason-demo':copy('وقت إضافي لإكمال المعالجة وإعادة التحقق.','Extra time to complete remediation and reverification.'),
    'deadline-message-demo':copy('هل يمكن توضيح خطوات إعادة الفحص المتبقية قبل الموعد المطلوب؟','Can you clarify which verification steps remain before the requested date?')
  })[value]||value;
}

function displayReviewDeadline(value){
  return mon(value.replace('T',' '))+(value.includes('T')?' · '+copy('بتوقيت الرياض','Riyadh time'):'');
}

function adjustReviewDeadline(id){
  const request=threads.find(thread=>thread.id===id)?.deadline;
  if(profile.role!=='security'||request?.status!=='pending')return;
  const proposed=request.requested.includes('T')?request.requested:request.requested+'T09:00';
  modal(copy('تعديل موعد التمديد','Adjust extension deadline'),
    '<form id="review-deadline-form" data-id="'+safe(id)+'">'
    +'<p>'+copy('موعد المطوّر المقترح','Developer proposed deadline')+' · '+displayReviewDeadline(request.requested)+'</p>'
    +'<label class="field">'+copy('التاريخ والوقت الجديدان · بتوقيت الرياض','New date and time · Riyadh time')
    +'<input type="datetime-local" name="approvedDeadline" value="'+safe(proposed)+'" required></label>'
    +'<button class="primary">'+copy('اعتماد الموعد المعدّل','Approve adjusted deadline')+'</button></form>');
}

function reviewRequestDetails(thread){
  const exception=thread.exceptionRequest;
  const request=exception||thread.deadline;
  if(!request)return '';
  const statuses={pending:copy('بانتظار المراجعة','Pending review'),approved:copy('معتمد','Approved'),rejected:copy('مرفوض','Rejected')};
  return '<section class="note"><h3>'+(exception?copy('طلب استثناء أمني','Security exception request'):copy('طلب تمديد المهلة','Deadline extension request'))+'</h3><div class="details-grid">'
    +(exception?'':detail(copy('الموعد الساري','Effective deadline'),displayReviewDeadline(request.status==='approved'?(request.approvedDeadline||request.requested):request.original))
      +detail(copy('الموعد الأصلي','Original deadline'),mon(request.original))
      +detail(copy('موعد المطوّر المقترح','Developer proposed deadline'),displayReviewDeadline(request.requested)))
    +detail(copy('الحالة','Status'),statuses[request.status])
    +detail(copy('المبرر','Justification'),safe(threadText(request.reason)))
    +(request.by?detail(copy('قرار المراجع','Reviewed by'),safe(accountName(request.by))):'')+'</div>'
    +(profile.role==='security'&&request.status==='pending'?'<div class="actions">'
      +action('approve-review-request',exception?copy('قبول الاستثناء','Approve exception'):copy('اعتماد التمديد','Approve extension'),'class="primary" data-id="'+safe(thread.id)+'"')
      +(exception?'':action('adjust-review-deadline',copy('تعديل الموعد','Adjust deadline'),'data-id="'+safe(thread.id)+'"'))
      +action('reject-review-request',exception?copy('رفض الاستثناء','Reject exception'):copy('رفض التمديد','Reject extension'),'data-id="'+safe(thread.id)+'"')+'</div>':'')
    +'<p class="muted">'+(exception?copy('اعتماد الاستثناء يخص هذه الثغرة فقط.','Approval applies to this finding only.'):copy('اعتماد المهلة يغيّر الموعد فقط.','Approval updates the deadline only.'))+'</p></section>';
}

function communicationView(){
  const thread=threads.find(item=>item.id===selectedThread);
  const cards=threads.map(item=>'<button type="button" class="thread-card" data-action="thread" data-id="'+safe(item.id)+'" aria-pressed="'+(item.id===selectedThread)+'"><b>'+safe(threadText(item.subject))+'</b><small>'+(item.kind==='administrative'?copy('مراسلة إدارية','Administrative message'):safe(buildName(item.build)))+(item.unread?' · '+copy('غير مقروء','Unread'):'')+'</small></button>').join('');
  let details='<p class="muted">'+copy('اختر محادثة لعرض الرسائل.','Select a conversation to view messages.')+'</p>';
  if(thread){
    details='<h2>'+safe(threadText(thread.subject))+'</h2><p>'+(thread.kind==='administrative'?'':safe(buildName(thread.build))+' · ')+thread.members.map(member=>safe(accountName(member))).join(' · ')+'</p>'
      +(thread.finding?'<small>'+copy('بصمة المشكلة','Finding fingerprint')+' '+mon(thread.finding)+'</small>':'')
      +(thread.evidenceAllowed?'<p><a href="/dashboard?build='+encodeURIComponent(thread.release)+'">'+copy('فتح بناء الدليل','Open evidence build')+'</a></p>':'')
      +reviewRequestDetails(thread)
      +'<div class="messages">'+thread.messages.map(message=>'<article class="note"><small>'+safe(accountName(message.by))+' · '+roleNames(message.role)+' · '+mon(message.at.slice(0,16).replace('T',' '))+'</small><p>'+safe(threadText(message.text))+'</p></article>').join('')+'</div>'
      +'<form id="thread-reply" data-id="'+safe(thread.id)+'"><label class="field">'+copy('اكتب ردًا أو اطلب توضيحًا','Write a reply or ask for clarification')+'<textarea name="message" maxlength="1500" required></textarea></label><button class="primary">'+copy('إرسال الرد','Send reply')+'</button></form>';
  }
  return '<main><h1>'+(profile.role==='company-admin'?copy('مراسلات الموظفين','Employee messages'):copy('التواصل','Communication'))+'</h1>'+(profile.role==='company-admin'?'<div class="actions">'+action('new-admin-thread',copy('رسالة جديدة','New message'))+'</div>':'')+(profile.role==='qa'?qaReviewAlertsPanel():'')+'<div class="communication-grid"><section class="panel thread-list"><h2>'+copy('المحادثات','Conversations')+'</h2>'+ (cards||'<p>'+copy('لا توجد محادثات في نطاقك.','No conversations in your scope.')+'</p>')+'</section><section class="panel">'+details+'</section></div></main>';
}

function startThread(finding,releaseId=release.id){
  const extensionOnly=profile.role==='developer'&&release.stage==='security';
  const simple=!extensionOnly;
  const optional=extensionOnly?'':' '+copy('(اختياري)','(optional)');
  const required=extensionOnly?' required':'';
  const destination=profile.role==='developer'?stageText(release.stage):copy('المطوّر المسند إليه التعديل','Assigned developer');
  modal(extensionOnly?copy('طلب تمديد المهلة','Request deadline extension'):(profile.role==='qa'?copy('مراسلة المطوّر بخصوص هذا الطلب','Message the developer about this request'):copy('فتح نقاش مرتبط بالبناء','Start a build discussion')),
    '<form id="thread-new" data-finding="'+safe(finding)+'" data-release="'+safe(releaseId)+'">'+(simple?'':'<div class="note"><b>'+copy('المرسل','Sender')+'</b> '+safe(accountName(profile.account))+' · '+roleNames(profile.role)+'<br><b>'+copy('التوجيه التلقائي','Automatically routed to')+'</b> '+destination+'</div>')
    +'<label class="field">'+(simple?copy('العنوان','Title'):copy('موضوع النقاش','Subject'))+'<input name="subject" required maxlength="100"></label>'
    +'<label class="field">'+(simple?copy('الرسالة','Message'):copy('الرسالة أو سبب طلب المهلة','Message or extension reason'))+'<textarea name="message" required maxlength="1500"></textarea></label>'+(simple?'<input type="hidden" name="original" value=""><input type="hidden" name="requested" value="">':'<div class="details-grid"><label class="field">'+copy('الموعد المعتمد','Approved deadline')+optional+'<input type="date" name="original"'+required+'></label><label class="field">'+copy('الموعد المطلوب','Requested deadline')+optional+'<input type="date" name="requested"'+required+'></label></div>')+'<button class="primary">'+copy('إرسال','Send')+'</button></form>');
}

function startAdminThread(){
  const recipients=profile.accounts.filter(account=>account.active&&account.role!=='company-admin');
  modal(copy('رسالة إدارية جديدة','New administrative message'),recipients.length?
    '<form id="admin-thread-new"><label class="field">'+copy('الموظف المستلم','Employee recipient')+'<select name="recipient" required><option value="">'+copy('اختر موظفًا','Select an employee')+'</option>'
    +recipients.map(account=>'<option value="'+safe(account.name)+'">'+safe(accountName(account.name))+' · '+roleNames(account.role)+'</option>').join('')+'</select></label>'
    +'<label class="field">'+copy('الموضوع','Subject')+'<input name="subject" required maxlength="100"></label>'
    +'<label class="field">'+copy('الرسالة','Message')+'<textarea name="message" required maxlength="1500"></textarea></label>'
    +'<button class="primary">'+copy('إرسال','Send')+'</button></form>':'<p>'+copy('لا توجد حسابات موظفين نشطة.','There are no active employee accounts.')+'</p>');
}

function startExceptionRequest(finding){
  modal(copy('طلب استثناء أمني','Request security exception'),
    '<form id="exception-new" data-release="'+safe(release.id)+'" data-finding="'+safe(finding)+'">'
    +'<p>'+safe(buildName(release.build))+' · '+mon(finding)+'</p>'
    +'<label class="field">'+copy('مبرر الاستثناء','Exception justification')+'<textarea name="message" maxlength="1500" required></textarea></label>'
    +'<button class="primary">'+copy('إرسال للمراجعة الأمنية','Send for security review')+'</button></form>');
}
