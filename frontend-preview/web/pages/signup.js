function signup(){
  return '<section class="login">'+authClose()+'<h1>'+copy('إنشاء حساب','Create account')+'</h1><p>'+copy('يراجع مسؤول الشركة طلبك قبل تفعيل الحساب.','Your company admin reviews your request before activation.')+'</p><form id="sign-up">'
    +'<label class="field">'+copy('اسم المستخدم','Username')+'<input name="account" required autocomplete="username" placeholder="example-user"></label>'
    +'<label class="field">'+copy('كلمة المرور (١٠ أحرف على الأقل)','Password (10 characters minimum)')+'<input type="password" name="password" minlength="10" maxlength="128" required autocomplete="new-password"></label>'
    +'<label class="field">'+copy('الدور المطلوب','Requested role')+'<select name="role">'+['developer','qa','security'].map(id=>'<option value="'+id+'">'+roleNames(id)+'</option>').join('')+'</select></label>'
    +'<label class="field">'+copy('رمز دعوة الشركة','Company invitation code')+'<input name="invitation" required></label><button class="primary">'+copy('إرسال طلب الحساب','Submit account request')+'</button></form><p class="muted">'+copy('رمز دعوة المعاينة','Demo invitation code')+' '+mon('YAQIDH-DEMO')+'</p><a href="/login">'+copy('تسجيل الدخول','Sign in')+'</a></section>';
}
