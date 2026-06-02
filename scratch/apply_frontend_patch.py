import re

file_path = "frontend/templates/dashboard.html"

with open(file_path, "r") as f:
    html_content = f.read()

old_logic = """  fetch(API+'/bills?t='+Date.now()).then(r=>r.json()).then(bls=>{
    allBills=bls;let tr=0,ytr=0,tb=0,ytb=0;
    const d=sD?new Date(sD):new Date();
    const ds=pd(d.getDate())+'/'+pd(d.getMonth()+1)+'/'+d.getFullYear();
    const yd=new Date(d); yd.setDate(d.getDate()-1);
    const yds=pd(yd.getDate())+'/'+pd(yd.getMonth()+1)+'/'+yd.getFullYear();
    
    bls.forEach(b=>{
      if(b.date.startsWith(ds)){tr+=b.total;tb++;}
      else if(b.date.startsWith(yds)){ytr+=b.total;ytb++;}
    });

    const isT = ds === (pd(new Date().getDate())+'/'+pd(new Date().getMonth()+1)+'/'+new Date().getFullYear());
    document.getElementById('kl-tb').textContent = isT ? 'Today Bills' : 'Bills on '+ds;
    document.getElementById('kl-tr').textContent = isT ? 'Today Revenue' : 'Revenue on '+ds;
    
    document.getElementById('kpi-tb').textContent=tb;
    document.getElementById('kpi-tr').textContent='₹'+tr.toLocaleString('en-IN');
    if(document.getElementById('kpi-au'))document.getElementById('kpi-au').textContent=(APP_USERS&&APP_USERS.length)||1;
    const b_diff=tb-ytb;
    document.getElementById('ks-tb').textContent=(b_diff>=0?'+':'')+b_diff+' vs prev day';
    const r_pct=ytr===0?0:(tr-ytr)/ytr*100;
    document.getElementById('ks-tr').textContent=(r_pct>=0?'+':'')+r_pct.toFixed(0)+'% vs prev day';
    const billBadge=document.querySelector('.rbn');
    if(billBadge)billBadge.textContent=editingBillId?`Editing ${editingBillId}`:'#B-'+(bls.length+heldBills.length+1);
    renderUtils();
    rMasters();
    rSys(sD);
    if(typeof generateWantedList==='function')generateWantedList();
    if(!sD){
      const todayIso = d.toISOString().split('T')[0];
      document.getElementById('sys-date').value = todayIso;
      document.getElementById('sys-date').max = todayIso;
    }
  });"""

new_logic = """  Promise.all([
    fetch(API+'/bills?limit=50&page=1&t='+Date.now()).then(r=>r.json()),
    fetch(API+'/bills/kpis?t='+Date.now()).then(r=>r.json())
  ]).then(([bls, kpis]) => {
    allBills = bls.items || [];
    let tr = kpis.today_revenue || 0,
        ytr = kpis.yesterday_revenue || 0,
        tb = kpis.today_bills || 0,
        ytb = kpis.yesterday_bills || 0;
        
    const d=sD?new Date(sD):new Date();
    const ds=pd(d.getDate())+'/'+pd(d.getMonth()+1)+'/'+d.getFullYear();
    const isT = ds === (pd(new Date().getDate())+'/'+pd(new Date().getMonth()+1)+'/'+new Date().getFullYear());
    
    document.getElementById('kl-tb').textContent = isT ? 'Today Bills' : 'Bills on '+ds;
    document.getElementById('kl-tr').textContent = isT ? 'Today Revenue' : 'Revenue on '+ds;
    
    document.getElementById('kpi-tb').textContent=tb;
    document.getElementById('kpi-tr').textContent='₹'+tr.toLocaleString('en-IN');
    if(document.getElementById('kpi-au'))document.getElementById('kpi-au').textContent=(APP_USERS&&APP_USERS.length)||1;
    
    const b_diff=tb-ytb;
    document.getElementById('ks-tb').textContent=(b_diff>=0?'+':'')+b_diff+' vs prev day';
    const r_pct=ytr===0?0:(tr-ytr)/ytr*100;
    document.getElementById('ks-tr').textContent=(r_pct>=0?'+':'')+r_pct.toFixed(0)+'% vs prev day';
    
    const billBadge=document.querySelector('.rbn');
    let totalAllTime = kpis.total_bills || 0;
    if(billBadge)billBadge.textContent=editingBillId?`Editing ${editingBillId}`:'#B-'+(totalAllTime+heldBills.length+1);
    
    renderUtils();
    rMasters();
    rSys(sD);
    if(typeof generateWantedList==='function')generateWantedList();
    if(!sD){
      const todayIso = d.toISOString().split('T')[0];
      document.getElementById('sys-date').value = todayIso;
      document.getElementById('sys-date').max = todayIso;
    }
  });"""

if old_logic in html_content:
    print("Found! Replaced.")
    html_content = html_content.replace(old_logic, new_logic)
    with open(file_path, "w") as f:
        f.write(html_content)
else:
    print("Not found... Trying soft match")
    # Clean both strings of whitespace
    import re
    norm_old = re.sub(r'\s+', '', old_logic)
    norm_content = re.sub(r'\s+', '', html_content)
    if norm_old in norm_content:
        print("Data is there, just whitespace difference.")
