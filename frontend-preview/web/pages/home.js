function landing(){
  return '<main class="landing"><div><img alt="'+copy('يقظ','YAQIDH')+'" src="'+logo()+'"><div class="actions"><a class="action primary" href="/login">'+copy('تسجيل الدخول','Sign in')+'</a><a class="action" href="/signup">'+copy('إنشاء حساب','Create account')+'</a></div></div><footer>'+ (profile?'<a href="'+(profile.role==='company-admin'?'/admin':'/dashboard')+'">'+copy('لوحة المتابعة','Dashboard')+'</a> · ':'')+'<a href="/about">'+copy('عن يقظ','About YAQIDH')+'</a></footer></main>';
}
