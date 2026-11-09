function dashboardView(){
  return profile.role==='developer'?developerView():reviewView();
}
