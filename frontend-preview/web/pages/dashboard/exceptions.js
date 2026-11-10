/* The security reviewer decides what happens to findings the tool rated MEDIUM.
   Yaqidh never decides this: only a person with a written reason can accept one, and high findings never appear here. */

function exceptionPanel(){
  if(profile.role!=='security'||!release||!release.live)return '';
  const medium=release.findings.filter(f=>f.reported_as==='medium');
  const title='<h2>'+copy('الملاحظات المتوسطة: قرارك','Medium findings: your decision')+'</h2>';
  if(!medium.length)return '';
  const open=medium.filter(f=>f.status==='open'),done=medium.filter(f=>f.status==='excepted');
  const line=f=>'<li><label><input type="checkbox" name="finding" value="'+safe(f.fingerprint)+'" checked> <b>'+safe(findingName(f))+'</b> <small>'+mon(f.location)+'</small></label></li>';
  const form=open.length?'<form id="exception-form" data-release="'+safe(release.id)+'"><ul class="exception-list">'+open.map(line).join('')+'</ul>'
    +'<button class="primary">'+copy('قبول المحدد','Accept selected')+'</button> <small class="muted">'+copy('غير المحدد يبقى مانعًا حتى يُصلَح.','Anything left unchecked keeps blocking until fixed.')+'</small></form>':'';
  const accepted=done.length?'<details><summary>'+copy('مقبولة سابقًا','Already accepted')+' ('+done.length+')</summary><ul>'+done.map(f=>'<li>'+safe(findingName(f))+' · '+safe(f.exception?f.exception.justification:'')+' · <small>'+safe(f.exception?f.exception.approved_by:'')+'</small></li>').join('')+'</ul></details>':'';
  return '<section class="panel" id="medium-panel">'+title+'<p class="muted">'+copy('صنّفتها الأداة «متوسطة». العالية لا تُستثنى أبدًا.','Rated medium by the tool. High is never excepted.')+'</p>'+form+accepted+'</section>';
}
