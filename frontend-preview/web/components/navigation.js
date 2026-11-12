/* the name shown for the signed-in person: the display name, else the username, else (for a demo account named after its role) the role */
function personName(){return profile.display||(profile.account&&profile.account!==profile.role?profile.account:roleNames(profile.role))}
function animatedLogo(){
  return '<span class="animated-logo"><img class="logo-body" alt="'+copy('يَقِـــظ','YAQIDH')+'" src="'+logo()+'"><img class="logo-loop" alt="" aria-hidden="true" src="'+logo()+'"></span>';
}
/* only the company administrator has a sidebar (it has several real destinations); the other roles have one page, so the account sits in the top bar */
function hasSidebar(){return Boolean(profile&&profile.role==='company-admin')}
function headerAccount(){
  return '<div class="hdr-account"><button type="button" class="acct" data-action="account-menu" aria-expanded="false"><span class="avatar" aria-hidden="true">'+safe(Array.from(personName())[0])+'</span><span class="acct-text"><b>'+safe(personName())+'</b><small>'+roleNames(profile.role)+'</small></span><span class="chev" aria-hidden="true">⋯</span></button><div class="acct-menu" hidden>'+action('logout',copy('تسجيل الخروج','Sign out'))+'</div></div>';
}
function demoBadge(){return profile&&profile.guide?'<span class="demo-badge">'+copy('ديمو توضيحي','Guided demo')+'</span>':''}
function header(){
  // the main page is the same page for everyone: no account card and no demo badge up there; a demo visitor sees the sign-in button like any visitor
  const landing=location.pathname==='/';
  const showLogin=!['/login','/signup'].includes(location.pathname)&&(!profile||(landing&&Boolean(profile.guide)));
  const ar=document.documentElement.lang==='ar', theme=document.documentElement.dataset.theme;
  const toggle=(id,label,active,name)=>action(id,label,'aria-pressed="'+active+'" aria-label="'+name+'" title="'+name+'"');
  return '<header class="top"><div class="top-navigation"><a class="top-logo" href="/" aria-label="'+copy('يَقِـــظ · الرئيسية','YAQIDH · Home')+'"><img class="brand" alt="'+copy('يَقِـــظ','YAQIDH')+'" src="'+logo()+'"></a><nav aria-label="'+copy('التنقل العام','Main navigation')+'">'+(location.pathname==='/'?'<a href="#problem">'+copy('المشكلة','The problem')+'</a><a href="#about">'+copy('كيف يعمل','How it works')+'</a><a href="#features">'+copy('المميزات','Features')+'</a>':'')+'</nav></div>'
    +'<div class="toolbar"><div class="top-control" role="group" aria-label="'+copy('اللغة','Language')+'">'+(ar?toggle('en','EN',false,'English'):toggle('ar','ع',false,'العربية'))+'</div>'
    +'<div class="top-control" role="group" aria-label="'+copy('المظهر','Appearance')+'">'+(theme==='dark'?toggle('light','☀',false,copy('الوضع الفاتح','Light mode')):toggle('dark','☾',false,copy('الوضع الغامق','Dark mode')))+'</div>'+(showLogin?'<a class="action primary hdr-login" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a>':'')+(landing?'':demoBadge()+(profile&&!hasSidebar()?headerAccount():''))+'</div></header>';
}

const sbIcon=path=>'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+path+'</svg>';
const SB_ICONS={
  grid:'<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>',
  chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/>',
  users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 20a6.5 6.5 0 0 0-3-5.4"/>',
  shield:'<path d="M12 3 4 6v6c0 4.5 3.2 7.6 8 9 4.8-1.4 8-4.5 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>'
};
function sidebar(){
  const nav=(href,label,icon,badge)=>'<a href="'+href+'" '+(location.pathname===href?'aria-current="page"':'')+'>'+sbIcon(SB_ICONS[icon])+'<span class="sb-label">'+label+'</span>'+(badge?'<b class="sb-badge">'+badge+'</b>':'')+'</a>';
  const waiting=profile?(profile.releases||[]).filter(r=>r.active===profile.role&&r.pendingReview).length:0;
  const dashLabel=profile?.role==='qa'?copy('لوحة متابعة الجودة','QA dashboard'):copy('لوحة المتابعة','Dashboard');
  const account=profile?'<button type="button" class="acct" data-action="account-menu" aria-expanded="false"><span class="avatar" aria-hidden="true">'+safe(Array.from(personName())[0])+'</span><span class="acct-text"><b>'+safe(personName())+'</b><small>'+roleNames(profile.role)+'</small></span><span class="chev" aria-hidden="true">⋯</span></button><div class="acct-menu" hidden>'+action('logout',copy('تسجيل الخروج','Sign out'))+'</div>'
    :'<a class="action" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a>';
  return '<aside class="sidebar"><div class="sb-role">'+sbIcon(SB_ICONS.shield)+'<span><b>'+(profile?roleNames(profile.role):copy('يَقِـــظ','YAQIDH'))+'</b></span></div>'
    +'<nav aria-label="'+copy('التنقل','Navigation')+'"><p class="sb-title">'+copy('القائمة','Menu')+'</p>'
    +nav(profile?.role==='company-admin'?'/admin':'/dashboard',dashLabel,'grid',waiting||'')
    +(profile?.role==='company-admin'?nav('/communication',copy('مراسلات الموظفين','Employee messages'),'chat',unreadCount()||''):'')
    +(profile?.role==='security'?nav('/exceptions',copy('الاستثناءات','Exceptions'),'shield',''):'')
    +(profile?.role==='company-admin'?nav('/admin#accounts',copy('إدارة الحسابات','Account administration'),'users',''):'')
    +'</nav><div class="sidebar-account">'+account+'</div></aside>';
}
