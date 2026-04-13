let rxBase64 = '';
function attachRx(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    const btn = document.getElementById('btn-rx');
    const prev = document.getElementById('rx-preview');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    
    // If it's a PDF, we can't compress with canvas - just use raw Base64
    if (file.type === 'application/pdf') {
        const reader = new FileReader();
        reader.onload = e => {
            rxBase64 = e.target.result;
            btn.innerHTML = `<i class="fas fa-check" style="color:#22c55e"></i> Prescription Attached (PDF)`;
            btn.style.borderColor = '#22c55e'; btn.style.color = '#22c55e';
            if(prev) { prev.style.display = 'none'; }
        };
        reader.readAsDataURL(file);
        return;
    }

    const img = new Image();
    const objUrl = URL.createObjectURL(file);
    img.onload = () => {
        try {
            const MAX_W = 800;
            const scale = Math.min(1, MAX_W / img.width);
            const canvas = document.createElement('canvas');
            canvas.width = img.width * scale;
            canvas.height = img.height * scale;
            canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
            rxBase64 = canvas.toDataURL('image/jpeg', 0.5);
            if(prev) { prev.src = rxBase64; prev.style.display = 'block'; }
            btn.innerHTML = `<i class="fas fa-check" style="color:#22c55e"></i> Prescription Attached`;
        } catch(e) {
            console.error('Compression failed, using raw:', e);
            btn.innerHTML = `<i class="fas fa-check" style="color:#22c55e"></i> Prescription Attached`;
        }
        URL.revokeObjectURL(objUrl);
    };
    img.onerror = () => {
        console.error('Image load failed, using raw FileReader fallback');
        const reader = new FileReader();
        reader.onload = e => {
            rxBase64 = e.target.result;
            btn.innerHTML = `<i class="fas fa-check" style="color:#22c55e"></i> Prescription Attached`;
            btn.style.borderColor = '#22c55e'; btn.style.color = '#22c55e';
        };
        reader.readAsDataURL(file);
    };
    img.src = objUrl;
  }
}
let faceStream = null;
async function triggerFaceScan() {
  if(!window.faceapi || !faceapi.nets.tinyFaceDetector.isLoaded) { alert('AI Models are still loading (about 5MB). Please try again in 5 seconds.'); return; }
  const modal = document.getElementById('face-modal');
  const vid = document.getElementById('face-vid');
  modal.style.display = 'flex';
  document.getElementById('face-status').textContent = 'Accessing camera...';
  document.getElementById('face-status').style.color = 'var(--tx)';
  
  try {
    faceStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user'}});
    vid.srcObject = faceStream;
    document.getElementById('face-status').textContent = 'Analyzing facial features...';
    
    setTimeout(async () => {
      const det = await faceapi.detectSingleFace(vid, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor();
      if(!det) {
         document.getElementById('face-status').textContent = 'No face detected. Try again.';
         document.getElementById('face-status').style.color = '#ef4444';
         setTimeout(() => { if(faceStream){ faceStream.getTracks().forEach(t=>t.stop()); faceStream=null; } modal.style.display='none';}, 1500);
         return;
      }
      
      const labeled = [];
      CUSTOMERS.forEach(c => {
         if(c.face_vector && c.face_vector.length > 50) {
            try {
               const arr = new Float32Array(JSON.parse(c.face_vector));
               labeled.push(new faceapi.LabeledFaceDescriptors(c.name + '|' + c.phone, [arr]));
            } catch(e){ console.error('Vector err:', e); }
         }
      });
      
      if(labeled.length === 0) {
         document.getElementById('face-status').textContent = 'Database empty. No enrolled faces.';
         document.getElementById('face-status').style.color = '#ef4444';
         setTimeout(() => { if(faceStream){ faceStream.getTracks().forEach(t=>t.stop()); faceStream=null; } modal.style.display='none';}, 2000);
         return;
      }
      
      const faceMatcher = new faceapi.FaceMatcher(labeled, 0.55);
      const bestMatch = faceMatcher.findBestMatch(det.descriptor);
      
      if(bestMatch.label === 'unknown') {
         document.getElementById('face-status').textContent = 'New Face! Enrolling temporarily...';
         document.getElementById('face-status').style.color = '#f5a623';
         
         let h=document.getElementById('pos-face-vector');
         if(!h){ h=document.createElement('input');h.type='hidden';h.id='pos-face-vector';document.body.appendChild(h); }
         h.value = JSON.stringify(Array.from(det.descriptor));
         
         setTimeout(() => { if(faceStream){ faceStream.getTracks().forEach(t=>t.stop()); faceStream=null; } modal.style.display='none'; document.getElementById('cn').focus(); }, 2000);
      } else {
         const [mName, mPhone] = bestMatch.label.split('|');
         document.getElementById('face-status').textContent = `Match Found: ${mName} (${(100 - bestMatch.distance * 100).toFixed(0)}%)`;
         document.getElementById('face-status').style.color = '#22c55e';
         setTimeout(() => {
           if(faceStream){ faceStream.getTracks().forEach(t=>t.stop()); faceStream=null; }
           modal.style.display = 'none';
           document.getElementById('cn').value = mName;
           document.getElementById('cp').value = mPhone;
         }, 1200);
      }
    }, 1500);
  } catch (err) {
    document.getElementById('face-status').textContent = 'Camera access error: ' + err;
    document.getElementById('face-status').style.color = '#ef4444';
    setTimeout(() => { modal.style.display = 'none'; }, 2000);
  }
}
// Clock
const DY=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
function pd(n){return String(n).padStart(2,'0')}
function tk(){const n=new Date();document.getElementById('hd').textContent=pd(n.getDate())+'/'+pd(n.getMonth()+1)+'/'+n.getFullYear();document.getElementById('hw').textContent=DY[n.getDay()];document.getElementById('hc').textContent=pd(n.getHours())+':'+pd(n.getMinutes())+':'+pd(n.getSeconds());}
tk();setInterval(tk,1000);
// Nav
const ROLE_ACCESS={
  owner_technical:['*'],
  super_user:['sales','purchase','item','masters','reorder','system','utilities','sms','settings','users'],
  manager:['sales','purchase','item','masters','reorder','utilities','sms'],
  user:['sales','reorder']
};
let APP_USERS=[],CUR_USER_ID='owner-tech';
function roleCanAccess(panel){
  const u=APP_USERS.find(x=>x.id===CUR_USER_ID)||APP_USERS[0];
  if(!u)return true;
  const allow=ROLE_ACCESS[u.role]||[];
  return allow.includes('*')||allow.includes(panel);
}
function sw(k,el){
  if(!roleCanAccess(k)){alert('Access denied for this role.');return;}
  document.querySelectorAll('.ni').forEach(x=>x.classList.remove('on'));
  if(el)el.classList.add('on');
  else{
    const mn=document.querySelector(`.ni[data-panel="${k}"]`);
    if(mn)mn.classList.add('on');
  }
  document.querySelectorAll('.pn').forEach(x=>x.classList.remove('on'));
  const pn=document.getElementById('p-'+k);
  if(pn)pn.classList.add('on');
}
// Log
function doLogout(){if(confirm('Logout?'))window.close();}
// Tabs (Masters)
function stab(el,id){document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));el.classList.add('on');['mt-cust','mt-sup','mt-doc'].forEach(x=>document.getElementById(x).style.display='none');document.getElementById(id).style.display='block';}
// POS
// POS
let MEDS=[], SHELVES=[], cart={}, pm='cash', AM=[];
let heldBills=JSON.parse(localStorage.getItem('heldBills')||'[]');
let purchaseImportRows=[];
let connectorSites=JSON.parse(localStorage.getItem('connectorSites')||'[{"id":"site-retailio","name":"Retailio","catalog":["Dolo 650mg","Augmentin 625","Pantoprazole 40","Ondansetron 4mg"]}]');
let wantedRows=[];
const BASE_ORIGIN = window.location.protocol.startsWith('http') ? window.location.origin : 'http://127.0.0.1:5001';
const USE_SEPARATE_BACKEND = BASE_ORIGIN.includes(':8000');
const API = USE_SEPARATE_BACKEND ? 'http://127.0.0.1:5001/api' : BASE_ORIGIN + '/api';
const STATIC_BASE = USE_SEPARATE_BACKEND ? 'http://127.0.0.1:5001/static' : BASE_ORIGIN + '/static';

function saveHeldBills(){localStorage.setItem('heldBills',JSON.stringify(heldBills));}
function saveConnectorSites(){localStorage.setItem('connectorSites',JSON.stringify(connectorSites));}

function initUsers(){
  APP_USERS=JSON.parse(localStorage.getItem('appUsers')||'[]');
  if(!APP_USERS.length){
    APP_USERS=[
      {id:'owner-tech',name:'Owner Technical (You)',contact:'owner@local',role:'owner_technical',locked:true},
      {id:'super-demo',name:'Super User',contact:'super@local',role:'super_user'},
      {id:'manager-demo',name:'Manager',contact:'manager@local',role:'manager'},
      {id:'user-demo',name:'Billing User',contact:'user@local',role:'user'}
    ];
    localStorage.setItem('appUsers',JSON.stringify(APP_USERS));
  }
  CUR_USER_ID=localStorage.getItem('currentUserId')||APP_USERS[0].id;
  renderUserSwitch();
  renderUsersPanel();
  applyRoleAccess();
}

function renderUserSwitch(){
  const sel=document.getElementById('user-switch');
  if(!sel)return;
  sel.innerHTML=APP_USERS.map(u=>`<option value="${u.id}">${u.name}</option>`).join('');
  sel.value=CUR_USER_ID;
  const u=APP_USERS.find(x=>x.id===CUR_USER_ID)||APP_USERS[0];
  document.getElementById('role-badge').textContent=(u?.role||'user').replace('_',' ').toUpperCase();
}

function applyRoleAccess(){
  document.querySelectorAll('.ni[data-panel]').forEach(n=>{
    const p=n.getAttribute('data-panel');
    const ok=roleCanAccess(p);
    n.style.opacity=ok?'1':'0.45';
    n.style.pointerEvents=ok?'auto':'none';
    n.title=ok?'':'Locked for role';
  });
  const active=document.querySelector('.pn.on');
  if(active){
    const key=(active.id||'').replace('p-','');
    if(key && !roleCanAccess(key)) sw('sales',document.querySelector('.ni[data-panel="sales"]'));
  }
}

function addAppUser(){
  const n=document.getElementById('u-name').value.trim();
  const c=document.getElementById('u-phone').value.trim();
  const r=document.getElementById('u-role').value;
  if(!n){alert('Enter user name');return;}
  APP_USERS.push({id:'u-'+Date.now(),name:n,contact:c,role:r});
  localStorage.setItem('appUsers',JSON.stringify(APP_USERS));
  document.getElementById('u-name').value='';document.getElementById('u-phone').value='';
  renderUserSwitch();renderUsersPanel();applyRoleAccess();
}

function removeAppUser(id){
  const u=APP_USERS.find(x=>x.id===id);
  if(!u || u.locked){alert('This user is protected.');return;}
  APP_USERS=APP_USERS.filter(x=>x.id!==id);
  if(CUR_USER_ID===id)CUR_USER_ID=APP_USERS[0].id;
  localStorage.setItem('appUsers',JSON.stringify(APP_USERS));
  localStorage.setItem('currentUserId',CUR_USER_ID);
  renderUserSwitch();renderUsersPanel();applyRoleAccess();
}

function renderUsersPanel(){
  const tb=document.getElementById('u-body');
  if(tb){
    tb.innerHTML=APP_USERS.map(u=>`<tr><td>${u.name}</td><td>${u.contact||'—'}</td><td><span class="bx bo">${u.role}</span></td><td style="text-align:right">${u.locked?'<span style="color:var(--dim)">Protected</span>':`<button class="btn btn-r" style="padding:4px 8px" onclick="removeAppUser('${u.id}')">Delete</button>`}</td></tr>`).join('');
  }
  const rb=document.getElementById('role-body');
  if(rb){
    const yn=(k,p)=>((ROLE_ACCESS[k]||[]).includes('*')||(ROLE_ACCESS[k]||[]).includes(p))?'Yes':'No';
    rb.innerHTML=['owner_technical','super_user','manager','user'].map(k=>`<tr><td>${k}</td><td>${yn(k,'sales')}</td><td>${yn(k,'purchase')}</td><td>${yn(k,'item')}</td><td>${yn(k,'masters')}</td><td>${yn(k,'reorder')}</td><td>${yn(k,'utilities')}</td><td>${yn(k,'system')}</td><td>${yn(k,'users')}</td></tr>`).join('');
  }
}

function initBillResizer(){
  const rz=document.getElementById('pos-resizer'), pr=document.getElementById('pos-right');
  if(!rz||!pr)return;
  const saved=parseInt(localStorage.getItem('billWidth')||'310',10);
  const setW=(v)=>{const w=Math.max(260,Math.min(560,v));document.documentElement.style.setProperty('--billw',w+'px');localStorage.setItem('billWidth',String(w));};
  setW(saved);
  let sx=0,sw=0,drag=false;
  rz.addEventListener('mousedown',e=>{drag=true;sx=e.clientX;sw=pr.getBoundingClientRect().width;document.body.style.userSelect='none';});
  window.addEventListener('mousemove',e=>{if(!drag)return;setW(sw-(sx-e.clientX));});
  window.addEventListener('mouseup',()=>{drag=false;document.body.style.userSelect='';});
}

function clearCurrentBillUI(){
  cart={};rct();
  document.getElementById('cn').value='';
  document.getElementById('cp').value='';
  document.getElementById('cdr').value='';
  document.getElementById('dv').value='0';
  document.getElementById('dt').value='pct';
  document.getElementById('bill-type').value='retail';
  document.getElementById('cust-type').value='customer';
  pm='cash';sp('cash');
  rxBase64='';
  const btn=document.getElementById('btn-rx'), prev=document.getElementById('rx-preview');
  if(btn){btn.innerHTML='<i class="fas fa-paperclip"></i> Upload';btn.style.borderColor='var(--brd)';btn.style.color='var(--mt)';}
  if(prev){prev.src='';prev.style.display='none';}
}

function nextBillNo(){return '#B-'+(allBills.length+heldBills.length+1);}
function refreshBillNo(){const el=document.querySelector('.rbn');if(el)el.textContent=nextBillNo();}

function renderHeldBills(){
  const sel=document.getElementById('hold-list');
  if(!sel)return;
  sel.innerHTML='<option value="">Held Bills</option>';
  heldBills.forEach(h=>sel.innerHTML+=`<option value="${h.id}">${h.billNo} · ${h.cust||'Walk-in'} (${(h.items||[]).length})</option>`);
  refreshBillNo();
}

function newBillTab(){
  if(Object.keys(cart).length && !confirm('Current bill has items. Clear and start new bill?'))return;
  clearCurrentBillUI();
  refreshBillNo();
}

function loadHeldBill(){
  const sel=document.getElementById('hold-list');
  if(!sel||!sel.value){alert('Select a held bill first.');return;}
  const i=heldBills.findIndex(x=>x.id===sel.value);
  if(i<0)return;
  const h=heldBills[i];
  heldBills.splice(i,1);
  saveHeldBills();
  cart={};(h.items||[]).forEach(it=>cart[it.id]={...it});
  document.getElementById('cn').value=h.cust||'';
  document.getElementById('cp').value=h.phone||'';
  document.getElementById('cdr').value=h.doctor||'';
  document.getElementById('dv').value=h.discountValue||0;
  document.getElementById('dt').value=h.discountType||'pct';
  document.getElementById('bill-type').value=h.billType||'retail';
  document.getElementById('cust-type').value=h.custType||'customer';
  pm=h.pay||'cash';sp(pm);
  rxBase64=h.prescription||'';
  rct();renderHeldBills();
}

function shelfLabel(m){
  return m.shelf_label || (m.shelf_name ? m.shelf_name : 'Unassigned');
}
function renderShelfSelects(){
  const medSel=document.getElementById('man-shelf');
  const invSel=document.getElementById('shelf-filter');
  const currentMedValue=medSel ? medSel.value : '';
  const currentInvValue=invSel ? invSel.value : '';
  if(medSel){
    medSel.innerHTML='<option value="">Unassigned</option>' + SHELVES.map(s=>`<option value="${s.id}">${s.label}${s.status!=='Active'?' ('+s.status+')':''}</option>`).join('');
    medSel.value=currentMedValue;
  }
  if(invSel){
    invSel.innerHTML='<option value="">All Shelves</option>' + SHELVES.map(s=>`<option value="${s.id}">${s.label}${s.status!=='Active'?' ('+s.status+')':''}</option>`).join('');
    invSel.value=currentInvValue;
  }
  updateShelfPreview();
}
function updateShelfPreview(){
  const medSel=document.getElementById('man-shelf');
  const preview=document.getElementById('man-shelf-label');
  if(!medSel || !preview)return;
  const shelf=SHELVES.find(s=>String(s.id)===String(medSel.value));
  preview.value=shelf?shelf.label:'Unassigned';
  medSel.onchange=updateShelfPreview;
}
function rmed(list){const g=document.getElementById('mg');g.innerHTML='';if(!list.length){g.innerHTML='<div style="color:var(--mt);font-size:12px;padding:16px;grid-column:1/-1">No medicines found.</div>';return;}list.forEach(m=>{const d=document.createElement('div');let scl='';if(m.s<=0)scl=' os';else if(m.s<15)scl=' ls';d.className='mc'+scl;d.tabIndex=0;d.onclick=(e)=>{if(!e.target.closest('.madd')&&!e.target.closest('.mdel')&&!e.target.closest('.mst'))at(m.id);};const db=`<div class="mdel" title="Delete" onclick="dm('${m.id}');event.stopPropagation()"><i class="fas fa-trash"></i></div>`;d.innerHTML='<div class="mn" title="'+m.n+'">'+m.n+'</div><div class="mcat">'+m.g+' · '+m.c+'</div><div style="font-size:10px;color:var(--mt);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+shelfLabel(m)+'</div><div class="mr"><div class="mp">₹'+m.p+'</div><div class="mst" onclick="editMed(\''+m.id+'\');event.stopPropagation()" title="Edit Medicine">'+m.s+' units <i class="fas fa-pen" style="font-size:8.5px;opacity:0.6"></i></div><div style="display:flex;align-items:center;gap:6px;">'+db+'<div class="madd" onclick="at(\''+m.id+'\');event.stopPropagation()"><i class="fas fa-plus"></i></div></div></div>';g.appendChild(d);});}
function rItems(list){const tb=document.getElementById('inv-body');if(!tb)return;tb.innerHTML='';if(!list.length){tb.innerHTML='<tr><td colspan="16" style="text-align:center;color:var(--dim)">No items found.</td></tr>';return;}list.forEach(m=>{const st=m.s<=0?'<span class="bx br">Out</span>':(m.s<15?'<span class="bx br" style="background:#f59e0b">Low</span>':'<span class="bx bg">OK</span>');tb.innerHTML+=`<tr><td style="position:sticky;left:0;background:var(--card);border-right:1px solid var(--brd);font-weight:600">${m.n}</td><td>${shelfLabel(m)}</td><td>${m.batch||'—'}</td><td>${m.expiry||'—'}</td><td>₹${m.p_rate}</td><td>${m.p_packing||'—'}</td><td>₹${m.p}</td><td>${m.s_packing||'—'}</td><td>${m.s}</td><td>${m.p_gst}%</td><td>${m.s_gst}%</td><td>${m.disc}%</td><td>${m.offer||'None'}</td><td>${m.reorder}</td><td>${m.max_qty}</td><td style="text-align:right"><button class="btn btn-out" style="padding:4px 8px" onclick="editMed('${m.id}')"><i class="fas fa-pen"></i></button></td></tr>`;});}
function rPurchases(){fetch(API+'/purchases?t='+Date.now()).then(r=>r.json()).then(ps=>{const tb=document.getElementById('pur-body');if(!tb)return;if(!ps.length){tb.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--dim)">No purchase orders recorded.</td></tr>';return;}tb.innerHTML='';ps.sort((a,b)=>b.id.localeCompare(a.id)).forEach(p=>{const st=p.status==='Received'?'bg':(p.status==='Cancelled'?'br':'bo');const prf=p.photo?`<i class="fas fa-camera-retro" style="margin-left:6px;opacity:0.6;cursor:pointer" onclick="v_sh('${p.id}')"></i>`:'';tb.innerHTML+=`<tr><td><span class="bx bo">#${p.id}</span></td><td>${p.supplier}</td><td>${p.items}</td><td>₹${p.amount}</td><td>${p.date}</td><td><span class="bx ${st}" onclick="upSt('${p.id}')" style="cursor:pointer">${p.status}</span>${prf}</td></tr>`;});});}
function v_sh(id){fetch(API+'/purchases').then(r=>r.json()).then(ps=>{const p=ps.find(x=>x.id==id);if(!p||!p.photo)return;const w=window.open('','_blank','width=450,height=550');w.document.write(`<html><body style="background:#0f172a;color:#fff;font-family:sans-serif;padding:20px;text-align:center;"><h3>Order Verification Proof</h3><img src="${p.photo}" style="width:100%;border-radius:8px;border:1px solid #334155"/><div style="text-align:left;margin-top:15px;font-size:13px;"><p><b>ID:</b> #${p.id}</p><p><b>Supplier:</b> ${p.supplier}</p><p><b>Batch:</b> ${p.batch}</p><p><b>Expiry:</b> ${p.expiry}</p></div></body></html>`);});}
function upSt(id){fetch(API+'/purchases').then(r=>r.json()).then(ps=>{const p=ps.find(x=>x.id==id);if(!p)return;const next={'Pending':'Received','Received':'Cancelled','Cancelled':'Pending'}[p.status]||'Pending';if(next==='Received'){v_open(p);return;}p.status=next;fetch(API+'/purchases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}).then(()=>rPurchases());});}

let V_P=null, V_S=null;
function v_open(p){V_P=p;document.getElementById('v-mod').style.display='flex';v_cam();}
function v_close(){if(V_S){V_S.getTracks().forEach(t=>t.stop());V_S=null;}document.getElementById('v-mod').style.display='none';}
async function v_cam(){const v=document.getElementById('v-vid'),c=document.getElementById('v-can');v.style.display='block';c.style.display='none';try{const s=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});V_S=s;v.srcObject=s;}catch(err){alert('Camera access denied');}}
function v_cap(){const v=document.getElementById('v-vid'),c=document.getElementById('v-can'),ctx=c.getContext('2d');const w=v.videoWidth,h=v.videoHeight;c.width=Math.min(400,w);c.height=c.width*(h/w);ctx.drawImage(v,0,0,c.width,c.height);v.style.display='none';c.style.display='block';document.getElementById('v-msg').textContent='Captured!';if(V_S){V_S.getTracks().forEach(t=>t.stop());V_S=null;}}
function v_sv(){const b=document.getElementById('v-b').value.trim(),e=document.getElementById('v-e').value,c=document.getElementById('v-can');if(!b||!e){alert('Batch and Expiry are mandatory!');return;}if(c.style.display!=='block'){alert('Please capture a photo first!');return;}const btn=document.querySelector('#v-mod .btn-acc[onclick="v_sv()"]');const ot=btn.textContent;btn.disabled=true;btn.textContent='Saving...';const ph=c.toDataURL('image/jpeg',0.4);const p={...V_P,status:'Received',batch:b,expiry:e,photo:ph};fetch(API+'/purchases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}).then(r=>r.json()).then(()=>{rPurchases();v_close();alert('Verified and Received!');}).catch(err=>alert('Error: '+err.message)).finally(()=>{btn.disabled=false;btn.textContent=ot;});}
function loadInventory(){fetch(API+'/medicines?t='+Date.now()).then(r=>{if(!r.ok)throw new Error('API Error');return r.json();}).then(data=>{MEDS=data;fm2();rItems(MEDS);rSys();rCategories(data);}).catch(err=>{console.error(err);});}
function rCategories(ms){const cs=['All Categories',...new Set(ms.map(m=>m.c))];const sel=document.getElementById('cat-filter');if(sel){const curr=sel.value;sel.innerHTML=cs.map(c=>`<option value="${c==='All Categories'?'':c}" ${c===curr?'selected':''}>${c}</option>`).join('');}}

let filteredMeds=[];
function fm2(){
    const q=document.getElementById('ms').value.toLowerCase();
    const c=document.getElementById('cat-filter').value;
    filteredMeds=MEDS.filter(m=>{
        const matchCat = !c || m.c === c;
        const matchText = m.n.toLowerCase().includes(q) || 
                          m.g.toLowerCase().includes(q) || 
                          (m.batch && m.batch.toLowerCase().includes(q)) ||
                          (m.shelf_name && m.shelf_name.toLowerCase().includes(q)) ||
                          (m.shelf_label && m.shelf_label.toLowerCase().includes(q));
        return matchCat && matchText;
    });
    rmed(filteredMeds);
}

// Global Keyboard Shortcuts & Barcode Logic
let barcodeBuffer = '';
let barcodeTimeout = null;
window.addEventListener('keydown', e=>{
    if (e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
        barcodeBuffer += e.key;
        if (barcodeTimeout) clearTimeout(barcodeTimeout);
        barcodeTimeout = setTimeout(() => { barcodeBuffer = ''; }, 50);
    } else if (e.key === 'Enter') {
        if (barcodeBuffer.length >= 3) {
            e.preventDefault();
            const match = MEDS.find(m => (m.batch || '').toLowerCase() === barcodeBuffer.toLowerCase() || m.id.toString() === barcodeBuffer);
            if (match) {
                at(match.id);
                const act = document.activeElement;
                if(act && act.tagName === 'INPUT') act.value = act.value.replace(barcodeBuffer, '');
            }
            barcodeBuffer = '';
            return;
        }
        barcodeBuffer = '';
    }

    if(e.key==='F2'){ e.preventDefault(); const modes=['cash','upi','card']; sp(modes[(modes.indexOf(pm)+1)%3]); }
    if(e.key==='F3'){ e.preventDefault(); document.getElementById('ms').focus(); }
    if(e.key==='F4'){ e.preventDefault(); triggerFaceScan(); }
    if(e.key==='F8' || e.key==='F12'){ e.preventDefault(); pb2(); }
    if(e.key==='F9'){ e.preventDefault(); hb(); }
});

function hb(){
  const ks=Object.keys(cart);
  if(!ks.length){alert('Cart empty.');return;}
  const holdObj={
    id:'H-'+Date.now(),
    billNo:nextBillNo(),
    ts:Date.now(),
    cust:document.getElementById('cn').value.trim(),
    phone:document.getElementById('cp').value.trim(),
    doctor:document.getElementById('cdr').value.trim(),
    discountValue:parseFloat(document.getElementById('dv').value)||0,
    discountType:document.getElementById('dt').value,
    billType:document.getElementById('bill-type').value,
    custType:document.getElementById('cust-type').value,
    pay:pm,
    prescription:rxBase64,
    items:ks.map(k=>({...cart[k]}))
  };
  heldBills.unshift(holdObj);
  if(heldBills.length>30)heldBills=heldBills.slice(0,30);
  saveHeldBills();
  clearCurrentBillUI();
  renderHeldBills();
  alert('Bill held. New bill created.');
}

// Global 2D Spatial Arrow Navigation Engine
window.addEventListener('keydown', e => {
    const K = ['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'];
    if(!K.includes(e.key) && e.key !== 'Enter') return;
    
    const ae = document.activeElement;
    if(e.key === 'Enter') {
        if(ae && (ae.classList.contains('mc') || ae.classList.contains('ni'))) { e.preventDefault(); ae.click(); }
        else if (ae && ae.id === 'ms' && filteredMeds.length > 0) { e.preventDefault(); at(filteredMeds[0].id); ae.value=''; if(typeof fm2 === 'function') fm2(); }
        return;
    }
    
    if(ae && (ae.tagName==='INPUT' || ae.tagName==='TEXTAREA')) {
        if(ae.type !== 'number') {
            try {
                if(e.key==='ArrowLeft' && typeof ae.selectionStart === 'number' && ae.selectionStart > 0) return;
                if(e.key==='ArrowRight' && typeof ae.selectionEnd === 'number' && ae.selectionEnd < ae.value.length) return;
            } catch(err) {} 
        }
    }
    if(ae && ae.tagName==='SELECT') {
        if(e.key==='ArrowUp' || e.key==='ArrowDown') return; // let native handle select drop-down choices
        // ArrowLeft and ArrowRight can organically jump to other UI sections
    }
    
    e.preventDefault();
    
    const nodes = Array.from(document.querySelectorAll('input:not([type="hidden"]), button, select, .mc, .ni, [tabindex="0"]'))
        .filter(n => n.offsetParent !== null && n.style.display !== 'none' && !n.disabled);
    
    if(nodes.length === 0) return;
    if(!nodes.includes(ae)) { nodes[0].focus(); return; }
    
    const rA = ae.getBoundingClientRect();
    const cx = rA.left + rA.width/2, cy = rA.top + rA.height/2;
    
    let best = null, minScore = Infinity;
    
    nodes.forEach(n => {
        if(n === ae) return;
        const rB = n.getBoundingClientRect();
        const overlapX = Math.max(0, Math.min(rA.right, rB.right) - Math.max(rA.left, rB.left));
        const overlapY = Math.max(0, Math.min(rA.bottom, rB.bottom) - Math.max(rA.top, rB.top));
        
        const cB = { x: rB.left + rB.width/2, y: rB.top + rB.height/2 };
        let dx = cB.x - cx, dy = cB.y - cy;
        let dist = Math.sqrt(dx*dx + dy*dy);
        
        let valid = false, score = Infinity;
        if(e.key==='ArrowUp' && dy < -5) { 
            valid = true; 
            score = Math.abs(dy) + Math.abs(dx) * (overlapX > 20 ? 0.1 : 10); 
        }
        if(e.key==='ArrowDown' && dy > 5) { 
            valid = true; 
            score = Math.abs(dy) + Math.abs(dx) * (overlapX > 20 ? 0.1 : 10); 
        }
        if(e.key==='ArrowLeft' && dx < -5) { 
            valid = true; 
            score = Math.abs(dx) + Math.abs(dy) * (overlapY > 20 ? 0.1 : 10); 
        }
        if(e.key==='ArrowRight' && dx > 5) { 
            valid = true; 
            score = Math.abs(dx) + Math.abs(dy) * (overlapY > 20 ? 0.1 : 10); 
        }
        
        if(valid && score < minScore) { minScore = score; best = n; }
    });
    
    if(best) best.focus();
});

function fi(q){
  const lq=(q||'').toLowerCase();
  const shelfFilter=document.getElementById('shelf-filter')?.value || '';
  const list=MEDS.filter(m=>{
    const shelfMatch = !shelfFilter || String(m.shelf_id||'') === String(shelfFilter);
    const text = [
      m.n, m.g, m.c, m.batch, m.expiry, m.offer, m.shelf_name, m.shelf_label, m.shelf_aisle, m.shelf_rack, m.shelf_slot, m.shelf_bin
    ].filter(Boolean).join(' ').toLowerCase();
    return shelfMatch && text.includes(lq);
  });
  rItems(list);
}
// fm2() handles both now

function at(id){const i=MEDS.find(x=>x.id==id);if(!i)return;if(i.s<=0){alert('Out of stock!');return;}if(cart[id]&&(cart[id].qty>=i.s)){alert('Cannot exceed available stock!');return;}if(cart[id])cart[id].qty++;else cart[id]={...i,qty:1};rct();}
function rct(){const ca=document.getElementById('ca'),ec=document.getElementById('ec'),bs2=document.getElementById('bs2'),ks=Object.keys(cart);ca.querySelectorAll('.ci2').forEach(x=>x.remove());if(!ks.length){ec.style.display='flex';bs2.style.display='none';return;}ec.style.display='none';ks.forEach(k=>{const i=cart[k];const d=document.createElement('div');d.className='ci2';d.innerHTML='<div class="cn2"><div class="nm">'+i.n+'</div><div class="pr">₹'+i.p+' × '+i.qty+'</div></div><div class="qc"><button class="qb" onclick="cq(\''+k+'\',-1)"><i class="fas fa-minus"></i></button><input type="number" class="qv-in" value="'+i.qty+'" onchange="sq(\''+k+'\',this.value)"/><button class="qb" onclick="cq(\''+k+'\',1)"><i class="fas fa-plus"></i></button></div><span class="ct2">₹'+(i.p*i.qty).toFixed(2)+'</span><span class="cd" onclick="ri(\''+k+'\')"><i class="fas fa-xmark"></i></span>';ca.appendChild(d);});bs2.style.display='block';rc();}
function cq(id,d){if(!cart[id])return;cart[id].qty+=d;if(cart[id].qty<=0)delete cart[id];rct();}
function sq(id,v){
  const i=MEDS.find(x=>x.id==id);
  let q=parseInt(v);
  if(isNaN(q)||q<=0){delete cart[id];}
  else{
    if(q > i.s){alert('Cannot exceed available stock!');q=i.s;}
    cart[id].qty=q;
  }
  rct();
}
function ri(id){delete cart[id];rct();}
function rc(){
  const ks=Object.keys(cart);
  const sub=ks.reduce((s,k)=>s+cart[k].p*cart[k].qty,0);
  const dv=parseFloat(document.getElementById('dv').value)||0;
  const dt=document.getElementById('dt').value;
  const billTypeEl=document.getElementById('bill-type');
  const billType=billTypeEl?billTypeEl.value:'retail';
  const modeDiscount=billType==='wholesale'?sub*0.08:0;
  const da=dt==='pct'?sub*(dv/100):Math.min(dv,sub);
  const taxable=Math.max(sub-modeDiscount-da,0);
  const tax=taxable*0.05;
  const tot=taxable+tax;
  document.getElementById('sv').textContent='₹'+sub.toFixed(2);
  document.getElementById('tv').textContent='₹'+tax.toFixed(2);
  document.getElementById('ttv').textContent='₹'+tot.toFixed(2);
}
function sp(m){pm=m;['cash','upi','card'].forEach(x=>document.getElementById('pm-'+x).classList.remove('sel'));document.getElementById('pm-'+m).classList.add('sel');}
function sm(){
  document.getElementById('man-mod').style.display='flex';
  document.getElementById('man-title').textContent='Add New Medicine';
  document.getElementById('man-id').value='';
  ['n','g','batch','exp','ppack','spack','offer'].forEach(k=>document.getElementById('man-'+k).value='');
  ['s','prate','p','pgst','sgst','disc','reorder','max'].forEach(k=>document.getElementById('man-'+k).value=0);
  document.getElementById('man-shelf').value='';
  document.getElementById('man-shelf-label').value='Unassigned';
  document.getElementById('man-n').focus();
}
function editMed(id){
  const m=MEDS.find(x=>x.id==id);
  if(!m)return;
  document.getElementById('man-mod').style.display='flex';
  document.getElementById('man-title').textContent='Edit Medicine: '+m.n;
  document.getElementById('man-id').value=m.id;
  document.getElementById('man-n').value=m.n;
  document.getElementById('man-g').value=m.g;
  document.getElementById('man-c').value=m.c;
  document.getElementById('man-batch').value=m.batch;
  document.getElementById('man-exp').value=m.expiry;
  document.getElementById('man-s').value=m.s;
  document.getElementById('man-prate').value=m.p_rate;
  document.getElementById('man-p').value=m.p;
  document.getElementById('man-ppack').value=m.p_packing;
  document.getElementById('man-spack').value=m.s_packing;
  document.getElementById('man-pgst').value=m.p_gst;
  document.getElementById('man-sgst').value=m.s_gst;
  document.getElementById('man-disc').value=m.disc;
  document.getElementById('man-offer').value=m.offer;
  document.getElementById('man-reorder').value=m.reorder;
  document.getElementById('man-max').value=m.max_qty;
  document.getElementById('man-shelf').value=m.shelf_id||'';
  document.getElementById('man-shelf-label').value=shelfLabel(m);
  document.getElementById('man-n').focus();
}
function am_sv(){
  const n=document.getElementById('man-n').value.trim();
  if(!n){alert('Enter item name');return;}
  const btn=document.querySelector('#man-mod .btn-acc');
  const ot=btn.textContent;
  btn.disabled=true;
  btn.textContent='Saving...';
  const id=document.getElementById('man-id').value||'m_'+Date.now();
  const itemData={
    id:id,n:n,g:document.getElementById('man-g').value,c:document.getElementById('man-c').value,
    p:parseFloat(document.getElementById('man-p').value)||0,
    s:parseInt(document.getElementById('man-s').value)||0,
    batch:document.getElementById('man-batch').value,
    expiry:document.getElementById('man-exp').value,
    p_rate:parseFloat(document.getElementById('man-prate').value)||0,
    p_packing:document.getElementById('man-ppack').value,
    s_packing:document.getElementById('man-spack').value,
    p_gst:parseFloat(document.getElementById('man-pgst').value)||0,
    s_gst:parseFloat(document.getElementById('man-sgst').value)||0,
    disc:parseFloat(document.getElementById('man-disc').value)||0,
    offer:document.getElementById('man-offer').value,
    reorder:parseInt(document.getElementById('man-reorder').value)||0,
    max_qty:parseInt(document.getElementById('man-max').value)||0,
    shelf_id:document.getElementById('man-shelf').value||''
  };
  fetch(API+'/medicines',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(itemData)
  })
  .then(r=>{if(!r.ok)return r.json().then(e=>{throw e});return r.json();})
  .then(()=>{
    loadInventory();
    document.getElementById('man-mod').style.display='none';
    alert('Medicine details saved successfully!');
  })
  .catch(err=>alert('Save Failed: '+(err.message||'Server error')))
  .finally(()=>{btn.disabled=false;btn.textContent=ot;});
}
function initNav(){
  const ids=['man-n','man-g','man-c','man-batch','man-shelf','man-exp','man-s','man-prate','man-p','man-ppack','man-spack','man-pgst','man-sgst','man-disc','man-offer','man-reorder','man-max'];
  ids.forEach((id,idx)=>{
    const el=document.getElementById(id);
    if(el)el.onkeydown=(e)=>{
      if(e.key==='Enter'){
        e.preventDefault();
        const nxt=document.getElementById(ids[idx+1]);
        if(nxt)nxt.focus();
        else am_sv();
      }
    };
  });
}
initNav();

function rMasters(){rCustomers();rSuppliers();rDoctors();loadShelves();}
let CUSTOMERS=[];
function rCustomers(){fetch(API+'/customers?t='+Date.now()).then(r=>r.json()).then(cs=>{CUSTOMERS=cs;const tb=document.getElementById('cust-body');const nL=document.getElementById('cust-list');const pL=document.getElementById('phone-list');if(nL&&pL){nL.innerHTML='';pL.innerHTML='';cs.forEach(x=>{nL.innerHTML+=`<option value="${x.name}">${x.phone}</option>`;pL.innerHTML+=`<option value="${x.phone}">${x.name}</option>`;});}if(!tb)return;tb.innerHTML='';if(!cs.length){tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:var(--dim)">No customer records.</td></tr>';return;}cs.forEach(c=>tb.innerHTML+=`<tr><td>${c.name}</td><td>${c.phone}</td><td style="text-align:center">${c.visits}</td><td style="font-weight:600">₹${c.total_spend.toFixed(2)}</td><td style="text-align:right"><i class="fas fa-edit" style="cursor:pointer;color:var(--acc);margin-right:10px" onclick="ecust(${c.id})"></i><i class="fas fa-trash" style="cursor:pointer;color:#e74c3c" onclick="dcust(${c.id})"></i></td></tr>`)});}
function rSuppliers(){fetch(API+'/suppliers?t='+Date.now()).then(r=>r.json()).then(ss=>{SUPPLIERS=ss;const tb=document.getElementById('sup-body');if(!tb)return;tb.innerHTML='';if(!ss.length){tb.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--dim)">No supplier records.</td></tr>';return;}ss.forEach(s=>tb.innerHTML+=`<tr><td>${s.name}</td><td>${s.phone}</td><td>${s.gst||'—'}</td><td><span class="bx bg">${s.status}</span></td><td style="text-align:right"><i class="fas fa-edit" style="cursor:pointer;color:var(--acc);margin-right:10px" onclick="esup(${s.id})"></i><i class="fas fa-trash" style="cursor:pointer;color:#e74c3c" onclick="dm_sup('${s.id}')"></i></td></tr>`)});}
let DOCTORS=[];
function rDoctors(){fetch(API+'/doctors?t='+Date.now()).then(r=>r.json()).then(ds=>{DOCTORS=ds;const tb=document.getElementById('doc-body');if(!tb)return;tb.innerHTML='';if(!ds.length){tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:var(--dim)">No doctor records.</td></tr>';return;}ds.forEach(d=>tb.innerHTML+=`<tr><td>${d.name}</td><td>${d.specialty}</td><td>${d.hospital}</td><td>${d.phone}</td><td style="text-align:right"><i class="fas fa-edit" style="cursor:pointer;color:var(--acc);margin-right:10px" onclick="edoc(${d.id})"></i><i class="fas fa-trash" style="cursor:pointer;color:#e74c3c" onclick="ddoc(${d.id})"></i></td></tr>`)}); }

function loadShelves(){
  fetch(API+'/shelves?t='+Date.now()).then(r=>r.json()).then(rows=>{
    SHELVES=rows||[];
    renderShelfSelects();
    const tb=document.getElementById('shelf-body');
    if(!tb)return;
    tb.innerHTML='';
    if(!SHELVES.length){
      tb.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--dim)">No shelf locations.</td></tr>';
      return;
    }
    tb.innerHTML=SHELVES.map(s=>`<tr><td>${s.name}</td><td style="font-size:11px;color:var(--mt)">${[s.aisle&&`Aisle ${s.aisle}`,s.rack&&`Rack ${s.rack}`,s.shelf&&`Shelf ${s.shelf}`,s.bin&&`Bin ${s.bin}`].filter(Boolean).join(' / ')||'—'}</td><td>${s.notes||'—'}</td><td><span class="bx ${s.status==='Active'?'bg':'bo'}">${s.status}</span></td><td>${s.medicine_count||0}</td><td style="text-align:right"><i class="fas fa-edit" style="cursor:pointer;color:var(--acc);margin-right:10px" onclick="eshelf(${s.id})"></i><i class="fas fa-trash" style="cursor:pointer;color:#e74c3c" onclick="dshelf(${s.id})"></i></td></tr>`).join('');
  });
}
function ashelf(){
  document.getElementById('shelf-mod').style.display='flex';
  document.getElementById('shelf-title').textContent='Add Shelf Location';
  document.getElementById('shelf-id').value='';
  ['name','aisle','rack','slot','bin','notes'].forEach(k=>document.getElementById('shelf-'+k).value='');
  document.getElementById('shelf-status').value='Active';
  document.getElementById('shelf-name').focus();
}
function eshelf(id){
  const s=SHELVES.find(x=>x.id==id);
  if(!s)return;
  document.getElementById('shelf-mod').style.display='flex';
  document.getElementById('shelf-title').textContent='Edit Shelf Location';
  document.getElementById('shelf-id').value=s.id;
  document.getElementById('shelf-name').value=s.name||'';
  document.getElementById('shelf-aisle').value=s.aisle||'';
  document.getElementById('shelf-rack').value=s.rack||'';
  document.getElementById('shelf-slot').value=s.shelf||'';
  document.getElementById('shelf-bin').value=s.bin||'';
  document.getElementById('shelf-notes').value=s.notes||'';
  document.getElementById('shelf-status').value=s.status||'Active';
  document.getElementById('shelf-name').focus();
}
function saveShelf(){
  const name=document.getElementById('shelf-name').value.trim();
  if(!name){alert('Enter shelf name');return;}
  const payload={
    id:document.getElementById('shelf-id').value||null,
    name,
    aisle:document.getElementById('shelf-aisle').value.trim(),
    rack:document.getElementById('shelf-rack').value.trim(),
    shelf:document.getElementById('shelf-slot').value.trim(),
    bin:document.getElementById('shelf-bin').value.trim(),
    notes:document.getElementById('shelf-notes').value.trim(),
    status:document.getElementById('shelf-status').value
  };
  fetch(API+'/shelves',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)
  }).then(r=>{if(!r.ok)return r.json().then(e=>{throw e});return r.json();}).then(()=>{
    document.getElementById('shelf-mod').style.display='none';
    loadShelves();
    loadInventory();
  }).catch(err=>alert('Save Failed: '+(err.message||'Server error')));
}
function dshelf(id){
  if(!confirm('Delete this shelf location? Medicines assigned to it will become unassigned.'))return;
  fetch(API+'/shelves/'+id,{method:'DELETE'}).then(r=>{if(!r.ok)return r.json().then(e=>{throw e});return r.json();}).then(()=>{
    loadShelves();
    loadInventory();
  }).catch(err=>alert('Delete Failed: '+(err.message||'Server error')));
}

function acust(){document.getElementById('cust-mod').style.display='flex';document.getElementById('cust-title').textContent='Add Customer';document.getElementById('c-id').value='';document.getElementById('c-n').value='';document.getElementById('c-p').value='';document.getElementById('c-a').value='';document.getElementById('c-e').value='';document.getElementById('c-face').value='';document.getElementById('c-btn-scan').innerHTML='<i class="fas fa-camera"></i> Enroll Face Vector';document.getElementById('c-btn-scan').style.borderColor='';document.getElementById('c-btn-scan').style.color='';document.getElementById('c-n').focus();}
function ecust(id){const c=CUSTOMERS.find(x=>x.id==id);if(!c)return;document.getElementById('cust-mod').style.display='flex';document.getElementById('cust-title').textContent='Edit Customer';document.getElementById('c-id').value=c.id;document.getElementById('c-n').value=c.name;document.getElementById('c-p').value=c.phone;document.getElementById('c-a').value=c.address||'';document.getElementById('c-e').value=c.email||'';document.getElementById('c-face').value=c.face_vector||'';document.getElementById('c-btn-scan').innerHTML=c.face_vector?'<i class="fas fa-check"></i> ML Vector Enrolled!':'<i class="fas fa-camera"></i> Enroll Face Vector';document.getElementById('c-btn-scan').style.borderColor=c.face_vector?'#22c55e':'';document.getElementById('c-btn-scan').style.color=c.face_vector?'#22c55e':'';document.getElementById('c-n').focus();}

let enrollStream = null;
async function enrollFace(e) {
  e.preventDefault();
  if(!window.faceapi){ alert('AI Models are loading, give it a moment.'); return; }
  const vid = document.getElementById('c-vid'), btn = document.getElementById('c-btn-scan');
  if(!enrollStream) {
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Initializing Camera...';
    try {
      enrollStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user'}});
      vid.srcObject = enrollStream;
      vid.style.display = 'block';
      btn.innerHTML = '<i class="fas fa-camera"></i> Capture & Extract Vector';
    } catch(err) { alert('Camera err: '+err); btn.innerHTML = 'Enroll Face Vector'; }
  } else {
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing 128D Math...';
    try {
      const det = await faceapi.detectSingleFace(vid, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor();
      if(!det) { alert('No face detected! Look directly at the camera.'); btn.innerHTML = '<i class="fas fa-camera"></i> Try Again'; return; }
      document.getElementById('c-face').value = JSON.stringify(Array.from(det.descriptor));
      btn.innerHTML = '<i class="fas fa-check" style="color:#22c55e"></i> Face Enrolled Successfully!';
      btn.style.borderColor = '#22c55e'; btn.style.color = '#22c55e';
    } catch(err){ alert('Error: '+err); }
    enrollStream.getTracks().forEach(t=>t.stop()); enrollStream = null;
    setTimeout(()=>vid.style.display='none', 800);
  }
}

function sv_cust(){const id=document.getElementById('c-id').value,n=document.getElementById('c-n').value.trim(),p=document.getElementById('c-p').value.trim(),a=document.getElementById('c-a').value.trim(),e=document.getElementById('c-e').value.trim(),f=document.getElementById('c-face').value;if(!n){alert('Enter Customer Name');return;}const d=id?CUSTOMERS.find(x=>x.id==id):{};fetch(API+'/customers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id||null,name:n,phone:p,address:a,email:e,visits:d.visits||1,total:d.total_spend||0,face_vector:f})}).then(()=>{rMasters();document.getElementById('cust-mod').style.display='none';});}
function dcust(id){if(!confirm('Delete this customer?'))return;fetch(API+'/customers/'+id,{method:'DELETE'}).then(()=>rMasters());}

function asup(){document.getElementById('sup-mod').style.display='flex';document.getElementById('sup-title').textContent='Add Supplier';document.getElementById('s-id').value='';document.getElementById('s-n').value='';document.getElementById('s-p').value='';document.getElementById('s-g').value='';document.getElementById('s-st').value='Active';document.getElementById('s-n').focus();}
function esup(id){const s=SUPPLIERS.find(x=>x.id==id);if(!s)return;document.getElementById('sup-mod').style.display='flex';document.getElementById('sup-title').textContent='Edit Supplier';document.getElementById('s-id').value=s.id;document.getElementById('s-n').value=s.name;document.getElementById('s-p').value=s.phone;document.getElementById('s-g').value=s.gst||'';document.getElementById('s-st').value=s.status||'Active';document.getElementById('s-n').focus();}
function sv_sup(){const id=document.getElementById('s-id').value,n=document.getElementById('s-n').value.trim(),p=document.getElementById('s-p').value.trim(),g=document.getElementById('s-g').value.trim(),st=document.getElementById('s-st').value;if(!n){alert('Enter Supplier Name');return;}const d=id?SUPPLIERS.find(x=>x.id==id):{};fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id||null,name:n,phone:p,gst:g,status:st,last_order:d.last_order||'—'})}).then(()=>{rMasters();document.getElementById('sup-mod').style.display='none';});}

function adoc(){document.getElementById('doc-mod').style.display='flex';document.getElementById('doc-title').textContent='Add Doctor';document.getElementById('d-id').value='';document.getElementById('d-n').value='';document.getElementById('d-s').value='';document.getElementById('d-h').value='';document.getElementById('d-p').value='';document.getElementById('d-n').focus();}
function edoc(id){const d=DOCTORS.find(x=>x.id==id);if(!d)return;document.getElementById('doc-mod').style.display='flex';document.getElementById('doc-title').textContent='Edit Doctor';document.getElementById('d-id').value=d.id;document.getElementById('d-n').value=d.name;document.getElementById('d-s').value=d.specialty;document.getElementById('d-h').value=d.hospital;document.getElementById('d-p').value=d.phone;document.getElementById('d-n').focus();}
function sv_doc(){const id=document.getElementById('d-id').value,n=document.getElementById('d-n').value.trim(),s=document.getElementById('d-s').value.trim(),h=document.getElementById('d-h').value.trim(),p=document.getElementById('d-p').value.trim();if(!n){alert('Enter Doctor Name');return;}fetch(API+'/doctors',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id||null,name:n,specialty:s,hospital:h,phone:p})}).then(()=>{rMasters();document.getElementById('doc-mod').style.display='none';});}
function ddoc(id){if(!confirm('Delete this doctor?'))return;fetch(API+'/doctors/'+id,{method:'DELETE'}).then(()=>rMasters());}

function dm_sup(id){if(!confirm('Delete this supplier?'))return;fetch(API+'/suppliers/'+id,{method:'DELETE'}).then(()=>rMasters());}
function dm(id){if(!confirm('Permanently delete this medicine?'))return;fetch(API+'/medicines/'+id,{method:'DELETE'}).then(()=>{loadInventory();if(cart[id]){delete cart[id];rct();}});}
function us(id){const i=MEDS.find(x=>x.id==id);if(!i)return;let nv=prompt(`Update stock for ${i.n}:`,i.s);if(nv!==null){nv=parseInt(nv);if(!isNaN(nv)){fetch(API+'/medicines',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...i,s:nv})}).then(()=>loadInventory());}}}

let allBills=[];
function renderUtils(){const tbody=document.getElementById('util-bills-body');if(!tbody)return;if(!allBills.length){tbody.innerHTML='<tr><td colspan="8" style="text-align:center;color:var(--dim)">No bills generated yet.</td></tr>';return;}tbody.innerHTML='';allBills.slice().reverse().forEach((b)=>{const itemsTxt=(b.items&&b.items.length)?b.items.map(i=>i.n).join(', '):'—';const rxf=b.prescription?`<button class="btn btn-out" style="padding:4px 10px;font-size:10px;border-color:var(--acc);color:var(--acc);background:rgba(245,166,35,0.05)" onclick="v_rx('${b.id}')"><i class="fas fa-eye"></i> View Prescription</button>`:'<span style="color:var(--dim);font-size:11px;opacity:0.5">—</span>';tbody.innerHTML+=`<tr>
<td style="vertical-align:middle"><span class="bx bo">#${b.id}</span></td>
<td style="vertical-align:middle;font-size:12px">${b.date}</td>
<td style="vertical-align:middle;font-weight:500">${b.cust}</td>
<td style="vertical-align:middle;text-align:center">${rxf}</td>
<td style="vertical-align:middle;font-weight:600;color:var(--acc)">₹${b.total.toFixed(2)}</td>
<td style="vertical-align:middle"><span style="text-transform:uppercase;font-size:10px;background:var(--brd);padding:2px 6px;border-radius:4px">${b.pay}</span></td>
<td style="vertical-align:middle;color:var(--mt);font-size:11.5px">${b.doctor||'Self'}</td>
<td style="vertical-align:middle;color:var(--mt);font-size:11.5px;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${itemsTxt}">${itemsTxt}</td>
</tr>`;});}
function v_rx(id){const b=allBills.find(x=>x.id==id);if(!b||!b.prescription)return;const isPdf=b.prescription.startsWith('data:application/pdf');const w=window.open('','_blank','width=1000,height=920');const content=isPdf?`<iframe src="${b.prescription}" style="width:95%;height:82vh;border-radius:12px;border:1px solid #334155;background:#1e293b;box-shadow:0 20px 50px rgba(0,0,0,0.5)"></iframe>`:`<video style="display:none"></video><img src="${b.prescription}" style="max-width:90%;max-height:80%;border-radius:12px;box-shadow:0 20px 50px rgba(0,0,0,0.5);border:1px solid #334155;"/><p style="margin-top:24px;font-size:14px;color:#94a3b8;letter-spacing:0.5px">Customer: <b style="color:#f1f5f9">${b.cust}</b></p>`;w.document.write(`<html><head><title>Prescription: ${b.cust}</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet"/><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"/><style>body{margin:0;background:#0f172a;color:#fff;font-family:'Inter',sans-serif;display:flex;flex-direction:column;align-items:center;height:100vh;overflow:hidden}.hdr{width:100%;padding:20px;background:#1e293b;border-bottom:1px solid #334155;display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:30px}.hdr i{color:#f5a623;font-size:20px}.hdr h2{margin:0;font-size:18px;font-weight:600;letter-spacing:-0.5px}</style></head><body><div class="hdr"><i class="fas fa-file-prescription"></i><h2>Prescription for Bill #${b.id}</h2></div>${content}</body></html>`);}
function rKpis(sD){
  fetch(API+'/bills?t='+Date.now()).then(r=>r.json()).then(bls=>{
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
    document.querySelector('.rbn').textContent='#B-'+(bls.length+heldBills.length+1);
    renderUtils();
    rMasters();
    rSys(sD);
    if(typeof generateWantedList==='function')generateWantedList();
    if(!sD){
      const todayIso = d.toISOString().split('T')[0];
      document.getElementById('sys-date').value = todayIso;
      document.getElementById('sys-date').max = todayIso;
    }
  });
}
function rSys(sD){
  if(!MEDS.length)return;
  const d=sD?new Date(sD):new Date();
  const ls=MEDS.filter(m=>m.s<15).slice(0,5);
  const ex=MEDS.filter(m=>m.expiry && new Date(m.expiry)<new Date(d.getTime()+90*24*60*60*1000)).slice(0,5);
  document.getElementById('kpi-al').textContent=ls.length+ex.length;
  const g_low=document.getElementById('sys-low'), g_exp=document.getElementById('sys-exp');
  g_low.innerHTML='';g_exp.innerHTML='';
  if(!ls.length)g_low.innerHTML='<div style="color:var(--dim);font-size:11px;padding:8px">No low stock items.</div>';
  ls.forEach(m=>{
    const txt=m.s<=0?'<span style="color:#ef4444;font-weight:600">Out of Stock</span>':`${m.s} units left`;
    g_low.innerHTML+=`<div class="ali"><div class="dot dr2"></div><div style="flex:1;min-width:0"><div>${m.n}</div><div style="font-size:10px;color:var(--mt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${shelfLabel(m)}</div></div><span style="font-size:10.5px;color:var(--mt)">${txt}</span></div>`
  });
  if(!ex.length)g_exp.innerHTML='<div style="color:var(--dim);font-size:11px;padding:8px">No near-expiry items.</div>';
  ex.forEach(m=>{g_exp.innerHTML+=`<div class="ali"><div class="dot dr2"></div><div style="flex:1;min-width:0"><div>${m.n}</div><div style="font-size:10px;color:var(--mt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${shelfLabel(m)}</div></div><span style="font-size:10.5px;color:var(--mt)">Exp: ${m.expiry}</span></div>`});
}
function clRep(){
    document.getElementById('rep-mod').style.display='none';
    const pb=document.getElementById('rep-print-btn');
    if(pb)pb.style.display='none';
}
function rStockRep(){
    const m=document.getElementById('rep-mod'), t=document.getElementById('rep-title'), c=document.getElementById('rep-content'), pb=document.getElementById('rep-print-btn');
    t.textContent='Inventory Stock Report';
    pb.style.display='block';
    pb.onclick=prInv;
    let tv=0, tp=0, ti=0;
    let rows=MEDS.map(i=>{
        const pr = parseFloat(i.p_rate)||0;
        const val=i.s*i.p, pval=i.s*pr;
        tv+=val; tp+=pval; ti+=i.s;
        return `<tr><td>${i.n}</td><td>${i.batch}</td><td>${i.s}</td><td>₹${pr||'—'}</td><td>₹${i.p}</td><td style="font-weight:600;color:var(--acc)">₹${val.toFixed(2)}</td></tr>`;
    }).join('');
    c.innerHTML=`<div class="kpi" style="margin-bottom:20px;grid-template-columns:repeat(3,1fr)">
        <div class="kc or"><div class="kl">Total Units</div><div class="kv">${ti}</div></div>
        <div class="kc gr"><div class="kl">Inventory Value (MRP)</div><div class="kv">₹${tv.toLocaleString('en-IN')}</div></div>
        <div class="kc bl"><div class="kl">Purchase Value (Cost)</div><div class="kv">₹${tp.toLocaleString('en-IN')}</div></div>
    </div><div class="tw"><table><thead><tr><th>Medicine</th><th>Batch</th><th>Qty</th><th>P.Rate</th><th>MRP</th><th>Valuation</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    m.style.display='flex';
}
function rExpRep(){
    const m=document.getElementById('rep-mod'), t=document.getElementById('rep-title'), c=document.getElementById('rep-content'), pb=document.getElementById('rep-print-btn');
    t.textContent='Detailed Expiry Report';
    pb.style.display='block';
    pb.onclick=prExp;
    const now=new Date();
    const ex=MEDS.filter(i=>i.expiry).sort((a,b)=>new Date(a.expiry)-new Date(b.expiry));
    let rows=ex.map(i=>{
        const ed=new Date(i.expiry), diff=(ed-now)/(1000*60*60*24);
        const st=diff<30?'br':(diff<90?'bo':'bg');
        return `<tr><td>${i.n}</td><td>${i.batch}</td><td><span class="bx ${st}">${i.expiry}</span></td><td>${i.s}</td><td>${Math.ceil(diff)} days</td></tr>`;
    }).join('');
    c.innerHTML=`<div class="tw"><table><thead><tr><th>Medicine</th><th>Batch</th><th>Expiry Date</th><th>Stock</th><th>Remaining</th></tr></thead><tbody>${rows||'<tr><td colspan="5" style="text-align:center">No items with expiry dates.</td></tr>'}</tbody></table></div>`;
    m.style.display='flex';
}
function rExpDel(){
    const m=document.getElementById('rep-mod'), t=document.getElementById('rep-title'), c=document.getElementById('rep-content');
    t.textContent='Export & Print Reports';
    c.innerHTML=`
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:10px">
            <div class="crd" style="padding:20px;text-align:center">
                <i class="fas fa-boxes-stacked" style="font-size:30px;color:var(--acc);margin-bottom:12px"></i>
                <div style="font-weight:600;margin-bottom:15px">Inventory Reports</div>
                <button class="btn btn-acc" onclick="dnInv()" style="width:100%;margin-bottom:8px">Download CSV (Excel)</button>
                <button class="btn btn-out" onclick="prInv()" style="width:100%">Print Report (PDF)</button>
            </div>
            <div class="crd" style="padding:20px;text-align:center">
                <i class="fas fa-file-invoice-dollar" style="font-size:30px;color:#22c55e;margin-bottom:12px"></i>
                <div style="font-weight:600;margin-bottom:15px">Sales History</div>
                <button class="btn btn-acc" onclick="dnSal()" style="width:100%;margin-bottom:8px" style="background:#22c55e;border-color:#22c55e">Download CSV (Excel)</button>
                <button class="btn btn-out" onclick="prSal()" style="width:100%">Print History (PDF)</button>
            </div>
        </div>
    `;
    m.style.display='flex';
}
function dnInv(){
    let csv="ID,Medicine Name,Generic,Category,MRP,Purch.Rate,Stock,Batch,Expiry,GST,Disc%\n";
    MEDS.forEach(i=>csv+=`"${i.id}","${i.n}","${i.g}","${i.c}","${i.p}","${i.p_rate}","${i.s}","${i.batch}","${i.expiry}","${i.p_gst}","${i.disc}"\n`);
    const blob=new Blob([csv],{type:'text/csv'}), url=window.URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download='Pharmacy_Inventory.csv'; a.click();
}
function dnSal(){
    let csv="Bill ID,Date,Customer,Phone,Doctor,Total,Discount,Tax,Payment Mode,Items\n";
    allBills.forEach(b=>{
        const its=(b.items||[]).map(i=>`${i.n}(${i.qty})`).join('; ');
        csv+=`"${b.id}","${b.date}","${b.cust}","${b.phone}","${b.doctor}","${b.total}","${b.disc}","${b.tax}","${b.pay}","${its}"\n`;
    });
    const blob=new Blob([csv],{type:'text/csv'}), url=window.URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download='Sales_History.csv'; a.click();
}
function prInv(){
    const w=window.open('','_blank');
    let rows=MEDS.map(i=>`<tr><td>${i.n}</td><td>${i.batch}</td><td>${i.expiry}</td><td>${i.s}</td><td>₹${i.p}</td></tr>`).join('');
    w.document.write(`<html><head><title>Inventory Report</title><style>body{font-family:sans-serif;padding:30px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f4f4f4}h2{margin:0}</style></head><body><h2>SELVAM MEDICALS - Inventory Report</h2><p>Date: ${new Date().toLocaleDateString()}</p><table><thead><tr><th>Medicine</th><th>Batch</th><th>Expiry</th><th>Stock</th><th>MRP</th></tr></thead><tbody>${rows}</tbody></table><script>window.print()<\/script></body></html>`);
    w.document.close();
}
function prExp(){
    const w=window.open('','_blank');
    const now=new Date();
    const ex=MEDS.filter(i=>i.expiry).sort((a,b)=>new Date(a.expiry)-new Date(b.expiry));
    let rows=ex.map(i=>{
        const ed=new Date(i.expiry), diff=(ed-now)/(1000*60*60*24);
        return `<tr><td>${i.n}</td><td>${i.batch}</td><td>${i.expiry}</td><td>${i.s}</td><td>${Math.ceil(diff)} days</td></tr>`;
    }).join('');
    w.document.write(`<html><head><title>Expiry Report</title><style>body{font-family:sans-serif;padding:30px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f4f4f4}h2{margin:0}</style></head><body><h2>SELVAM MEDICALS - Expiry Report</h2><p>As of: ${new Date().toLocaleDateString()}</p><table><thead><tr><th>Medicine</th><th>Batch</th><th>Expiry Date</th><th>Stock</th><th>Days Left</th></tr></thead><tbody>${rows||'<tr><td colspan="5">No items.</td></tr>'}</tbody></table><script>window.print()<\/script></body></html>`);
    w.document.close();
}
function prSal(){
    const w=window.open('','_blank');
    let rows=allBills.map(b=>`<tr><td>${b.id}</td><td>${b.date}</td><td>${b.cust}</td><td>₹${b.total.toFixed(2)}</td><td>${b.pay}</td></tr>`).join('');
    w.document.write(`<html><head><title>Sales History</title><style>body{font-family:sans-serif;padding:30px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f4f4f4}h2{margin:0}</style></head><body><h2>SELVAM MEDICALS - Sales History</h2><p>Print Date: ${new Date().toLocaleDateString()}</p><table><thead><tr><th>Bill ID</th><th>Date</th><th>Customer</th><th>Total</th><th>Payment</th></tr></thead><tbody>${rows}</tbody></table><script>window.print()<\/script></body></html>`);
    w.document.close();
}
function pb2(){
  const ks=Object.keys(cart);
  if(!ks.length){alert('Cart empty!');return;}
  const cnInp=document.getElementById('cn').value.trim(),cpInp=document.getElementById('cp').value.trim(),cdrInp=document.getElementById('cdr').value.trim();
  const custType=(document.getElementById('cust-type')||{}).value||'customer';
  const billType=(document.getElementById('bill-type')||{}).value||'retail';
  if(!cnInp||!cpInp){alert('Please enter Name and Phone Number.');return;}
  const sub=ks.reduce((s,k)=>s+cart[k].p*cart[k].qty,0);
  const dv=parseFloat(document.getElementById('dv').value)||0,dt=document.getElementById('dt').value;
  const modeDisc=billType==='wholesale'?sub*0.08:0;
  const da=dt==='pct'?sub*(dv/100):Math.min(dv,sub);
  const taxable=Math.max(sub-modeDisc-da,0),tax=taxable*0.05,tot=taxable+tax;
  const now=new Date(),ds=pd(now.getDate())+'/'+pd(now.getMonth()+1)+'/'+now.getFullYear()+' '+pd(now.getHours())+':'+pd(now.getMinutes());
  const bId='B-'+(allBills.length+1);
  const savedItems=ks.map(k=>({...cart[k]})); // snapshot before clearing
  const billData={id:bId,ts:now.getTime(),date:ds,cust:cnInp,phone:cpInp,doctor:cdrInp,pay:pm,sub:sub,disc:da+modeDisc,tax:tax,total:tot,items:savedItems,prescription:rxBase64,customer_type:custType,bill_type:billType};
  console.log('Final Bill Payload prescription length:', (billData.prescription||'').length);
  
  fetch(API+'/bills',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(billData)})
  .then(r=>{if(!r.ok)throw new Error('Server returned '+r.status);return r.json();})
  .then(()=>{
    // ALL UI refreshes happen AFTER server confirms save
    rKpis();
    loadInventory();
    rMasters();
    rxBase64='';
    const btn=document.getElementById('btn-rx'), prev=document.getElementById('rx-preview');
    if(btn){btn.innerHTML='<i class="fas fa-file-prescription"></i> Attach Prescription';btn.style.borderColor='var(--brd)';btn.style.color='var(--mt)';}
    if(prev){prev.src='';prev.style.display='none';}
    // Clear cart & form
    cart={};
    rct();
    document.getElementById('cn').value='';
    document.getElementById('cp').value='';
    document.getElementById('cdr').value='';
    document.getElementById('cust-type').value='customer';
    document.getElementById('bill-type').value='retail';
    if(document.getElementById('pos-face-vector'))document.getElementById('pos-face-vector').value='';
    renderHeldBills();
    generateWantedList();
    // Print receipt
    const rows=savedItems.map(i=>'<tr><td>'+i.n+'</td><td style="text-align:center">'+i.qty+'</td><td style="text-align:right">₹'+i.p+'</td><td style="text-align:right">₹'+(i.p*i.qty).toFixed(2)+'</td></tr>').join('');
    const w=window.open('','_blank','width=400,height=580');
    w.document.write('<!DOCTYPE html><html><head><title>Bill</title><style>body{font-family:Courier New,monospace;padding:18px;font-size:12px}h2{text-align:center;font-size:17px;margin:0}p{margin:2px 0;text-align:center;font-size:10px;color:#555}hr{border:none;border-top:1px dashed #999;margin:8px 0}table{width:100%;border-collapse:collapse}th{border-bottom:1px solid #000;padding:3px 0;text-align:left;font-size:11px}td{padding:3px 0;font-size:11px}.r{text-align:right}.tot{font-weight:700;border-top:1px dashed #999}</style></head><body><h2>SELVAM MEDICALS</h2><p>Pharmacy & Health Store | Ph: 044-XXXXXXXX</p><hr/><p style="text-align:left">Bill: #'+bId+' | Date: '+ds+'</p><p style="text-align:left;margin-bottom:6px;">'+custType.toUpperCase()+': '+cnInp+' | Phone: '+cpInp+' | Ref: '+(cdrInp||'-')+'</p><p style="text-align:left">Pay: '+pm.toUpperCase()+' | Type: '+billType.toUpperCase()+'</p><hr/><table><thead><tr><th>Medicine</th><th style="text-align:center">Qty</th><th class="r">MRP</th><th class="r">Amt</th></tr></thead><tbody>'+rows+'</tbody></table><hr/><table><tr><td>Subtotal</td><td class="r">₹'+sub.toFixed(2)+'</td></tr><tr><td>Discount</td><td class="r">-₹'+(da+modeDisc).toFixed(2)+'</td></tr><tr><td>GST 5%</td><td class="r">₹'+tax.toFixed(2)+'</td></tr><tr class="tot"><td>TOTAL</td><td class="r">₹'+tot.toFixed(2)+'</td></tr></table><p style="margin-top:12px">Thank you! Get well soon 💊</p><scr'+'ipt>window.print();<\/scr'+'ipt></body></html>');
    w.document.close();
  }).catch(e=>alert('Bill Save Error: '+e.message));
}

loadInventory();
rKpis();
rPurchases();
rMasters();

function rBckMod(){
    const m=document.getElementById('rep-mod'), t=document.getElementById('rep-title'), c=document.getElementById('rep-content');
    t.textContent='System Backup Options';
    c.innerHTML=`
        <div style="display:flex;flex-direction:column;gap:15px;padding:10px">
            <div class="crd" style="padding:20px;display:flex;align-items:center;gap:20px">
                <i class="fas fa-file-shield" style="font-size:32px;color:#a78bfa"></i>
                <div style="flex:1">
                    <div style="font-weight:700">Full Database Backup (.db)</div>
                    <div style="font-size:11px;color:var(--mt)">The most secure way to save every single record.</div>
                </div>
                <button class="btn btn-acc" onclick="window.open(API+'/backup')">Download .db</button>
            </div>
            <div class="crd" style="padding:20px;display:flex;align-items:center;gap:20px">
                <i class="fas fa-file-excel" style="font-size:32px;color:#22c55e"></i>
                <div style="flex:1">
                    <div style="font-weight:700">Excel Master Backup (CSV)</div>
                    <div style="font-size:11px;color:var(--mt)">Downloads all Medicines, Customers, and Sales in one file.</div>
                </div>
                <button class="btn btn-acc" onclick="dnFullCsv()" style="background:#22c55e;border-color:#22c55e">Download CSV</button>
            </div>
            <div class="crd" style="padding:20px;display:flex;align-items:center;gap:20px">
                <i class="fas fa-file-pdf" style="font-size:32px;color:#ef4444"></i>
                <div style="flex:1">
                    <div style="font-weight:700">System Audit PDF</div>
                    <div style="font-size:11px;color:var(--mt)">Generates a printable summary of your current status.</div>
                </div>
                <button class="btn btn-out" onclick="prFullPdf()">Print PDF</button>
            </div>
        </div>
    `;
    m.style.display='flex';
}
function dnFullCsv(){
    let csv="### MEDICINES INVENTORY ###\nID,Name,Units(Stock),Batch,Expiry,MRP,Purch.Rate,Status\n";
    MEDS.forEach(i=>{
        const st=i.s<=0?'OUT':(i.s<15?'LOW':'OK');
        csv+=`"${i.id}","${i.n}","${i.s}","${i.batch}","${i.expiry}","${i.p}","${i.p_rate}","${st}"\n`;
    });
    csv+="\n### CUSTOMERS ###\nID,Name,Phone,Spend\n";
    AM.filter(x=>x.type==='cust').forEach(c=>csv+=`"${c.id}","${c.n}","${c.p}","${c.spend}"\n`);
    csv+="\n### RECENT SALES ###\nID,Date,Customer,Total\n";
    allBills.slice(0,100).forEach(b=>csv+=`"${b.id}","${b.date}","${b.cust}","${b.total}"\n`);
    const blob=new Blob([csv],{type:'text/csv'}), url=window.URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download='Pharmacy_Full_Master_Backup.csv'; a.click();
}
function prFullPdf(){
    const w=window.open('','_blank');
    const totV=MEDS.reduce((s,i)=>s+(i.s*i.p),0);
    const totC=AM.filter(x=>x.type==='cust').length;
    const ls=MEDS.filter(i=>i.s<15);
    
    let mRows=MEDS.map(i=>`<tr><td>${i.n}</td><td>${i.batch}</td><td>${i.expiry}</td><td>${i.s}</td><td>₹${i.p}</td></tr>`).join('');
    let sRows=allBills.slice(0,30).map(b=>`<tr><td>${b.id}</td><td>${b.date}</td><td>${b.cust}</td><td>₹${b.total}</td></tr>`).join('');
    let lsRows=ls.map(i=>`<tr><td>${i.n}</td><td>${i.s} units</td><td style="color:#ef4444;font-weight:700">${i.s<=0?'OUT OF STOCK':'LOW STOCK'}</td></tr>`).join('');

    w.document.write(`<html><head><title>System Audit</title><style>body{font-family:sans-serif;padding:30px;color:#1e293b}table{width:100%;border-collapse:collapse;margin:15px 0 30px}th,td{border:1px solid #e2e8f0;padding:8px;text-align:left;font-size:12px}th{background:#f8fafc;font-weight:700}h1{margin:0;color:#0f172a}h2,h3{border-bottom:2px solid #e2e8f0;padding-bottom:5px;margin-top:25px}hr{margin:20px 0;opacity:0.2}.br{color:#ef4444}</style></head><body>
        <h1>SELVAM MEDICALS - MASTER AUDIT</h1>
        <p>Date: ${new Date().toLocaleString()}</p>
        <hr/>
        <h3>1. System Summary</h3>
        <table style="width:auto;min-width:300px">
            <tr><td>Total Medicines</td><td>${MEDS.length}</td></tr>
            <tr><td>Inventory Value (MRP)</td><td>₹${totV.toLocaleString()}</td></tr>
            <tr><td>Total Registered Customers</td><td>${totC}</td></tr>
            <tr><td>Total Bills Generated</td><td>${allBills.length}</td></tr>
            <tr><td>Low/Out of Stock Items</td><td class="br">${ls.length}</td></tr>
        </table>

        <h3 class="br">2. LOW STOCK ALERTS (Critical)</h3>
        <table><thead><tr><th>Medicine</th><th>Current Units</th><th>Alert Type</th></tr></thead><tbody>${lsRows||'<tr><td colspan="3">All stock levels healthy.</td></tr>'}</tbody></table>

        <h3>3. Full Inventory List</h3>
        <table><thead><tr><th>Medicine</th><th>Batch</th><th>Expiry</th><th>Units</th><th>MRP</th></tr></thead><tbody>${mRows||'<tr><td colspan="5">No medicines.</td></tr>'}</tbody></table>

        <h3>4. Recent Sales History (Top 30)</h3>
        <table><thead><tr><th>Bill ID</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead><tbody>${sRows||'<tr><td colspan="4">No sales history.</td></tr>'}</tbody></table>
        
        <p style="margin-top:40px;font-size:11px;color:#64748b;text-align:center">This is an automated system audit report generated by Selvam Medicals POS.</p>
        <script>window.print()<\/script>
    </body></html>`);
    w.document.close();
}
function apur(){
  document.getElementById('pur-mod').style.display='flex';
  document.getElementById('pur-s').value='';
  document.getElementById('pur-i').value='';
  document.getElementById('pur-a').value=0;
  document.getElementById('pur-s').focus();
}

function sv_pur(){
  const s=document.getElementById('pur-s').value.trim(),i=document.getElementById('pur-i').value.trim(),a=parseFloat(document.getElementById('pur-a').value)||0,st=document.getElementById('pur-st').value;
  if(!s||!i){alert('Enter Supplier and Items');return;}
  const now=new Date(),ds=pd(now.getDate())+'/'+pd(now.getMonth()+1)+'/'+now.getFullYear();
  const id='P-'+Date.now().toString().slice(-4);
  fetch(API+'/purchases',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,supplier:s,items:i,amount:a,date:ds,status:st})
  }).then(()=>{
    rPurchases();
    rMasters();
    document.getElementById('pur-mod').style.display='none';
    alert('Purchase order saved!');
  });
}

function normalizeMedName(t){
  return String(t||'').toLowerCase().replace(/tablets?/g,'').replace(/capsules?/g,'').replace(/syrup/g,'').replace(/mg/g,'').replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
}

function renderPurchaseImportPreview(){
  const tb=document.getElementById('pur-import-preview');
  if(!tb)return;
  if(!purchaseImportRows.length){tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:var(--dim)">No Excel parsed yet.</td></tr>';return;}
  tb.innerHTML=purchaseImportRows.slice(0,200).map(r=>`<tr><td>${r.name}</td><td>${r.qty}</td><td>₹${r.price.toFixed(2)}</td><td>${r.batch||'—'}</td><td>${r.expiry||'—'}</td></tr>`).join('');
}

function parsePurchaseExcel(){
  const fi=document.getElementById('pur-xl-file');
  if(!fi||!fi.files||!fi.files[0]){alert('Choose an Excel/CSV file first.');return;}
  const file=fi.files[0];
  const reader=new FileReader();
  reader.onload=(e)=>{
    try{
      const wb=XLSX.read(e.target.result,{type:'binary'});
      const ws=wb.Sheets[wb.SheetNames[0]];
      const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});
      if(!rows.length){purchaseImportRows=[];renderPurchaseImportPreview();return;}
      const hd=rows[0].map(x=>String(x).toLowerCase().trim());
      const idx=(...alts)=>hd.findIndex(h=>alts.includes(h));
      const iName=idx('medicine','item','product','name');
      const iQty=idx('qty','quantity','stock','units','strips');
      const iPrice=idx('mrp','price','rate','ptr','amount');
      const iBatch=idx('batch','batchno','batch_no');
      const iExp=idx('exp','expiry','expirydate','expiry_date');
      if(iName<0||iQty<0){alert('Required columns missing: medicine/item and qty/stock');return;}
      purchaseImportRows=rows.slice(1).map(r=>({
        name:String(r[iName]||'').trim(),
        qty:Math.max(0,parseInt(r[iQty],10)||0),
        price:iPrice>=0?(parseFloat(r[iPrice])||0):0,
        batch:iBatch>=0?String(r[iBatch]||'').trim():'',
        expiry:iExp>=0?String(r[iExp]||'').trim():''
      })).filter(x=>x.name&&x.qty>0);
      renderPurchaseImportPreview();
      alert(`Parsed ${purchaseImportRows.length} rows.`);
    }catch(err){
      alert('Excel parse failed: '+err.message);
    }
  };
  reader.readAsBinaryString(file);
}

function importPurchaseExcelToInventory(){
  if(!purchaseImportRows.length){alert('No parsed rows to import.');return;}
  const now=new Date(),ds=pd(now.getDate())+'/'+pd(now.getMonth()+1)+'/'+now.getFullYear();
  const reqs=[];
  let amount=0;
  purchaseImportRows.forEach((r,ix)=>{
    amount += (r.price||0) * r.qty;
    const found=MEDS.find(m=>normalizeMedName(m.n)===normalizeMedName(r.name));
    let payload;
    if(found){
      payload={...found,s:(parseInt(found.s,10)||0)+r.qty,batch:r.batch||found.batch,expiry:r.expiry||found.expiry,p:r.price>0?r.price:found.p,p_rate:r.price>0?r.price:found.p_rate};
    }else{
      payload={
        id:'m_'+Date.now()+'_'+ix,
        n:r.name,g:'Generic',c:'Tablet',
        p:r.price>0?r.price:1,s:r.qty,batch:r.batch||'',expiry:r.expiry||'',
        p_rate:r.price>0?r.price:0,p_packing:'',s_packing:'',p_gst:12,s_gst:12,disc:0,offer:'',reorder:10,max_qty:200
      };
    }
    reqs.push(fetch(API+'/medicines',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));
  });
  Promise.all(reqs).then(()=>{
    return fetch(API+'/purchases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      id:'PX-'+Date.now().toString().slice(-5),
      supplier:'Excel Import',
      items:`Excel Stock Import (${purchaseImportRows.length} lines)`,
      amount:parseFloat(amount.toFixed(2)),
      date:ds,
      status:'Received'
    })});
  }).then(()=>{
    purchaseImportRows=[];
    renderPurchaseImportPreview();
    loadInventory();
    rPurchases();
    alert('Excel import completed and stock updated.');
  }).catch(err=>alert('Import error: '+err.message));
}

function addConnectorSite(){
  const n=document.getElementById('site-name')?.value.trim();
  const c=document.getElementById('site-catalog')?.value.trim();
  if(!n||!c){alert('Enter website name and catalog mapping list.');return;}
  connectorSites.push({id:'site-'+Date.now(),name:n,catalog:c.split(',').map(x=>x.trim()).filter(Boolean)});
  saveConnectorSites();
  document.getElementById('site-name').value='';
  document.getElementById('site-catalog').value='';
  renderConnectorSites();
}

function removeConnectorSite(id){
  connectorSites=connectorSites.filter(x=>x.id!==id);
  saveConnectorSites();
  renderConnectorSites();
}

function renderConnectorSites(){
  const tb=document.getElementById('site-body');
  if(!tb)return;
  if(!connectorSites.length){tb.innerHTML='<tr><td colspan="3" style="text-align:center;color:var(--dim)">No sites configured.</td></tr>';return;}
  tb.innerHTML=connectorSites.map(s=>`<tr><td>${s.name}</td><td style="font-size:11px;color:var(--mt)">${(s.catalog||[]).join(', ')}</td><td style="text-align:right"><button class="btn btn-r" style="padding:4px 8px" onclick="removeConnectorSite('${s.id}')">Delete</button></td></tr>`).join('');
}

function parseBillDateToTs(b){
  if(b.ts)return Number(b.ts);
  const p=String(b.date||'').split(' ')[0].split('/');
  if(p.length===3)return new Date(Number(p[2]),Number(p[1])-1,Number(p[0])).getTime();
  return 0;
}

function matchedSiteForMedicine(medName){
  const n=normalizeMedName(medName);
  for(const s of connectorSites){
    if((s.catalog||[]).some(x=>{
      const k=normalizeMedName(x);
      return k && (k.includes(n)||n.includes(k));
    })) return s.name;
  }
  return 'No Match';
}

function generateWantedList(){
  const days=parseInt(document.getElementById('ro-days')?.value,10)||30;
  const lead=parseInt(document.getElementById('ro-lead')?.value,10)||7;
  const safety=parseInt(document.getElementById('ro-safety')?.value,10)||8;
  const since=Date.now()-days*24*60*60*1000;
  const salesMap={};
  allBills.forEach(b=>{
    if(parseBillDateToTs(b)<since)return;
    (b.items||[]).forEach(i=>{
      salesMap[i.n]=(salesMap[i.n]||0)+(parseInt(i.qty,10)||0);
    });
  });
    wantedRows=MEDS.map(m=>{
    const sold=salesMap[m.n]||0;
    const avg=sold/days;
    const minPoint=parseInt(m.reorder,10)||10;
    const forecast=Math.ceil(avg*lead+safety);
    const reorderPoint=Math.max(minPoint,forecast);
    const wanted=Math.max(0,reorderPoint-(parseInt(m.s,10)||0));
    return {name:m.n,stock:parseInt(m.s,10)||0,minPoint,avg,forecast,reorderPoint,wanted,site:matchedSiteForMedicine(m.n),shelf:shelfLabel(m)};
  }).sort((a,b)=>b.wanted-a.wanted);
  const tb=document.getElementById('ro-body');
  if(!tb)return;
  if(!wantedRows.length){tb.innerHTML='<tr><td colspan="9" style="text-align:center;color:var(--dim)">No inventory data.</td></tr>';return;}
  tb.innerHTML=wantedRows.map(r=>`<tr><td>${r.name}</td><td>${r.shelf}</td><td>${r.stock}</td><td>${r.minPoint}</td><td>${r.avg.toFixed(2)}</td><td>${r.forecast}</td><td style="font-weight:700;color:${r.wanted>0?'#f5a623':'#22c55e'}">${r.wanted}</td><td>${r.site}</td><td>${r.wanted>0?'<span class="bx br">REORDER</span>':'<span class="bx bg">OK</span>'}</td></tr>`).join('');
}

function exportWantedCsv(){
  if(!wantedRows.length){alert('Generate wanted list first.');return;}
  let csv='Medicine,Shelf,Stock,ReorderPoint,WantedQty,MatchedSite\n';
  wantedRows.filter(r=>r.wanted>0).forEach(r=>csv+=`"${r.name}","${r.shelf}","${r.stock}","${r.reorderPoint}","${r.wanted}","${r.site}"\n`);
  const blob=new Blob([csv],{type:'text/csv'}), url=window.URL.createObjectURL(blob), a=document.createElement('a');
  a.href=url; a.download='wanted_reorder_list.csv'; a.click();
}

window.onload = () => { 
  document.querySelectorAll('.ni').forEach(n => n.tabIndex = 0);
  document.getElementById('ms').focus();
  initUsers();
  initBillResizer();
  renderHeldBills();
  renderConnectorSites();

  const us=document.getElementById('user-switch');
  if(us){
    us.addEventListener('change',e=>{
      CUR_USER_ID=e.target.value;
      localStorage.setItem('currentUserId',CUR_USER_ID);
      renderUserSwitch();
      applyRoleAccess();
    });
  }

  if(window.faceapi && faceapi.nets) {
      Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(STATIC_BASE + '/models'),
        faceapi.nets.faceLandmark68Net.loadFromUri(STATIC_BASE + '/models'),
        faceapi.nets.faceRecognitionNet.loadFromUri(STATIC_BASE + '/models')
      ]).then(() => console.log('Face API AI models loaded!')).catch(e=>console.log('Model err:',e));
  }
  if(typeof rMasters === 'function') rMasters();
  if(typeof rPurchases === 'function') rPurchases();
  fetch(API+'/medicines').then(r=>r.json()).then(ms=>{
      MEDS=ms; filteredMeds=ms; 
      if(typeof rmed === 'function') rmed(ms);
      if(typeof rItems === 'function') rItems(ms);
      if(typeof generateWantedList==='function')generateWantedList();
  }).catch(e=>console.log(e));

  // Customer Sync
  document.getElementById('cn').addEventListener('input', e => {
    const v=e.target.value; const c=CUSTOMERS.find(x=>x.name===v);
    if(c) document.getElementById('cp').value=c.phone;
  });
  document.getElementById('cp').addEventListener('input', e => {
    const v=e.target.value; const c=CUSTOMERS.find(x=>x.phone===v);
    if(c) document.getElementById('cn').value=c.name;
  });

  // Refresh heartbeat
  setInterval(() => {
    if(typeof rKpis === 'function') rKpis();
    if(typeof loadInventory === 'function') loadInventory();
  }, 5000);
};
