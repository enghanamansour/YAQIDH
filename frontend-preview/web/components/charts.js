function adminTimeline(runs,developer=false){
  const heading=developer?copy('اتجاه نتائج الأبنية المسندة','Assigned build trend'):copy('تشغيل وكيل يقظ عبر الزمن','YAQIDH agent runs over time');
  const totalLabel=developer?copy('إجمالي الأبنية','Total builds'):copy('تشغيلات الوكيل','Agent runs');
  const failureLabel=developer?copy('أبنية أخفقت','Failed builds'):copy('تشغيلات الوكيل المتعطلة','Failed agent runs');
  const actionName=developer?'developer-day':'agent-day';
  const selectedDay=null;
  const days=[...new Set(runs.map(run=>run.day).filter(Boolean))].sort();
  if(!days.length)return '<section class="panel admin-trend"><h2>'+heading+'</h2><p class="muted">'+copy('لا توجد تشغيلات مؤرخة في النطاق المحدد.','No dated runs match the selected scope.')+'</p></section>';
  const totals=days.map(day=>runs.filter(run=>run.day===day).length);
  const errors=days.map(day=>runs.filter(run=>run.day===day&&run.state==='error').length);
  const max=Math.max(2,...totals);
  const x=i=>days.length===1?300:43+i*518/(days.length-1);
  const y=n=>162-132*n/max;
  const poly=counts=>counts.map((n,i)=>x(i)+','+y(n)).join(' ');
  const scale=[0,Math.ceil(max/2),max].filter((value,index,list)=>list.indexOf(value)===index);
  return '<section class="panel admin-trend"><div class="section-head"><h2>'+heading+'</h2>'+badge(copy('سجل تجريبي مؤرخ','Dated demo history'))+'</div>'
    +'<p class="muted">'+ (developer?copy('الأبنية المسندة يوميًا حسب تاريخ سجل المعاينة. اختر يومًا لتصفية قائمة الأبنية.','Assigned builds by dated demo record. Select a day to filter the build list.'):copy('تشغيلات الوكيل وتعطلاته يوميًا في سجل المعاينة. اختر يومًا لعرض التفاصيل.','Daily agent runs and failures in the demo history. Select a day for details.'))+'</p>'
    +'<svg class="admin-line" viewBox="0 0 600 202" role="img" aria-label="'+copy('التشغيلات والمتعطل حسب اليوم','Daily runs and failures')+'">'
    +scale.map(n=>'<path class="line-grid" d="M43 '+y(n)+'H561"/><text x="30" y="'+(y(n)+4)+'">'+n+'</text>').join('')
    +(days.length>1?'<polygon class="line-area" points="'+x(0)+',162 '+poly(totals)+' '+x(days.length-1)+',162"/>':'')
    +'<polyline class="line-total" points="'+poly(totals)+'"/><polyline class="line-errors" points="'+poly(errors)+'"/>'
    +days.map((day,i)=>'<g class="line-point" role="button" data-action="'+actionName+'" data-id="'+day+'"'+(developer?' aria-pressed="'+(selectedDay===day)+'"':'')+' tabindex="0" aria-label="'+day+' · '+totalLabel+' '+totals[i]+' · '+failureLabel+' '+errors[i]+'"><title>'+day+' · '+totalLabel+' '+totals[i]+' · '+failureLabel+' '+errors[i]+'</title><circle class="line-dot total" cx="'+x(i)+'" cy="'+y(totals[i])+'" r="4"/><circle class="line-dot error" cx="'+x(i)+'" cy="'+y(errors[i])+'" r="3"/><text x="'+x(i)+'" y="186">'+day.slice(5)+'</text></g>').join('')
    +'</svg><div class="actions"><span class="trend-key">'+totalLabel+'</span><span class="trend-key errors">'+failureLabel+'</span></div></section>';
}

function toolRunChart(runs,developer=false){
  const keys=developer?['pass','fail','pending']:['completed','error','pending'];
  const labels=developer?[copy('اجتاز','Passed'),copy('أخفق','Failed'),copy('قيد الانتظار','Pending')]:stateLabels().map(([,label])=>label);
  const interactive=profile.role!=='qa';
  const selected=developer?developerOutcome:runFilter;
  const act=developer?'developer-outcome':'run-state';
  const states=['completed','error','pending'];
  const bins=states.map((state,i)=>[keys[i],labels[i],['good','bad','wait'][i],runs.filter(run=>run.state===state).length]);
  let offset=0;
  const segments=bins.map(([id,label,tone,count])=>{
    if(!count)return '';
    const length=count/runs.length*100;
    const tip=label+' · '+fraction(count,runs.length);
    const controls=interactive?' role="button" data-action="'+act+'" data-id="'+id+'" aria-pressed="'+(selected===id)+'" tabindex="0"':'';
    const result='<circle class="chart-ring '+tone+(interactive?'':' chart-ring-static')+'"'+controls+' aria-label="'+tip+'" cx="54" cy="54" r="39" pathLength="100" stroke-dasharray="'+length+' '+(100-length)+'" stroke-dashoffset="'+(-offset)+'"><title>'+tip+'</title></circle>';
    offset+=length;
    return result;
  }).join('');
  const selectedCount=bins.find(([id])=>id===selected)?.[3];
  return '<section class="panel"><h2>'+(developer?copy('نتائج الأبنية المسندة','Assigned build outcomes'):copy('اكتمال تشغيل الأدوات','Tool run completion'))+'</h2><div class="chart-ring-layout">'
    +'<svg viewBox="0 0 108 108" class="chart-donut" role="group" aria-label="'+copy('توزيع الحالات','Status distribution')+'"><circle class="chart-ring-track" cx="54" cy="54" r="39"/>'+segments+'<text x="54" y="58">'+(selectedCount??runs.length)+'</text></svg>'
    +'<div>'+bins.map(([id,label,tone,count])=>'<p>'+(interactive?action(act,label+' · '+count,'class="badge '+tone+'" data-id="'+id+'" aria-pressed="'+(selected===id)+'" title="'+label+' · '+fraction(count,runs.length)+'"'):badge(label+' · '+count,tone))+'</p>').join('')+'</div></div>'
    +'<small>'+(runs.length?(developer?copy('التوزيع لكل الأبنية المسندة؛ الرقم يبيّن الحالة المختارة.','Distribution of all assigned builds; the number reflects the selection.'):copy('اكتمال التشغيل منفصل عن اجتياز الفحص.','Run completion is separate from passing a check.')):copy('لا توجد تشغيلات في النطاق المحدد.','No runs in the selected scope.'))+'</small></section>';
}

function shieldChart(){
  const tone=release.outcome?.result==='pass'?'good':release.outcome?.result==='fail'?'bad':'wait';
  return '<section class="panel"><h2>'+copy('درع نتيجة المرحلة','Stage outcome shield')+'</h2>'
    +'<div class="shield-chart '+tone+'"><svg viewBox="0 0 140 145" aria-hidden="true"><path class="shield-outer" d="M70 6 131 26v46c0 35-26 53-61 68C35 125 9 107 9 72V26Z"/><path class="shield-inner" d="M70 15 122 32v40c0 30-22 46-52 59C40 118 18 102 18 72V32Z"/></svg>'
    +'<div class="shield-content"><strong>'+outcomeText()+'</strong><small>'+safe(buildName(release.build))+'</small></div></div><small>'+copy('محرك القواعد · البناء كاملًا','Policy engine · full build')+'</small></section>';
}

function findingLabel(key){return ({open:copy('قيد التنفيذ','In progress'),fixed:copy('مغلقة','Closed'),excepted:copy('مستثناة','Excepted')})[key]||''}

function bugChart(rows){
  const counts=[['open',copy('قيد التنفيذ','In progress'),'bad'],['fixed',copy('مغلقة','Closed'),'good'],['excepted',copy('مستثناة','Excepted'),'wait']];
  return '<section class="panel"><h2>'+(profile.role==='qa'?copy('حالة ملاحظات الجودة','QA finding status'):copy('حالة الثغرات والملاحظات','Vulnerability and finding status'))+'</h2><div class="bug-chart">'
    +'<svg viewBox="0 0 230 140" preserveAspectRatio="none" aria-hidden="true"><path d="M41 51 20 39H5m36 32H5m36 25-21 14H5m184-59 21-12h15m-36 32h36m-36 25 21 14h15M55 25h120l14 15v72l-14 15H55l-14-15V40Z"/><path class="bug-head" d="M89 24 101 8h28l12 16v16H89Z"/></svg><b class="bug-total" title="'+copy('إجمالي الملاحظات المطابقة','Total matching findings')+'">'+rows.length+'</b><div class="bug-counts">'
    +counts.map(([key,label,tone])=>'<button type="button" data-action="finding-group" data-id="'+key+'" class="'+tone+'" aria-pressed="'+(findingFilter===key)+'" title="'+label+' · '+fraction(rows.filter(f=>findingGroup(f)===key).length,rows.length)+'"><span>'+label+'</span><progress value="'+rows.filter(f=>findingGroup(f)===key).length+'" max="'+Math.max(rows.length,1)+'"></progress><b>'+rows.filter(f=>findingGroup(f)===key).length+'</b></button>').join('')
    +'</div></div><small>'+copy('تتغير مع فلتر الأداة والخطورة','Updates with tool and severity filters')+'</small></section>';
}

function qaChart(rows,title=copy('حالة ملاحظات الجودة','QA finding status')){
  const resolved=rows.filter(f=>f.closure?.result==='closed').length;
  const groups=[[copy('تحتاج معالجة','Needs remediation'),rows.filter(f=>f.status!=='excepted'&&f.closure?.result!=='closed').length,'bad'],
    [copy('إغلاق مثبت','Verified closed'),resolved,'good'],
    [copy('مستثناة','Excepted'),rows.filter(f=>f.status==='excepted'&&f.closure?.result!=='closed').length,'wait']];
  return '<section class="panel"><h2>'+title+'</h2>'
    +groups.map(([label,count,tone])=>'<div class="bar-row '+tone+'"><span>'+label+' <b>'+count+'</b></span><progress value="'+count+'" max="'+Math.max(1,rows.length)+'"></progress></div>').join('')
    +'<small>'+copy('يعرض الملاحظات المطابقة للفلاتر الحالية','Shows findings matching the active filters')+'</small></section>';
}

function stageCharts(){
  const runs=release.runs.filter(run=>tool==='all'||run.tool===tool);
  return '<div class="role-charts three">'+shieldChart()+bugChart(matched())+toolRunChart(runs)+'</div>';
}
