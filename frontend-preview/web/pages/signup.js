function signup(){
  return '<section class="login">'+authClose()+'<h1>'+copy('إنشاء حساب','Create account')+'</h1><p>'+copy('يراجع مسؤول الشركة طلبك قبل تفعيل الحساب.','Your company admin reviews your request before activation.')+'</p><form id="sign-up">'
    +'<label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" required autocomplete="username"></label>'
    +'<label class="field">'+copy('كلمة المرور (١٠ أحرف على الأقل)','Password (10 characters minimum)')+'<input type="password" name="password" minlength="10" maxlength="128" required autocomplete="new-password"></label>'
    +'<label class="field">'+copy('دور الموظف','Requested role')+'<select name="role">'+['developer','qa','security'].map(id=>'<option value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'
    +'<button class="primary">'+copy('إرسال طلب الحساب','Submit account request')+'</button></form><a href="/login">'+copy('تسجيل الدخول','Sign in')+'</a></section>';
}
