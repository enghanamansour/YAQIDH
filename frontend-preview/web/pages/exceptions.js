/* The exceptions page: what the security team agreed to let through, who decided, when and why.
   An exception is only possible for a finding the tool itself rated MEDIUM, and only a person can grant it. */

function exceptionsView(){
  const title='<div class="intro"><div><h1>'+copy('الاستثناءات','Exceptions')+'</h1><small>'+copy('ما وافق عليه فريق الأمن ليمر مع البناء، ومن قرر ولماذا.','What the security team agreed to let through, who decided and why.')+'</small></div></div>';
  const report=release&&release.report;
  if(!release||!report)return '<main>'+title+'<section class="panel"><p class="muted">'+copy('لا توجد بيانات حيّة للعرض. شغّل اللوحة على واجهة يقظ.','There is no live data to show. Run the dashboard against the Yaqidh API.')+'</p></section></main>';
  const picker=profile.releases.length>1?'<label class="field">'+copy('البناء','Build')+'<select id="release-select">'+profile.releases.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr))+' · '+safe(buildName(item.build))+'</option>').join('')+'</select></label>':'';
  const list=report.findings.filter(r=>r.exception);
  const blocked=new Set((release.blockerIds||[]));
  const card=r=>{
    const closed=r.closed_at!==null&&r.closed_at!==undefined;
    const counts=String(r.reported_as).toLowerCase()==='medium'&&!blocked.has(r.fingerprint);
    const result=closed?'<span class="badge good">'+copy('أُغلقت لاحقًا بالإصلاح','Closed later by a fix')+'</span>'
      :counts?'<span class="badge good">'+copy('مقبول: لا يمنع الدمج','Accepted: does not block the merge')+'</span>'
      :'<span class="badge bad">'+copy('لا يُحتسب: ما زالت تمنع الدمج','Not counted: still blocks the merge')+'</span>';
    return '<article class="panel exception-card"><div class="section-head"><div><h2>'+safe(reportName(r))+'</h2><small>'+mon(r.location)+' · '+safe(reportStage(r.stage))+'</small></div>'+result+'</div>'
      +'<div class="facts">'
      +'<div><small>'+copy('وافق عليه','Approved by')+'</small><b>'+safe(r.exception.approved_by)+'</b></div>'
      +'<div><small>'+copy('متى','When')+'</small><b>'+safe(reportDate(r.exception.at))+'</b></div>'
      +'<div><small>'+copy('تصنيف الأداة','Tool rating')+'</small><b>'+safe(reportRated(r))+'</b></div>'
      +'<div><small>'+copy('حالة الملاحظة الآن','Finding now')+'</small><b>'+safe(reportStatus(r))+'</b></div></div>'
      +'<div class="exc"><small>'+copy('السبب الذي كتبه','The reason given')+'</small><p>'+safe(r.exception.justification)+'</p></div></article>';
  };
  const body=list.length?list.map(card).join(''):'<section class="panel"><p class="muted">'+copy('لم يوافق فريق الأمن على أي استثناء في هذا البناء بعد.','The security team has not accepted any exception in this build yet.')+'</p></section>';
  const rule='<section class="panel"><p class="muted">'+copy('القاعدة: يُسمح بالاستثناء فقط لملاحظة صنّفتها الأداة نفسها «متوسطة» وبسبب مكتوب من مراجع الأمن. الملاحظات العالية والحرجة لا تُستثنى أبدًا.','The rule: an exception is allowed only for a finding the tool itself rated medium, with a written reason from the security reviewer. High and critical findings are never excepted.')+'</p></section>';
  return '<main>'+title+(picker?'<section class="panel">'+picker+'</section>':'')+rule+body+'</main>';
}
