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
  return '<div class="developer-workspace">'+developerPriority()+developerReport()+'</div>';
}
