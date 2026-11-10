function developerStageHeading(stage){
  return '<b class="'+(stage==='qa'?'dev-stage-qa':'dev-stage-security')+'">'+safe(stageText(stage))+'</b>';
}

function developerPriority(returned){
  return '<section class="panel dev-priority"><h2>'+copy('يحتاج إجراء منك','Needs your action')+'</h2>'
    +(returned.length?returned.map(item=>'<article class="note dev-return"><div><b class="dev-finding-title">'+safe(requestName(item.pr))+'</b> · <b class="'+(item.active==='qa'?'dev-stage-qa':'dev-stage-security')+'">'+safe(stageText(item.active))+'</b><p><b class="dev-return-label">'+copy('سبب الإرجاع','Return reason')+'</b> · '+safe(item.returnReason?demoText(item.returnReason):copy('لم يُسجّل سبب للإرجاع','No return reason recorded'))+'</p><small>'+copy('عالج الملاحظة وارفع التعديل لإعادة الفحص.','Address the finding and resubmit the change for checking.')+'</small></div>'
    +action('returned-build',copy('عرض سبب الإرجاع','View return reason'),'data-id="'+safe(item.id)+'"')+'</article>').join(''):'<p>'+copy('لا توجد تعديلات معادة إليك.','No changes have been returned to you.')+'</p>')+'</section>';
}

function developerBuildName(item){
  const stage=item.stages?.[item.active||item.stage];
  return copy(stage?.hasResult?'النسخة المفحوصة':'النسخة','Build')+' #'+item.build;
}

function developerResultStage(item,stage){
  if(stage!=='all')return stage;
  const current=item.active||item.stage;
  if(current==='security'&&!['pass','fail'].includes(item.stages?.security?.status)
      &&['pass','fail'].includes(item.stages?.qa?.status))return 'qa';
  return current;
}

function developerStageResult(item,stage){
  return item.stages?.[developerResultStage(item,stage)]?.status;
}

function developerResultLabel(status){
  return {pass:copy('اجتاز','Passed'),fail:copy('أخفق','Failed')}[status]||'—';
}

function developerReturnRecord(item){
  return '<article class="note"><b>'+safe(requestName(item.pr)+' · '+developerBuildName(item))+'</b><dl>'
    +'<dt>'+copy('المرحلة','Stage')+'</dt><dd>'+developerStageHeading(item.active)+'</dd>'
    +'<dt>'+copy('سبب الإرجاع','Return reason')+'</dt><dd>'+safe(item.returnReason?demoText(item.returnReason):copy('لم يُسجّل سبب للإرجاع','No return reason recorded'))+'</dd>'
    +'<dt>'+copy('المطلوب منك','Next action')+'</dt><dd>'+copy('عالج الملاحظة وارفع التعديل على طلب الدمج نفسه لإعادة الفحص.','Address the finding and update the same pull request to rerun checks.')+'</dd></dl>'
    +action('queue',copy('عرض الملاحظات والأدلة','View findings and evidence'),'data-id="'+safe(item.id)+'"')+'</article>';
}

function developerBuildRecord(item){
  return safe(requestName(item.pr)+' · '+developerBuildName(item))+' '
    +action('queue',copy('عرض التفاصيل','View details'),'data-id="'+safe(item.id)+'"');
}

function developerStagePath(){
  return '<section class="panel"><div class="section-head"><h2>'+copy('مسار النسخة المختارة','Selected build path')+'</h2><b>'+safe(developerBuildName(release))+'</b></div>'
    +(release.version?'<p>'+copy('الإصدار','Version')+' '+mon(release.version)+'</p>':'')
    +'<div class="role-charts">'+['qa','security'].map(name=>{
      const stage=release.stages?.[name];
      const result=stage?developerResultLabel(stage.status):name==='security'&&release.stage==='qa'?copy('لم يصل لهذه المرحلة','Not reached'):copy('الدليل غير متاح','Evidence unavailable');
      const reviewer=stage?.decision?statusText(stage.decision.decision):stage?.status==='pass'?copy('بانتظار المراجعة','Awaiting review'):'—';
      const next=stage?.decision?.decision==='reject'||stage?.status==='fail'?copy('راجع الملاحظات وارفع الإصلاح.','Review findings and submit the fix.'):
        '';
      const stageColor=name==='qa'?'dev-stage-qa':'dev-stage-security';
      const resultTone={pass:'good',fail:'bad'}[stage?.status]||'';
      const reviewerTone={approve:'good',reject:'bad'}[stage?.decision?.decision]||'';
      return '<article class="note dev-status-colors"><h3 class="'+stageColor+'">'+stageText(name)+'</h3>'
        +'<p>'+copy('نتيجة التحقق','Check result')+' · '+badge(result,resultTone)+'</p>'
        +'<p>'+copy('قرار المراجع','Reviewer decision')+' · '+(reviewer==='—'?'<span class="muted">—</span>':badge(reviewer,reviewerTone))+'</p>'
        +(next?'<p>'+next+'</p>':'')+(stage?.status==='fail'&&name===release.stage?action('developer-evidence',copy('عرض الملاحظات والأدلة','View findings and evidence')):'')+'</article>';
    }).join('')+'</div></section>';
}

function developerDonut(versions){
  const bins=[['pass','good'],['fail','bad']];
  const pool=versions.filter(item=>bins.some(([id])=>developerStageResult(item,developerStage)===id));
  let offset=0;
  const segments=[];
  const legend=[];
  for(const [id,tone] of bins){
    const count=pool.filter(item=>developerStageResult(item,developerStage)===id).length;
    const label=developerResultLabel(id);
    const length=pool.length?100*count/pool.length:0;
    const scope=developerStage==='all'?copy('آخر نتيجة مسجّلة لكل نسخة','Latest recorded result per build'):stageText(developerStage);
    const tip=safe(scope+' · '+label+' · '+count+' · '+Math.round(length)+'%');
    const attrs=' data-action="developer-outcome" data-id="'+id+'" aria-pressed="'+(developerOutcome===id)+'" aria-label="'+tip+'"';
    if(count)segments.push('<circle class="chart-ring '+tone+'" role="button" tabindex="0"'+attrs+' cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="'+length+' '+(100-length)+'" stroke-dashoffset="'+(-offset)+'"><title>'+tip+'</title></circle>');
    offset+=length;
    legend.push('<button type="button" class="dev-donut-item '+tone+'"'+attrs+' title="'+tip+'"><span class="dev-donut-dot" aria-hidden="true"></span><span>'+safe(label)+'</span><b>'+count+'</b></button>');
  }
  return '<section class="panel dev-donut-panel dev-status-colors"><div class="dev-donut-heading"><h2>'+copy('نتائج النسخ المسندة','Assigned Build Results')+'</h2>'
    +adminSelect('developer-stage',copy('مسار الفحص','Check pipeline'),developerStage,[['qa',copy('الجودة','Quality')],['security',copy('الأمن','Security')]])+'</div><div class="chart-ring-layout">'
    +'<svg class="chart-donut" viewBox="0 0 108 108" role="group" aria-label="'+copy('توزيع نتائج النسخ','Build result distribution')+'"><circle class="chart-ring-track" cx="54" cy="54" r="39"/>'+segments.join('')
    +'<text class="dev-donut-total" x="54" y="53">'+pool.length+'</text><text class="dev-chart-caption" x="54" y="65">'+copy('نتائج التحقق','Check results')+'</text></svg><div class="dev-donut-legend">'+legend.join('')+'</div></div>'
    +(pool.length?'':'<p>'+copy('لا توجد نتائج تحقق مسجّلة لهذا المسار.','No recorded check results for this pipeline.')+'</p>')+'</section>';
}

function developerRemediationBars(findings){
  const bins=[['open','bad',copy('تحتاج معالجة','Needs remediation')],['fixed','good',copy('إغلاق مثبت','Verified closure')],['excepted','wait',copy('مستثناة','Excepted')]];
  const total=findings.length;
  const counts=bins.map(([id])=>findings.filter(f=>findingGroup(f)===id).length);
  const scaleMax=(Math.floor(Math.max(...counts)/5)+1)*5;
  return '<section class="panel"><h2>'+copy('حالات المعالجة','Remediation status')+'</h2><p>'+safe(developerBuildName(release))+'</p><div class="dev-remediation-bars">'
    +bins.map(([id,tone,label],index)=>{
      const count=counts[index];
      const tip=safe(label+' · '+count+'/'+total+' · '+developerBuildName(release));
      return '<button type="button" class="dev-remediation-bar '+tone+'" data-action="finding-group" data-id="'+id+'" aria-pressed="'+(findingFilter===id)+'" aria-label="'+tip+'" title="'+tip+'">'
        +'<span class="dev-remediation-label"><span>'+label+'</span><b>'+count+'</b></span>'
        +'<svg class="dev-remediation-track" viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true"><rect width="'+(count/scaleMax*100)+'" height="12"/></svg></button>';
    }).join('')+'</div><div class="dev-bar-scale"><span>'+copy('عدد الملاحظات','Finding count')+'</span><bdi>0–'+scaleMax+'</bdi></div></section>';
}

function developerFindingTarget(id){
  if(dialog.open)dialog.close();
  const target=[...app.querySelectorAll('[data-developer-finding]')].find(row=>row.dataset.developerFinding===id)||document.getElementById('developer-evidence');
  target?.focus({preventScroll:true});
  target?.scrollIntoView({block:'nearest'});
}

function developerEvidence(findings){
  const decision=lastDecision();
  const scanTypes={semgrep:copy('فحص الكود','Code scanning'),trivy:copy('فحص المكتبات','Dependency scanning'),playwright:copy('اختبار الجودة','Quality test')};
  return '<section class="panel" id="developer-evidence" tabindex="-1"><h2>'+copy('الملاحظات والأدلة','Findings and evidence')+'</h2><p>'
    +safe(requestName(release.pr)+' · '+developerBuildName(release))+' · '+developerStageHeading(release.stage)+' · '+mon(release.commit)+'</p><h3>'+copy('ملاحظات الفحص','Scan findings')+'</h3>'
    +(findings.length?findings.map(f=>'<article class="note dev-return" tabindex="-1" data-developer-finding="'+safe(f.fingerprint)+'"><div><b class="dev-finding-title">'+safe(findingName(f))+'</b> · '+findingState(f)
      +'<p>'+copy('رصدتها','Detected by')+' · '+toolLabel(f.tool)+(scanTypes[f.tool]?' · '+scanTypes[f.tool]:'')+'</p>'
      +(f.explanation?.text?'<p>'+copy('كتب الشرح','Explanation author')+' · <b class="yaqidh-author">'+copy('وكيل يقظ','YAQIDH agent')+'</b><br>'+safe(demoText(f.explanation.text))+'</p>':'<small>'+copy('لم يُسجّل شرح لهذه الملاحظة.','No explanation recorded.')+'</small>')+'</div>'
      +action('finding',copy('فتح الدليل','Open evidence'),'data-id="'+safe(f.fingerprint)+'"')+'</article>').join(''):'<p>'+copy('لا توجد ملاحظات مطابقة.','No matching findings.')+'</p>')
    +'<h3>'+copy('قرار المراجع','Reviewer decision')+'</h3>'
    +(decision?'<article class="note"><b>'+statusText(decision.decision)+'</b><p><b class="'+(decision.stage==='qa'?'dev-stage-qa':'dev-stage-security')+'">'+safe(decision.by?accountName(demoText(decision.by))+' · ':'')+roleNames(decision.stage)+'</b></p><p>'
      +safe(decision.reason?demoText(decision.reason):copy('لم يُسجّل سبب للإرجاع','No return reason recorded'))+'</p></article>':'<p>'+copy('لا يوجد قرار مسجّل لهذه النسخة.','No decision recorded for this build.')+'</p>')+'</section>';
}

function assignedBuildTable(builds){
  const rows=builds.filter(item=>['pass','fail'].includes(developerStageResult(item,developerStage)));
  return '<section class="panel dev-status-colors"><h2>'+copy('النسخ المسندة','Assigned builds')+'</h2><div class="table-wrap"><table><thead><tr><th>'+copy('طلب الدمج','Pull request')+'</th><th>'+copy('النسخة','Build')+'</th><th>'+copy('المرحلة','Stage')+'</th><th>'+copy('نتيجة التحقق','Check result')+'</th><th>'+copy('الإجراء','Action')+'</th></tr></thead><tbody>'+rows.map(item=>{
    const stage=developerStage==='all'?item.active:developerStage;
    const resultStage=developerResultStage(item,developerStage);
    const result=developerStageResult(item,developerStage);
    const tone={pass:'good',fail:'bad'}[result];
    const stageTone=stage==='qa'?'dev-stage-qa':'dev-stage-security';
    const priorResult=resultStage!==stage?'<small class="dev-result-stage '+(resultStage==='qa'?'dev-stage-qa':'dev-stage-security')+'">'
      +(resultStage==='qa'?copy('النتيجة من مسار الجودة','Result from QA pipeline'):copy('النتيجة من مسار الأمن','Result from security pipeline'))+'</small>':'';
    return '<tr><td>'+safe(requestName(item.pr))+'</td><td>'+safe(developerBuildName(item))+'</td><td><b class="'+stageTone+'">'+stageText(stage)+'</b>'+priorResult+'</td><td>'+badge(developerResultLabel(result),tone)+'</td><td>'
      +action('queue',copy('عرض التفاصيل','View details'),'data-id="'+safe(item.id)+'"')+'</td></tr>';
  }).join('')+'</tbody></table></div>'+(rows.length?'':'<p>'+copy('لا توجد نسخ مطابقة.','No matching builds.')+' '+action('clear',copy('مسح الكل','Clear all'))+'</p>')+'</section>';
}

function developerView(){
  if(!release)return '<section class="panel">'+copy('لا توجد تعديلات مسندة إلى حسابك.','No changes are assigned to your account.')+'</section>';
  const pool=profile.releases.filter(item=>developerStageResult(item,developerStage));
  const assigned=pool.filter(item=>developerOutcome==='all'||developerStageResult(item,developerStage)===developerOutcome);
  const selected=assigned.some(item=>item.id===release.id);
  const latestByRequest=new Map();
  for(const item of profile.releases){
    const key=item.project+'/'+item.pr;
    if(!latestByRequest.has(key)||latestByRequest.get(key).build<item.build)latestByRequest.set(key,item);
  }
  const currentReturns=[...latestByRequest.values()].filter(item=>item.stages?.[item.active]?.decision?.decision==='reject');
  const returns=currentReturns.filter(item=>assigned.includes(item));
  const requests=[...new Map(assigned.map(item=>[item.project+'/'+item.pr,item])).values()];
  const findings=selected?matched():[];
  const pending=findings.filter(f=>findingGroup(f)==='open');
  const fixed=findings.filter(f=>findingGroup(f)==='fixed');
  const requestsScope=copy('ضمن طلباتك المسندة','Within your assigned pull requests');
  const buildScopeText=copy('في النسخة المحددة','Within the selected build');
  const findingDetails=f=>safe(findingName(f))+' '+action('developer-evidence',copy('عرض الملاحظة','View finding'),'data-id="'+safe(f.fingerprint)+'"');
  return '<div class="developer-workspace">'+developerPriority(currentReturns)
    +'<section class="panel filters"><label>'+copy('طلب الدمج والنسخة المفحوصة','Pull request and build')+'<select id="release-select">'
    +(!selected?'<option value="" selected disabled>'+copy('اختر نسخة مطابقة','Select a matching build')+'</option>':'')
    +assigned.map(item=>'<option value="'+safe(item.id)+'" '+(item.id===release.id?'selected':'')+'>'+safe(requestName(item.pr)+' · '+developerBuildName(item))+'</option>').join('')+'</select></label>'
    +adminSelect('finding-filter',copy('حالة المعالجة','Remediation status'),findingFilter,[['open',copy('تحتاج معالجة','Needs remediation')],['fixed',copy('إغلاق مثبت','Verified closure')],['excepted',copy('مستثناة','Excepted')]])+'</section>'
    +chipRow([['finding',findingFilter,copy('حالة المعالجة','Remediation status')],['developer-stage',developerStage,stageText(developerStage)],['developer-outcome',developerOutcome,developerResultLabel(developerOutcome)]],'clear')
    +(selected?developerStagePath():'<p class="note">'+copy('اختر نسخة مطابقة لعرض مسارها وأدلتها.','Select a matching build to view its path and evidence.')+'</p>')
    +'<div class="metric-row">'
    +metric(copy('طلبات الدمج المسندة','Assigned pull requests'),requests.length,'',requests,requestsScope,developerBuildRecord,requestsScope)
    +metric(copy('طلبات الدمج المعادة','Returned pull requests'),returns.length,'bad',returns,copy('طلبات رجعت لك وتحتاج تعديلًا','Pull requests returned to you for changes'),developerReturnRecord,requestsScope,{hideValue:true,empty:copy('ما عندك طلبات دمج معادة ضمن الفلاتر الحالية','No returned pull requests match the current filters.')})
    +(selected?metric(copy('تحتاج معالجة','Needs remediation'),pending.length,'wait',pending,buildScopeText,findingDetails,buildScopeText)
      +metric(copy('إغلاقات مثبتة','Verified closures'),fixed.length,'good',fixed,buildScopeText,findingDetails,buildScopeText):'')+'</div>'
    +'<div class="role-charts dev-result-charts">'+developerDonut(pool)+(selected?developerRemediationBars(release.findings):'')+'</div>'
    +assignedBuildTable(assigned)+(selected?developerEvidence(findings):'')+'</div>';
}
