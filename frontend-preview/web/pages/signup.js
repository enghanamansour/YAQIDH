function signup(){
  return '<section class="login">'+authClose()+'<h1>'+copy('إنشاء حساب','Create account')+'</h1><p>'+copy('يُفعّل حسابك فور التسجيل.','Your account is active as soon as you register.')+'</p><form id="sign-up">'
    +'<label class="field">'+copy('اسم المستخدم (إنجليزي وأرقام، 3 أحرف أو أكثر)','Username (English letters and digits, 3+ characters)')+'<input name="account" required autocomplete="username" autocapitalize="none" spellcheck="false" pattern="[A-Za-z][A-Za-z0-9._-]{2,31}"></label>'
    +'<label class="field">'+copy('الاسم الظاهر (اختياري)','Display name (optional)')+'<input name="display" maxlength="40" autocomplete="name"></label>'
    +'<label class="field">'+copy('كلمة المرور (١٠ أحرف على الأقل)','Password (10 characters minimum)')+'<input type="password" name="password" minlength="10" maxlength="128" required autocomplete="new-password"></label>'
    +'<label class="field">'+copy('دور الموظف','Requested role')+'<select name="role">'+['developer','qa','security'].map(id=>'<option value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'
    +'<button class="primary">'+copy('إنشاء الحساب','Create account')+'</button></form><a href="/login">'+copy('تسجيل الدخول','Sign in')+'</a></section>';
}
