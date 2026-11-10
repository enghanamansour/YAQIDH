function animatedLogo(){
  return '<span class="animated-logo"><img class="logo-body" alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"><img class="logo-loop" alt="" aria-hidden="true" src="'+logo()+'"></span>';
}
function header(){
  const ar=document.documentElement.lang==='ar', theme=document.documentElement.dataset.theme;
  const toggle=(id,label,active)=>action(id,label,'aria-pressed="'+active+'"');
  return '<header class="top"><div class="top-navigation"><a class="top-logo" href="/" aria-label="'+copy('يقظ · الرئيسية','YAQIDH · Home')+'"><img class="brand" alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"></a><nav aria-label="'+copy('التنقل العام','Main navigation')+'">'+'<a href="/#about">'+copy('عن يقظ','About YAQIDH')+'</a>'+'</nav></div>'
    +'<div class="toolbar"><div class="top-control" role="group" aria-label="'+copy('اللغة','Language')+'">'+toggle('ar',copy('العربية','Arabic'),ar)+toggle('en',copy('الإنجليزية','English'),!ar)+'</div>'
    +'<div class="top-control" role="group" aria-label="'+copy('المظهر','Appearance')+'">'+toggle('light',copy('☀ فاتح','☀ Light'),theme==='light')+toggle('dark',copy('☾ غامق','☾ Dark'),theme==='dark')+'</div></div></header>';
}

function sidebar(){
  const nav=(href,label,mark)=>'<a href="'+href+'" '+(location.pathname===href?'aria-current="page"':'')+'><span aria-hidden="true">'+mark+'</span>'+label+'</a>';
  return '<aside class="sidebar"><a href="/" aria-label="'+copy('يقظ','YAQIDH')+'"><img class="brand" alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"></a><nav aria-label="'+copy('التنقل','Navigation')+'">'
    +nav(profile?.role==='company-admin'?'/admin':'/dashboard',copy('لوحة المتابعة','Dashboard'),'▦')
    +(profile&&profile.role!=='company-admin'?nav('/exceptions',copy('الاستثناءات','Exceptions'),'◈'):'')
    +(profile?nav('/communication',copy('التواصل','Communication')+(unreadCount()?' · '+unreadCount():''),'◌'):'')
    +(profile?.role==='company-admin'?nav('/admin#accounts',copy('إدارة الحسابات','Account administration'),'◇'):'')
    +'</nav><div class="sidebar-account">'+(profile?'<b>'+roleNames(profile.role)+'</b>'+action('logout',copy('تسجيل الخروج','Sign out')):'<a class="action" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a>')+'</div></aside>';
}
