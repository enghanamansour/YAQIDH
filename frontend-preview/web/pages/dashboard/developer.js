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
  return '<div class="developer-workspace">'+developerPriority()+statusPanel()
    +'<section class="panel filters"><label>'+copy('طلب الدمج والبناء','Pull request and build')+'<select id="release-select">'+profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+safe(buildName(item.build))+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',copy('قيد التنفيذ','In progress')],['fixed',copy('مغلقة','Closed')],['excepted',copy('مستثناة','Excepted')]])
    +action('decisions',copy('عرض قرار المراجع','View reviewer decision'))+'</section>'+chipRow([['finding',findingFilter,copy('حالة المعالجة','Remediation status')],['developer-outcome',developerOutcome,copy('نتائج الأبنية','Build outcomes')],['developer-day',developerDay,copy('اليوم','Day')+' · '+developerDay]],'clear')
    +'<div class="metric-row">'+metric(copy('طلبات الدمج المسندة','Assigned pull requests'),requests.length,'',requests,copy('طلبات دمج مميزة ضمن الأبنية المسندة المطابقة.','Distinct pull requests in the matching assigned builds.'),buildRecord)+metric(copy('تعديلات معادة للمعالجة','Returned changes'),returns.length,'bad',returns,copy('أبنية مسندة آخر قرار لها الإرجاع.','Assigned builds whose latest decision was a return.'),buildRecord)+metric(copy('تنتظر إعادة الفحص','Awaiting recheck'),pending.length,'wait',pending,buildScope(copy('ملاحظات مطابقة لم يثبت إغلاقها.','Matching findings awaiting verified closure.')),findingRecord)+metric(copy('إغلاقات مثبتة','Verified closures'),fixed.length,'good',fixed,buildScope(copy('ملاحظات مطابقة ثبت إغلاقها.','Matching findings with verified closure.')),findingRecord)+'</div>'
    +'<div class="role-charts">'+qaChart(matched(),copy('حالات المعالجة','Remediation status'))+toolRunChart(counts.flatMap(item=>Array.from({length:item.count},()=>item)),true)+'</div>'+adminTimeline(profile.releases.filter(item=>item.day&&(developerOutcome==='all'||(item.outcome||'pending')===developerOutcome)).map(item=>({day:item.day,state:item.outcome==='fail'?'error':item.outcome==='pass'?'completed':'pending'})),true)+assignedBuildTable(assigned)
    +'<section class="panel"><h2>'+copy('أدلة المعالجة','Remediation evidence')+'</h2>'+(rows?'<div class="table-wrap"><table><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('الدليل','Evidence')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>'+copy('لا توجد ملاحظات مطابقة.','No matching findings.')+'</p>')+'</section></div>';
}
