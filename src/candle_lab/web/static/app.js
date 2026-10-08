const $=id=>document.getElementById(id);
const state={
  symbols:[],sessions:[],candles:[],detail:null,replay:0,timer:null,selected:null,
  overview:[],overviewSessions:[],overviewCandles:[],overviewMeta:null,
  dragStart:null,dragCurrent:null,selection:null,indexLocation:null
};

async function api(url,opts={}){
  const r=await fetch(url,opts);
  if(!r.ok){let d;try{d=await r.json()}catch(e){}throw new Error(d&&d.detail?d.detail:r.statusText)}
  return r.json();
}
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=2)=>Number(v||0).toLocaleString('pt-BR',{maximumFractionDigits:d});
const pct=v=>n((v||0)*100,1)+'%';
const clock=iso=>new Date(iso).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
const shortClock=iso=>new Date(iso).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});

function draw(canvas,values,count){
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
  const arr=values.slice(0,count==null?values.length:Math.max(1,count));if(!arr.length)return;
  const nums=arr.map(v=>typeof v==='number'?v:v.price),lo=Math.min(...nums),hi=Math.max(...nums),span=hi-lo||1;
  ctx.strokeStyle='#5db5ff';ctx.lineWidth=2;ctx.beginPath();
  nums.forEach((v,i)=>{const x=18+(w-36)*(i/Math.max(nums.length-1,1)),y=h-18-(h-36)*((v-lo)/span);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)});ctx.stroke();
}

function drawDayChart(){
  const canvas=$('dayCanvas'),ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
  ctx.clearRect(0,0,w,h);
  const candles=state.overviewCandles;
  if(!candles.length)return;
  const left=66,right=20,top=20,bottom=42,plotW=w-left-right,plotH=h-top-bottom;
  const lo=Math.min(...candles.map(c=>c.low)),hi=Math.max(...candles.map(c=>c.high)),span=hi-lo||1;
  const y=p=>top+plotH-(p-lo)/span*plotH;
  const step=plotW/candles.length;
  const bodyW=Math.max(1,Math.min(7,step*.62));

  ctx.strokeStyle='#183048';ctx.lineWidth=1;ctx.fillStyle='#8298ad';ctx.font='11px Segoe UI';
  for(let i=0;i<=5;i++){
    const yy=top+plotH*i/5,price=hi-span*i/5;
    ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();
    ctx.fillText(n(price,2),4,yy+4);
  }

  const labelEvery=Math.max(1,Math.ceil(candles.length/10));
  candles.forEach((c,i)=>{
    const x=left+step*(i+.5);
    const up=c.close>=c.open;
    ctx.strokeStyle=up?'#63d7ae':'#f47f8d';
    ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(x,y(c.high));ctx.lineTo(x,y(c.low));ctx.stroke();
    const yo=y(c.open),yc=y(c.close),bh=Math.max(1,Math.abs(yc-yo));
    ctx.fillRect(x-bodyW/2,Math.min(yo,yc),bodyW,bh);
    if(i%labelEvery===0){
      ctx.fillStyle='#71869a';ctx.fillText(shortClock(c.start),Math.max(left,x-18),h-14);
    }
  });

  if(state.dragStart!=null){
    const a=Math.min(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
    const b=Math.max(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
    const x1=left+step*a,x2=left+step*(b+1);
    ctx.fillStyle='rgba(93,181,255,.13)';ctx.fillRect(x1,top,x2-x1,plotH);
    ctx.strokeStyle='#5db5ff';ctx.lineWidth=2;ctx.strokeRect(x1,top,x2-x1,plotH);
  }
}

function dayIndexFromEvent(e){
  const canvas=$('dayCanvas'),rect=canvas.getBoundingClientRect();
  const x=(e.clientX-rect.left)*(canvas.width/rect.width);
  const left=66,right=20,plotW=canvas.width-left-right;
  const idx=Math.floor((x-left)/(plotW/Math.max(state.overviewCandles.length,1)));
  return Math.max(0,Math.min(state.overviewCandles.length-1,idx));
}

function finalizeSelection(){
  if(state.dragStart==null||!state.overviewCandles.length)return;
  const a=Math.min(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
  const b=Math.max(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
  const first=state.overviewCandles[a],last=state.overviewCandles[b];
  state.selection={start:first.start,end:last.end,startIndex:a,endIndex:b,count:b-a+1};
  $('selectionLabel').textContent=clock(first.start)+' → '+clock(last.end);
  $('selectionCount').textContent=String(state.selection.count);
  $('selectionInfo').classList.remove('hidden');
  state.indexLocation=null;
  $('locateBtn').disabled=false;
  $('sliceBtn').disabled=true;
  $('lineMapWrap').classList.add('hidden');
  $('indexResult').textContent='Intervalo pronto. Cole o caminho do CSV grande e clique em “Preparar índice e localizar”.';
  $('sliceResult').textContent='Prepare primeiro o índice temporal.';
  drawDayChart();
}

async function refreshOverview(preferredSymbol=null){
  state.overview=await api('/api/reference-overview');
  const symbols=[...new Set(state.overview.map(x=>x.symbol))];
  $('overviewSymbolSelect').innerHTML=symbols.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join('');
  if(!symbols.length){
    state.overviewCandles=[];$('overviewEmpty').classList.remove('hidden');drawDayChart();return;
  }
  if(preferredSymbol&&symbols.includes(preferredSymbol))$('overviewSymbolSelect').value=preferredSymbol;
  await loadOverviewSessions();
}

async function loadOverviewSessions(){
  const symbol=$('overviewSymbolSelect').value;
  if(!symbol)return;
  state.overviewSessions=await api('/api/reference-sessions?symbol='+encodeURIComponent(symbol));
  $('overviewSessionSelect').innerHTML=state.overviewSessions.map((x,i)=>
    '<option value="'+i+'">'+x.session_date+' · '+(x.interval_seconds/60)+' min · '+x.candles+' candles</option>'
  ).join('');
  if(state.overviewSessions.length)await loadOverviewCandles();
}

async function loadOverviewCandles(){
  const symbol=$('overviewSymbolSelect').value,idx=Number($('overviewSessionSelect').value||0);
  const meta=state.overviewSessions[idx];if(!symbol||!meta)return;
  state.overviewMeta=state.overview.find(x=>x.symbol===symbol&&x.session_date===meta.session_date&&x.interval_seconds===meta.interval_seconds)||meta;
  state.overviewCandles=await api('/api/reference-candles?symbol='+encodeURIComponent(symbol)+'&session_date='+meta.session_date+'&interval_seconds='+meta.interval_seconds);
  state.dragStart=null;state.dragCurrent=null;state.selection=null;state.indexLocation=null;
  $('selectionInfo').classList.add('hidden');$('locateBtn').disabled=true;$('sliceBtn').disabled=true;$('lineMapWrap').classList.add('hidden');
  $('overviewEmpty').classList.toggle('hidden',state.overviewCandles.length>0);
  if(state.overviewMeta&&state.overviewMeta.tick_size)$('sliceTickInput').value=state.overviewMeta.tick_size;
  drawDayChart();
}

async function refresh(){
  const status=await api('/api/status');$('statusBadge').textContent='v'+status.version+' · '+n(status.trades,0)+' negócios';
  state.symbols=await api('/api/symbols');
  $('symbolSelect').innerHTML=state.symbols.map(x=>'<option value="'+esc(x.symbol)+'">'+esc(x.symbol)+' · '+n(x.trades,0)+' negócios</option>').join('');
  if(state.symbols.length)await loadSessions();else{$('sessionSelect').innerHTML='';$('candleBody').innerHTML='<tr><td colspan="7">Gere um recorte Tick para iniciar a análise profunda.</td></tr>'}
}

async function loadSessions(){
  const symbol=$('symbolSelect').value;
  state.sessions=await api('/api/sessions?symbol='+encodeURIComponent(symbol));
  $('sessionSelect').innerHTML=state.sessions.map(x=>'<option value="'+x.session_date+'">'+x.session_date+' · '+n(x.trades,0)+' negócios</option>').join('');
  if(state.sessions.length)await loadCandles();else{
    $('candleBody').innerHTML='<tr><td colspan="7">Este ativo possui apenas o gráfico diário. Selecione um intervalo acima e gere o recorte Tick.</td></tr>';
    $('qualityBox').textContent='Ainda não há microestrutura importada para este ativo.';
  }
}

async function loadCandles(){
  clearInterval(state.timer);state.detail=null;state.selected=null;
  ['labCard','researchCard','trajectoryCard','transitionCard'].forEach(id=>$(id).classList.add('hidden'));
  const symbol=$('symbolSelect').value,date=$('sessionSelect').value,interval=$('intervalSelect').value;if(!symbol||!date)return;
  state.candles=await api('/api/candles?symbol='+encodeURIComponent(symbol)+'&session_date='+date+'&interval_seconds='+interval);
  $('candleBody').innerHTML=state.candles.map((c,i)=>'<tr data-i="'+i+'"><td>'+clock(c.start)+'</td><td>'+n(c.open)+'</td><td>'+n(c.high)+'</td><td>'+n(c.low)+'</td><td>'+n(c.close)+'</td><td>'+n(c.volume,0)+'</td><td>'+n(c.trades,0)+'</td></tr>').join('');
  document.querySelectorAll('#candleBody tr').forEach(tr=>tr.onclick=()=>selectCandle(Number(tr.dataset.i),tr));
  try{const q=await api('/api/session-quality?symbol='+encodeURIComponent(symbol)+'&session_date='+date);$('qualityBox').textContent='Qualidade do recorte: '+q.status+' · score '+n(q.score,1)+' · cobertura '+(q.coverage_ratio==null?'—':pct(q.coverage_ratio))+' · lacunas '+n(q.gap_count,0)}catch(e){$('qualityBox').textContent='Qualidade: '+e.message}
  try{const v=await api('/api/reconciliation?symbol='+encodeURIComponent(symbol)+'&session_date='+date+'&interval_seconds='+interval);const sm=v.summary;if(!sm.reference_candles){$('validationBox').textContent=v.message||'Nenhuma referência OHLC para este período.'}else{$('validationBox').textContent='Validação do recorte: '+sm.exact+'/'+sm.reference_candles+' EXACT · '+sm.mismatch+' divergente(s) · taxa exata '+pct(sm.exact_rate)}}catch(e){$('validationBox').textContent='Validação indisponível: '+e.message}
}

async function selectCandle(i,row){
  document.querySelectorAll('#candleBody tr').forEach(x=>x.classList.remove('selected'));row.classList.add('selected');
  state.selected=state.candles[i];const symbol=$('symbolSelect').value,interval=$('intervalSelect').value;
  state.detail=await api('/api/candle-detail?symbol='+encodeURIComponent(symbol)+'&start='+encodeURIComponent(state.selected.start)+'&interval_seconds='+interval);
  state.replay=state.detail.timeline.length;$('selectedTitle').textContent=symbol+' · '+new Date(state.selected.start).toLocaleString('pt-BR');
  ['labCard','researchCard','trajectoryCard','transitionCard'].forEach(id=>$(id).classList.remove('hidden'));renderDetail();
}

function renderDetail(){
  const d=state.detail;if(!d)return;const dna=d.dna;
  const items=[['Range',dna.range_ticks+' ticks'],['Eficiência',pct(dna.directional_efficiency)],['Reversões',dna.reversals],['Revisitas',dna.total_revisits],['VWAP',n(dna.vwap)],['Trades/s',n(dna.trades_per_second,2)]];
  $('dnaKpis').innerHTML=items.map(v=>'<div class="kpi"><span>'+v[0]+'</span><strong>'+v[1]+'</strong></div>').join('');
  draw($('pathCanvas'),d.timeline,state.replay);draw($('counterCanvas'),d.counterfactual.prices);
  $('volumeLevels').innerHTML=d.volume_by_price.slice(0,40).map(x=>'<div class="level"><span>'+n(x.price)+'</span><strong>'+n(x.volume,0)+' · Δ '+n(x.delta,0)+'</strong></div>').join('');
  const shown=d.timeline.slice(0,state.replay);
  $('tradeBody').innerHTML=shown.slice(-250).map(t=>'<tr><td>'+(t.index+1)+'</td><td>'+clock(t.ts)+'</td><td>'+n(t.price)+'</td><td>'+t.quantity+'</td><td>'+t.aggressor+'</td><td>'+esc(t.buyer_id||'—')+'</td><td>'+esc(t.seller_id||'—')+'</td></tr>').join('');
  $('replayState').textContent=state.replay+'/'+d.timeline.length+' negócios';
}
function play(){clearInterval(state.timer);state.replay=0;state.timer=setInterval(()=>{state.replay=Math.min(state.replay+1,state.detail.timeline.length);renderDetail();if(state.replay>=state.detail.timeline.length)clearInterval(state.timer)},35)}
function matchHtml(rows){return (rows||[]).map(x=>'<div class="match"><span>'+new Date(x.feature.start).toLocaleString('pt-BR')+'<br><small>'+x.feature.session_regime+' · '+x.feature.volatility_bucket+'</small></span><strong>'+n(x.score,1)+'%</strong></div>').join('')||'<p>Sem candidatos.</p>'}
async function research(){if(!state.selected)return;const p=new URLSearchParams({symbol:$('symbolSelect').value,start:state.selected.start,interval_seconds:$('intervalSelect').value,same_time:$('sameTime').checked,same_volatility:$('sameVol').checked,same_context_regime:$('sameContext').checked,other_sessions_only:$('otherSessions').checked,quality_only:'true'});const r=await api('/api/research/search?'+p);$('visualMatches').innerHTML=matchHtml(r.visual_matches);$('dnaMatches').innerHTML=matchHtml(r.dna_matches)}
function familyLabel(x){return ({DIRECT_IMPULSE_UP:'Impulso direto de alta',DIRECT_IMPULSE_DOWN:'Impulso direto de baixa',SWEEP_LOW_REVERSAL:'Varredura da mínima → reversão',SWEEP_HIGH_REVERSAL:'Varredura da máxima → reversão',PULLBACK_CONTINUATION_UP:'Pullback → continuação de alta',PULLBACK_CONTINUATION_DOWN:'Pullback → continuação de baixa',V_SHAPED:'V-shaped',INVERTED_V:'V invertido',DOUBLE_EXCURSION:'Dupla excursão',OSCILLATING_RANGE:'Oscilação / range',UNCLASSIFIED:'Sem classificação',FLAT:'Flat'})[x]||x}
async function trajectory(){const p=new URLSearchParams({symbol:$('symbolSelect').value,interval_seconds:$('intervalSelect').value,clusters:$('clusterSelect').value,sample_points:$('pointsSelect').value,quality_only:'true'});const r=await api('/api/trajectory/families?'+p);$('ruleFamilies').innerHTML=r.rule_families.map(x=>'<div class="family"><span>'+familyLabel(x.family)+'</span><strong>'+x.count+' · '+pct(x.share)+'</strong></div>').join('');$('clusters').innerHTML=r.clusters.map(x=>'<div class="cluster"><span>'+esc(x.label)+'<br><small>'+familyLabel(x.dominant_rule)+'</small></span><strong>'+x.size+'</strong></div>').join('')}
async function transitions(){const p=new URLSearchParams({symbol:$('symbolSelect').value,interval_seconds:$('intervalSelect').value,clusters:$('clusterSelect').value,sample_points:$('pointsSelect').value,quality_only:'true'});if(state.selected)p.set('target_start',state.selected.start);const r=await api('/api/trajectory/transitions?'+p);$('stability').innerHTML=r.stability.map(x=>'<div class="transition"><span>'+familyLabel(x.family)+'<br><small>'+x.stability_label+' · '+x.sessions+' pregões</small></span><strong>'+n(x.stability_score,1)+'</strong></div>').join('');$('transitions').innerHTML=r.family_transitions.slice(0,12).map(x=>'<div class="transition"><span>'+familyLabel(x.from)+' → '+familyLabel(x.to)+'</span><strong>'+x.count+' · '+pct(x.probability)+'</strong></div>').join('');$('motifs').innerHTML=r.family_motifs.slice(0,8).map(x=>'<div class="transition"><span>'+x.sequence.map(familyLabel).join(' → ')+'</span><strong>'+x.count+'</strong></div>').join('');const s=r.selected_sequence;if(s&&s.current){const cell=(name,x)=>'<div><small>'+name+'</small><strong>'+(x?familyLabel(x.rule_family):'—')+'</strong></div>';$('sequenceBox').innerHTML=cell('Anterior',s.previous)+cell('Atual',s.current)+cell('Próximo',s.next)}else $('sequenceBox').innerHTML=''}

$('dayCanvas').addEventListener('mousedown',e=>{if(!state.overviewCandles.length)return;state.dragStart=dayIndexFromEvent(e);state.dragCurrent=state.dragStart;drawDayChart()});
$('dayCanvas').addEventListener('mousemove',e=>{if(state.dragStart==null||e.buttons!==1)return;state.dragCurrent=dayIndexFromEvent(e);drawDayChart()});
$('dayCanvas').addEventListener('mouseup',e=>{if(state.dragStart==null)return;state.dragCurrent=dayIndexFromEvent(e);finalizeSelection()});
$('dayCanvas').addEventListener('mouseleave',e=>{if(state.dragStart!=null&&e.buttons===1){state.dragCurrent=dayIndexFromEvent(e);finalizeSelection()}});
$('clearSelectionBtn').onclick=()=>{state.dragStart=null;state.dragCurrent=null;state.selection=null;state.indexLocation=null;$('selectionInfo').classList.add('hidden');$('locateBtn').disabled=true;$('sliceBtn').disabled=true;$('lineMapWrap').classList.add('hidden');$('indexResult').textContent='Selecione primeiro um intervalo no gráfico.';$('sliceResult').textContent='Prepare primeiro o índice temporal.';drawDayChart()};

function selectedCandleStarts(){
  if(!state.selection)return[];
  return state.overviewCandles
    .slice(state.selection.startIndex,state.selection.endIndex+1)
    .map(c=>c.start);
}

function renderLineMap(payload){
  const rows=payload.candles||[];
  $('lineMapBody').innerHTML=rows.map(x=>{
    if(x.status!=='FOUND')return '<tr><td>'+shortClock(x.start)+'</td><td colspan="5">Sem negócios no índice</td></tr>';
    return '<tr><td>'+shortClock(x.start)+'–'+shortClock(x.end)+'</td>'+
      '<td>'+n(x.source_row_min,0)+'–'+n(x.source_row_max,0)+'</td>'+
      '<td>'+n(x.chronological_open_row,0)+'</td>'+
      '<td>'+n(x.chronological_close_row,0)+'</td>'+
      '<td>'+n(x.trades,0)+'</td>'+
      '<td>'+n(x.byte_start,0)+'–'+n(x.byte_end,0)+'</td></tr>';
  }).join('');
  $('lineMapWrap').classList.toggle('hidden',rows.length===0);
}

$('locateBtn').onclick=async()=>{
  if(!state.selection||!state.overviewMeta)return;
  const path=$('localTradesPath').value.trim();
  if(!path){$('indexResult').textContent='Cole primeiro o caminho do CSV grande de Trades.';return}
  $('locateBtn').disabled=true;$('sliceBtn').disabled=true;
  $('indexResult').textContent='Preparando o índice temporal. Na primeira vez o arquivo inteiro é lido uma única vez; nas próximas seleções o índice será reutilizado…';
  try{
    const payload={
      source_path:path,symbol:state.overviewMeta.symbol,start:state.selection.start,end:state.selection.end,
      interval_seconds:state.overviewMeta.interval_seconds,candle_starts:selectedCandleStarts()
    };
    const r=await api('/api/time-index/locate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    state.indexLocation=r;
    renderLineMap(r);
    const mode=r.index_built_now?'Índice criado agora':'Índice existente reutilizado';
    $('indexResult').textContent=
      mode+'.\n'+
      'Arquivo: '+n(r.index.rows,0)+' linhas · '+r.index.minutes_indexed+' minutos indexados.\n'+
      'Seleção: linhas '+n(r.selection.source_row_min,0)+'–'+n(r.selection.source_row_max,0)+
      ' · '+n(r.selection.trades,0)+' negócios · '+n(r.selection.byte_length,0)+' bytes.\n'+
      'Abertura cronológica na linha '+n(r.selection.chronological_open_row,0)+
      '; fechamento cronológico na linha '+n(r.selection.chronological_close_row,0)+'.';
    $('sliceBtn').disabled=false;
    $('sliceResult').textContent='Linhas localizadas. Clique em “Recortar e importar intervalo localizado”.';
  }catch(err){
    state.indexLocation=null;$('lineMapWrap').classList.add('hidden');
    $('indexResult').textContent='Erro: '+err.message;
  }finally{$('locateBtn').disabled=false}
};

$('sliceBtn').onclick=async()=>{
  if(!state.selection||!state.overviewMeta||!state.indexLocation)return;
  const path=$('localTradesPath').value.trim();
  if(!path){$('sliceResult').textContent='Cole primeiro o caminho do CSV grande de Trades.';return}
  $('sliceBtn').disabled=true;$('sliceResult').textContent='Saltando para os bytes localizados e extraindo somente o intervalo selecionado…';
  try{
    const payload={
      source_path:path,symbol:state.overviewMeta.symbol,start:state.selection.start,end:state.selection.end,
      tick_size:Number($('sliceTickInput').value),interval_seconds:state.overviewMeta.interval_seconds,
      candle_starts:selectedCandleStarts()
    };
    const r=await api('/api/slice-import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('sliceResult').textContent='Recorte concluído por acesso indexado.\n\n'+JSON.stringify(r,null,2);
    await refresh();
    if([...$('symbolSelect').options].some(o=>o.value===payload.symbol)){$('symbolSelect').value=payload.symbol;await loadSessions()}
    const date=state.overviewMeta.session_date;
    if([...$('sessionSelect').options].some(o=>o.value===date)){$('sessionSelect').value=date;$('intervalSelect').value=String(state.overviewMeta.interval_seconds);await loadCandles()}
  }catch(err){$('sliceResult').textContent='Erro: '+err.message}
  finally{$('sliceBtn').disabled=false}
};

$('sampleBtn').onclick=async()=>{try{$('sampleBtn').disabled=true;await api('/api/load-sample',{method:'POST'});await Promise.all([refresh(),refreshOverview('WINLAB06')])}catch(e){alert(e.message)}finally{$('sampleBtn').disabled=false}};
$('overviewSymbolSelect').onchange=loadOverviewSessions;$('overviewSessionSelect').onchange=loadOverviewCandles;$('overviewRefreshBtn').onclick=loadOverviewCandles;
$('refreshBtn').onclick=refresh;$('symbolSelect').onchange=loadSessions;$('sessionSelect').onchange=loadCandles;$('intervalSelect').onchange=loadCandles;
$('playBtn').onclick=play;$('stepBtn').onclick=()=>{state.replay=Math.min(state.replay+1,state.detail.timeline.length);renderDetail()};$('resetBtn').onclick=()=>{clearInterval(state.timer);state.replay=0;renderDetail()};
$('researchBtn').onclick=research;$('trajectoryBtn').onclick=trajectory;$('transitionBtn').onclick=transitions;

$('importForm').onsubmit=async e=>{
  e.preventDefault();const fd=new FormData();fd.append('file',$('tradeFile').files[0]);fd.append('symbol',$('symbolInput').value);fd.append('tick_size',$('tickInput').value);fd.append('source',$('sourceInput').value);
  try{const r=await api('/api/import-csv',{method:'POST',body:fd});$('importResult').textContent=JSON.stringify(r,null,2);await refresh()}catch(err){$('importResult').textContent='Erro: '+err.message}
};

$('referenceForm').onsubmit=async e=>{
  e.preventDefault();const fd=new FormData();fd.append('file',$('referenceFile').files[0]);fd.append('symbol',$('referenceSymbolInput').value);fd.append('tick_size',$('referenceTickInput').value);fd.append('interval_seconds',$('referenceIntervalInput').value);fd.append('source','profit_ohlc_reference');
  try{
    const r=await api('/api/import-reference',{method:'POST',body:fd});
    $('referenceResult').textContent='Gráfico diário importado.\n\n'+JSON.stringify(r,null,2);
    $('sliceTickInput').value=$('referenceTickInput').value;
    await Promise.all([refresh(),refreshOverview(r.symbol)]);
  }catch(err){$('referenceResult').textContent='Erro: '+err.message}
};

Promise.all([refresh(),refreshOverview()]).catch(e=>{$('statusBadge').textContent='erro';console.error(e)});
