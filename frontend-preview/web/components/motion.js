/* Life for the pages: a watching eye, numbers that count up, and navigation that does not reload the page. */

const reducedMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* The mark of the project: an eye that follows the cursor and blinks. Vigilant, as the name says. */
function eyeMark(){
  return '<svg class="eye-mark" viewBox="0 0 74 46" role="img" aria-label="'+copy('عين يقظ','YAQIDH eye')+'">'
    +'<defs><radialGradient id="irisGradient" cx="40%" cy="35%" r="75%"><stop offset="0" stop-color="#d9c9ff"/><stop offset=".55" stop-color="#8f6cf0"/><stop offset="1" stop-color="#4b2c9a"/></radialGradient></defs>'
    +'<g class="blink"><path class="white" d="M4 23C14 8 26 3 37 3s23 5 33 20C60 38 48 43 37 43S14 38 4 23Z"/>'
    +'<circle class="iris" cx="37" cy="23" r="14"/><circle class="pupil" cx="37" cy="23" r="7"/><circle class="glint" cx="32" cy="18" r="2.6"/>'
    +'<path class="lid" d="M4 23C14 8 26 3 37 3s23 5 33 20C60 38 48 43 37 43S14 38 4 23Z"/></g></svg>';
}

/* a hand-drawn line under a title */
function squiggle(){
  return '<svg class="squiggle" viewBox="0 0 150 12" aria-hidden="true"><path d="M3 7C15 1 25 11 37 6s22 5 34 0 22 5 34 0 22 5 42-1"/></svg>';
}

/* the pupil looks toward the cursor */
document.addEventListener('pointermove',event=>{
  if(reducedMotion)return;
  document.querySelectorAll('.eye-mark .pupil, .eye-mark .glint').forEach(part=>{
    const box=part.ownerSVGElement.getBoundingClientRect();
    const dx=event.clientX-(box.left+box.width/2),dy=event.clientY-(box.top+box.height/2);
    const distance=Math.hypot(dx,dy)||1,reach=part.classList.contains('glint')?3:6;
    const scale=Math.min(1,distance/220);
    part.style.transform='translate('+(dx/distance*reach*scale).toFixed(2)+'px,'+(dy/distance*reach*scale*.8).toFixed(2)+'px)';
  });
},{passive:true});

/* whole numbers count up from zero once, when a page is drawn */
function countUp(){
  if(reducedMotion)return;
  document.querySelectorAll('.metric strong, .report-tile strong').forEach(node=>{
    const text=node.textContent.trim();
    if(!/^\d{1,5}$/.test(text)||node.dataset.counted)return;
    node.dataset.counted='1';
    const target=Number(text),start=performance.now(),duration=650;
    const step=now=>{
      const t=Math.min(1,(now-start)/duration),eased=1-Math.pow(1-t,3);
      node.textContent=String(Math.round(target*eased));
      if(t<1)requestAnimationFrame(step);
    };
    node.textContent='0';requestAnimationFrame(step);
  });
}
new MutationObserver(()=>countUp()).observe(document.getElementById('app')||document.body,{childList:true});

/* moving between pages without reloading everything: the scripts and styles stay, only the data is fetched */
const progressBar=()=>document.getElementById('progress');
async function goTo(url){
  progressBar()?.classList.add('on');
  history.pushState(null,'',url);
  try{await load()}finally{progressBar()?.classList.remove('on')}
}
document.addEventListener('click',event=>{
  const link=event.target.closest('.sidebar nav a[href^="/"]');
  if(!link||event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  const target=new URL(link.href);
  if(target.origin!==location.origin||target.pathname==='/admin')return; // the admin page is served separately
  event.preventDefault();
  if(target.pathname+target.search===location.pathname+location.search)return;
  goTo(target.pathname+target.search);
});
window.addEventListener('popstate',()=>{if(typeof load==='function')load()});
