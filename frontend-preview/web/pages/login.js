function authClose(){
  return '<a class="auth-close" href="/" aria-label="'+copy('إلغاء والعودة إلى الرئيسية','Cancel and return home')+'" title="'+copy('إلغاء والعودة إلى الرئيسية','Cancel and return home')+'">×</a>';
}

function login(){
  const requested=new URLSearchParams(location.search).get('account')||'';
  const accounts=['developer','qa','security','company-admin'].map(id=>'<option '+(id===requested?'selected ':'')+'value="'+id+'">'+roleNames(id)+'</option>').join('');
  return '<section class="login">'+authClose()+'<h1>'+copy('تسجيل الدخول إلى يقظ','Sign in to YAQIDH')+'</h1>'
    +'<form id="sign-in"><label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" autocomplete="username" value="'+safe(requested)+'" required></label><label class="field">'+copy('حساب عرض (اختياري)','Demo account (optional)')+'<select id="demo-account"><option value="">—</option>'+accounts+'</select></label>'
    +'<label class="field">'+copy('كلمة المرور','Password')+'<input name="password" type="password" required autocomplete="current-password"></label>'
    +'<button class="primary">'+copy('تسجيل الدخول','Sign in')+'</button></form><a href="/signup">'+copy('إنشاء حساب جديد','Create an account')+'</a></section>';
}
