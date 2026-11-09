/* The security reviewer decides what happens to findings the tool rated MEDIUM.
   Yaqidh never decides this: the policy only allows an exception for a finding the tool itself called medium,
   and only a person with a written reason can grant it. High findings never appear here. */

function exceptionPanel(){
  if(profile.role!=='security'||!release||!release.live)return '';
  const medium=release.findings.filter(f=>f.reported_as==='medium');
  const title='<h2>'+copy('قرار مسؤول الأمن على الملاحظات المتوسطة','Security decision on medium findings')+'</h2>';
  const intro='<p class="muted">'+copy('هذه ملاحظات صنّفتها الأداة نفسها «متوسطة». يقظ لا يقرر فيها: تُحجب حتى تقبلها أنت مع تبرير مكتوب، أو تتركها وتطلب الإصلاح. الملاحظات العالية لا تُستثنى أبدًا.','These findings were rated medium by the tool itself. Yaqidh does not decide on them: they block until you accept them with a written reason, or leave them and ask for a fix. High findings are never excepted.')+'</p>';
  if(!medium.length)return '<section class="panel">'+title+intro+'<p class="muted">'+copy('لا توجد ملاحظات متوسطة في هذا البناء.','There are no medium findings in this build.')+'</p></section>';
  const rows=medium.map(f=>{
    const name=safe(findingName(f))+'<br><small>'+mon(f.location)+'</small>'+(f.explanation?'<p>'+safe(f.explanation.text||'')+'</p>':'');
    if(f.status==='excepted'&&f.exception)return '<tr><td>'+name+'</td><td>'+copy('مقبولة بتبرير','Accepted with a reason')+'</td><td>'+safe(f.exception.justification)+'<br><small>'+safe(f.exception.approved_by)+'</small></td></tr>';
    if(f.status!=='open')return '<tr><td>'+name+'</td><td>'+safe(findingState(f))+'</td><td>—</td></tr>';
    return '<tr><td>'+name+'</td><td>'+copy('تنتظر قرارك','Waiting for your decision')+'</td><td><form id="exception-form" data-release="'+safe(release.id)+'" data-finding="'+safe(f.fingerprint)+'">'
      +'<label class="field">'+copy('تبرير القبول','Reason for accepting')+'<textarea name="justification" required minlength="10" maxlength="1000"></textarea></label>'
      +'<button class="primary">'+copy('قبول الاستثناء','Accept the exception')+'</button></form></td></tr>';
  }).join('');
  return '<section class="panel">'+title+intro+'<div class="table-wrap"><table><thead><tr><th>'+copy('الملاحظة','Finding')+'</th><th>'+copy('الحالة','Status')+'</th><th>'+copy('القرار','Decision')+'</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
