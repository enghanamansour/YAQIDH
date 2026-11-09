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
