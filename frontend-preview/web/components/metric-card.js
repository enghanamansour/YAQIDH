function metric(label,value,tone='',rows=[],scope='',format=safe,caption='',options={}){
  const key=String(metricDetails.size);
  metricDetails.set(key,{label,value,rows,scope,format,options});
  return '<button type="button" class="metric '+tone+'" data-action="metric" data-id="'+key+'"><strong>'+value+'</strong><span>'+label+'</span>'+(caption?'<small>'+safe(caption)+'</small>':'')+'<small>'+copy('عرض التفاصيل','View details')+'</small></button>';
}

function showMetric(key){
  hideMetricTip();
  const entry=metricDetails.get(key);
  if(!entry)return;
  const body=entry.rows.length?'<ul class="metric-records">'+entry.rows.map(row=>'<li>'+entry.format(row)+'</li>').join('')+'</ul>':'<p class="muted">'+safe(entry.options.empty||copy('لا توجد سجلات مطابقة لهذا المؤشر.','No records match this metric.'))+'</p>';
  modal(entry.label,'<p class="metric-scope">'+safe(entry.scope)+'</p>'+(entry.options.hideValue?'':'<p><b>'+copy('القيمة المعروضة','Displayed value')+'</b> '+safe(entry.value)+'</p>')+body);
}
