function signup(){
  return '<section class="login">'+authClose()+'<h1>'+copy('إنشاء حساب','Create account')+'</h1><form id="sign-up">'
    +'<label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" required autocomplete="username" autocapitalize="none" spellcheck="false" pattern="[A-Za-z][A-Za-z0-9._-]{2,31}"></label>'
    +'<label class="field">'+copy('كلمة المرور','Password')+'<input type="password" name="password" minlength="10" maxlength="128" required autocomplete="new-password"></label>'
    +'<label class="field">'+copy('دور الموظف','Requested role')+'<select name="role">'+['developer','qa','security'].map(id=>'<option value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'
    +'<button class="primary">'+copy('إنشاء الحساب','Create account')+'</button></form><a href="/login">'+copy('تسجيل الدخول','Sign in')+'</a></section>';
}
