function dashboardView(){
  return profile.role==='developer'?developerView():profile.role==='qa'?reviewView():reviewView();
}
