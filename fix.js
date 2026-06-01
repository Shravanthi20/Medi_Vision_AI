function renderPurchaseImportPreview(){
  const tb=document.getElementById('pur-import-preview');
  if(!tb)return;
  if(!purchaseImportRows.length){tb.innerHTML='<tr><td colspan="5" style="text-align:center;color:var(--dim)">No Excel parsed yet.</td></tr>';return;}
  tb.innerHTML=purchaseImportRows.slice(0,200).map(r=>`<tr><td>${r.name}</td><td>${r.qty}</td><td>₹${r.prate.toFixed(2)}</td><td>${r.batch||'—'}</td><td>${r.expiry||'—'}</td></tr>`).join('');
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
      const iGeneric=idx('generic','genericname','generic_name');
      const iCat=idx('category','type');
      const iShelf=idx('shelf','location','rack');
      const iQty=idx('qty','quantity','stock','units','strips');
      const iMrp=idx('mrp','price','selling_price','mrp_price');
      const iPrate=idx('prate','purchase_rate','ptr','rate','p_rate','cost','amount');
      const iBatch=idx('batch','batchno','batch_no');
      const iExp=idx('exp','expiry','expirydate','expiry_date');
      const iPPak=idx('p_packing','purchase_packing','purchasepacking');
      const iSPak=idx('s_packing','sales_packing','salespacking','packing');
      const iPgst=idx('p_gst','purchase_gst','purchasegst','gst');
      const iSgst=idx('s_gst','sales_gst','salesgst');
      const iDisc=idx('disc','discount');
      const iOffer=idx('offer');
      if(iName<0||iQty<0){alert('Required columns missing: medicine/item and qty/stock');return;}
      purchaseImportRows=rows.slice(1).map(r=>({
        name:String(r[iName]||'').trim(),
        generic:iGeneric>=0?String(r[iGeneric]||'').trim():'',
        category:iCat>=0?String(r[iCat]||'').trim():'',
        shelf:iShelf>=0?String(r[iShelf]||'').trim():'',
        qty:Math.max(0,parseInt(r[iQty],10)||0),
        mrp:iMrp>=0?(parseFloat(r[iMrp])||0):0,
        prate:iPrate>=0?(parseFloat(r[iPrate])||0):0,
        batch:iBatch>=0?String(r[iBatch]||'').trim():'',
        expiry:iExp>=0?String(r[iExp]||'').trim():'',
        p_packing:iPPak>=0?String(r[iPPak]||'').trim():'',
        s_packing:iSPak>=0?String(r[iSPak]||'').trim():'',
        p_gst:iPgst>=0?(parseFloat(r[iPgst])||12):12,
        s_gst:iSgst>=0?(parseFloat(r[iSgst])||12):12,
        disc:iDisc>=0?(parseFloat(r[iDisc])||0):0,
        offer:iOffer>=0?String(r[iOffer]||'').trim():''
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
    amount += (r.prate||0) * r.qty;
    const found=MEDS.find(m=>normalizeMedName(m.n)===normalizeMedName(r.name));
    let payload;
    if(found){
      payload={...found,
               s:(parseInt(found.s,10)||0)+r.qty,
               batch:r.batch||found.batch,
               expiry:r.expiry||found.expiry,
               p:r.mrp>0?r.mrp:found.p,
               p_rate:r.prate>0?r.prate:found.p_rate,
               g:r.generic||found.g,
               c:r.category||found.c,
               shelf_id:r.shelf||found.shelf_id,
               p_packing:r.p_packing||found.p_packing,
               s_packing:r.s_packing||found.s_packing,
               p_gst:r.p_gst||found.p_gst,
               s_gst:r.s_gst||found.s_gst,
               disc:r.disc||found.disc,
               offer:r.offer||found.offer
               };
    }else{
      payload={
        id:'m_'+Date.now()+'_'+ix,
        n:r.name,
        g:r.generic||'Generic',
        c:r.category||'Tablet',
        p:r.mrp>0?r.mrp:(r.prate>0?r.prate:1),
        s:r.qty,
        batch:r.batch||'',
        expiry:r.expiry||'',
        p_rate:r.prate>0?r.prate:0,
        p_packing:r.p_packing||'',
        s_packing:r.s_packing||'',
        p_gst:r.p_gst||12,
        s_gst:r.s_gst||12,
        disc:r.disc||0,
        offer:r.offer||'',
        reorder:10,
        max_qty:200,
        shelf_id:r.shelf||''
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
