const $=id=>document.getElementById(id);
const state={
  symbols:[],sessions:[],candles:[],detail:null,replay:0,timer:null,selected:null,
  overview:[],overviewSessions:[],overviewCandles:[],overviewMeta:null,
  dragStart:null,dragCurrent:null,dragMode:null,selection:null,indexLocation:null,
  zoom:1,viewStart:0
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
const isoTime=iso=>String(iso||'').slice(11,16);

function draw(canvas,values,count){
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
  const arr=values.slice(0,count==null?values.length:Math.max(1,count));if(!arr.length)return;
  const nums=arr.map(v=>typeof v==='number'?v:v.price),lo=Math.min(...nums),hi=Math.max(...nums),span=hi-lo||1;
  ctx.strokeStyle='#5db5ff';ctx.lineWidth=2;ctx.beginPath();
  nums.forEach((v,i)=>{const x=18+(w-36)*(i/Math.max(nums.length-1,1)),y=h-18-(h-36)*((v-lo)/span);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)});ctx.stroke();
}

function chartGeometry(){
  const canvas=$('dayCanvas');
  return {canvas,left:72,right:24,top:34,bottom:62,w:canvas.width,h:canvas.height};
}

function visibleWindow(){
  const total=state.overviewCandles.length;
  if(!total)return {start:0,end:0,count:0,total:0};
  const zoom=Math.max(1,Math.min(30,Number(state.zoom)||1));
  const count=Math.min(total,Math.max(10,Math.ceil(total/zoom)));
  const maxStart=Math.max(0,total-count);
  state.viewStart=Math.max(0,Math.min(maxStart,Math.round(state.viewStart||0)));
  return {start:state.viewStart,end:Math.min(total,state.viewStart+count),count,total};
}

function xForBoundary(globalBoundary,windowInfo=null){
  const win=windowInfo||visibleWindow(),g=chartGeometry();
  if(!win.count)return g.left;
  const plotW=g.w-g.left-g.right;
  return g.left+plotW*((globalBoundary-win.start)/win.count);
}

function markerBoundaryFromEvent(e){
  const g=chartGeometry(),rect=g.canvas.getBoundingClientRect(),win=visibleWindow();
  if(!win.count)return 0;
  const x=(e.clientX-rect.left)*(g.canvas.width/rect.width);
  const plotW=g.w-g.left-g.right;
  const local=Math.round((x-g.left)/(plotW/win.count));
  return Math.max(win.start,Math.min(win.end,win.start+local));
}

function dayIndexFromEvent(e){
  const g=chartGeometry(),rect=g.canvas.getBoundingClientRect(),win=visibleWindow();
  if(!win.count)return 0;
  const x=(e.clientX-rect.left)*(g.canvas.width/rect.width);
  const plotW=g.w-g.left-g.right;
  const local=Math.floor((x-g.left)/(plotW/win.count));
  return Math.max(win.start,Math.min(win.end-1,win.start+local));
}

function invalidateLocatedSlice(){
  state.indexLocation=null;
  $('sliceBtn').disabled=true;
  $('lineMapWrap').classList.add('hidden');
  $('indexProgressWrap').classList.add('hidden');
  $('indexProgressBar').style.width='0%';
  $('sliceProgressWrap').classList.add('hidden');
  $('sliceProgressBar').style.width='0%';
  $('sliceResult').textContent='Prepare primeiro o índice temporal para esta seleção.';
}

function updateSelectionUI(){
  if(!state.selection){
    $('selectionInfo').classList.add('hidden');
    $('startTimeInput').value='';
    $('endTimeInput').value='';
    $('zoomSelectionBtn').disabled=true;
    $('locateBtn').disabled=true;
    return;
  }
  const first=state.overviewCandles[state.selection.startIndex];
  const last=state.overviewCandles[state.selection.endIndex];
  state.selection.start=first.start;
  state.selection.end=last.end;
  state.selection.count=state.selection.endIndex-state.selection.startIndex+1;
  $('selectionLabel').textContent=clock(first.start)+' → '+clock(last.end);
  $('selectionCount').textContent=String(state.selection.count);
  $('startTimeInput').value=isoTime(first.start);
  $('endTimeInput').value=isoTime(last.end);
  $('selectionInfo').classList.remove('hidden');
  $('zoomSelectionBtn').disabled=false;
  $('locateBtn').disabled=false;
}

function setSelectionIndices(startIndex,endIndex,{invalidate=true,keepOrder=false}={}){
  const total=state.overviewCandles.length;
  if(!total)return;
  let a=Math.max(0,Math.min(total-1,Math.round(startIndex)));
  let b=Math.max(0,Math.min(total-1,Math.round(endIndex)));
  if(!keepOrder&&a>b)[a,b]=[b,a];
  if(keepOrder&&a>b)return;
  state.selection={startIndex:a,endIndex:b,start:null,end:null,count:b-a+1};
  state.dragStart=a;state.dragCurrent=b;
  if(invalidate)invalidateLocatedSlice();
  $('timeSelectionError').classList.add('hidden');
  updateSelectionUI();
  drawDayChart();
}

function clearSelection(){
  state.dragStart=null;state.dragCurrent=null;state.dragMode=null;state.selection=null;state.indexLocation=null;
  $('selectionInfo').classList.add('hidden');$('locateBtn').disabled=true;$('sliceBtn').disabled=true;
  $('zoomSelectionBtn').disabled=true;$('lineMapWrap').classList.add('hidden');
  $('startTimeInput').value='';$('endTimeInput').value='';
  $('timeSelectionError').classList.add('hidden');
  $('indexResult').textContent='Selecione primeiro um intervalo no gráfico.';
  $('sliceResult').textContent='Prepare primeiro o índice temporal.';
  drawDayChart();
}

function updateZoomStatus(){
  const win=visibleWindow();
  if(!win.count){$('zoomStatus').textContent='Sem dados';return}
  const first=state.overviewCandles[win.start],last=state.overviewCandles[win.end-1];
  $('zoomStatus').textContent=(state.zoom===1?'Dia inteiro':'Zoom '+state.zoom+'×')+
    ' · '+win.count+' candles visíveis · '+isoTime(first.start)+'–'+isoTime(last.end);
}

function setZoom(value,centerIndex=null){
  const total=state.overviewCandles.length;if(!total)return;
  const old=visibleWindow();
  const center=centerIndex==null?(old.start+(old.count-1)/2):centerIndex;
  state.zoom=Math.max(1,Math.min(30,Math.round(Number(value)||1)));
  $('zoomRange').value=String(state.zoom);
  const count=Math.min(total,Math.max(10,Math.ceil(total/state.zoom)));
  state.viewStart=Math.round(center-count/2);
  visibleWindow();
  updateZoomStatus();drawDayChart();
}

function panChart(direction){
  const win=visibleWindow();if(!win.count)return;
  state.viewStart+=Math.round(win.count*.45)*direction;
  visibleWindow();updateZoomStatus();drawDayChart();
}

function zoomToSelection(){
  if(!state.selection)return;
  const total=state.overviewCandles.length;
  const selected=state.selection.count;
  const targetVisible=Math.max(10,Math.ceil(selected*1.8));
  const wanted=Math.max(1,Math.min(30,Math.floor(total/targetVisible)||1));
  const center=(state.selection.startIndex+state.selection.endIndex)/2;
  setZoom(wanted,center);
}

function ensureSelectionVisible(){
  if(!state.selection)return;
  let win=visibleWindow();
  if(state.selection.count>win.count){
    const total=state.overviewCandles.length;
    const wanted=Math.max(1,Math.floor(total/Math.ceil(state.selection.count*1.35)));
    state.zoom=Math.max(1,Math.min(30,wanted));
    $('zoomRange').value=String(state.zoom);
    win=visibleWindow();
  }
  if(state.selection.startIndex<win.start||state.selection.endIndex>=win.end){
    state.viewStart=Math.round((state.selection.startIndex+state.selection.endIndex-win.count+1)/2);
    visibleWindow();
  }
  updateZoomStatus();
}

function drawMarker(ctx,x,top,bottom,label,time,color,alignRight=false){
  ctx.save();
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;
  ctx.beginPath();ctx.moveTo(x,top-6);ctx.lineTo(x,bottom);ctx.stroke();
  ctx.beginPath();ctx.arc(x,top-10,7,0,Math.PI*2);ctx.fill();
  ctx.font='bold 11px Segoe UI';
  const text=label+' '+time,tw=ctx.measureText(text).width,pad=6;
  let bx=alignRight?x-tw-pad*2-8:x+8;
  bx=Math.max(2,Math.min(ctx.canvas.width-tw-pad*2-2,bx));
  ctx.fillRect(bx,top-28,tw+pad*2,20);
  ctx.fillStyle='#071019';ctx.fillText(text,bx+pad,top-14);
  ctx.restore();
}

function drawDayChart(){
  const g=chartGeometry(),ctx=g.canvas.getContext('2d'),win=visibleWindow();
  ctx.clearRect(0,0,g.w,g.h);
  if(!win.count){updateZoomStatus();return}
  const candles=state.overviewCandles.slice(win.start,win.end);
  const plotW=g.w-g.left-g.right,plotH=g.h-g.top-g.bottom;
  const lo=Math.min(...candles.map(c=>c.low)),hi=Math.max(...candles.map(c=>c.high)),span=hi-lo||1;
  const y=p=>g.top+plotH-(p-lo)/span*plotH;
  const step=plotW/win.count;
  const bodyW=Math.max(1,Math.min(10,step*.62));

  ctx.strokeStyle='#183048';ctx.lineWidth=1;ctx.fillStyle='#8298ad';ctx.font='11px Segoe UI';
  for(let i=0;i<=5;i++){
    const yy=g.top+plotH*i/5,price=hi-span*i/5;
    ctx.beginPath();ctx.moveTo(g.left,yy);ctx.lineTo(g.w-g.right,yy);ctx.stroke();
    ctx.fillText(n(price,2),4,yy+4);
  }

  const maxLabels=Math.max(8,Math.floor(plotW/54));
  const labelEvery=Math.max(1,Math.ceil(win.count/maxLabels));
  candles.forEach((c,local)=>{
    const global=win.start+local,x=g.left+step*(local+.5);
    if(local%labelEvery===0){
      ctx.strokeStyle='#10283a';ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(x,g.top);ctx.lineTo(x,g.top+plotH);ctx.stroke();
      ctx.fillStyle='#8298ad';ctx.font='11px Segoe UI';
      ctx.fillText(isoTime(c.start),Math.max(g.left,x-16),g.h-18);
      ctx.beginPath();ctx.moveTo(x,g.top+plotH);ctx.lineTo(x,g.top+plotH+5);ctx.stroke();
    }
    const up=c.close>=c.open;
    ctx.strokeStyle=up?'#63d7ae':'#f47f8d';ctx.fillStyle=ctx.strokeStyle;
    ctx.beginPath();ctx.moveTo(x,y(c.high));ctx.lineTo(x,y(c.low));ctx.stroke();
    const yo=y(c.open),yc=y(c.close),bh=Math.max(1,Math.abs(yc-yo));
    ctx.fillRect(x-bodyW/2,Math.min(yo,yc),bodyW,bh);
  });

  if(state.selection){
    const selStart=Math.max(state.selection.startIndex,win.start);
    const selEnd=Math.min(state.selection.endIndex+1,win.end);
    if(selStart<selEnd){
      const x1=xForBoundary(selStart,win),x2=xForBoundary(selEnd,win);
      ctx.fillStyle='rgba(93,181,255,.13)';ctx.fillRect(x1,g.top,x2-x1,plotH);
      ctx.strokeStyle='#5db5ff';ctx.lineWidth=1;ctx.strokeRect(x1,g.top,x2-x1,plotH);
    }
    const first=state.overviewCandles[state.selection.startIndex];
    const last=state.overviewCandles[state.selection.endIndex];
    if(state.selection.startIndex>=win.start&&state.selection.startIndex<=win.end){
      drawMarker(ctx,xForBoundary(state.selection.startIndex,win),g.top,g.top+plotH,'INÍCIO',isoTime(first.start),'#5db5ff',false);
    }
    const endBoundary=state.selection.endIndex+1;
    if(endBoundary>=win.start&&endBoundary<=win.end){
      drawMarker(ctx,xForBoundary(endBoundary,win),g.top,g.top+plotH,'FIM',isoTime(last.end),'#f0b966',true);
    }
  }else if(state.dragStart!=null){
    const a=Math.min(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
    const b=Math.max(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent)+1;
    const x1=xForBoundary(Math.max(a,win.start),win),x2=xForBoundary(Math.min(b,win.end),win);
    ctx.fillStyle='rgba(93,181,255,.13)';ctx.fillRect(x1,g.top,Math.max(0,x2-x1),plotH);
  }
  updateZoomStatus();
}

function markerHitFromEvent(e){
  if(!state.selection)return null;
  const g=chartGeometry(),rect=g.canvas.getBoundingClientRect(),win=visibleWindow();
  const x=(e.clientX-rect.left)*(g.canvas.width/rect.width);
  const threshold=14;
  const sx=xForBoundary(state.selection.startIndex,win);
  const ex=xForBoundary(state.selection.endIndex+1,win);
  if(state.selection.startIndex>=win.start&&state.selection.startIndex<=win.end&&Math.abs(x-sx)<=threshold)return 'start';
  if(state.selection.endIndex+1>=win.start&&state.selection.endIndex+1<=win.end&&Math.abs(x-ex)<=threshold)return 'end';
  return null;
}

function finalizeSelection(){
  if(state.dragStart==null||!state.overviewCandles.length)return;
  const a=Math.min(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
  const b=Math.max(state.dragStart,state.dragCurrent==null?state.dragStart:state.dragCurrent);
  setSelectionIndices(a,b);
  state.dragMode=null;
}

function applyTimeSelection(){
  const startValue=$('startTimeInput').value,endValue=$('endTimeInput').value;
  const error=$('timeSelectionError');
  if(!startValue||!endValue){error.textContent='Informe os horários de início e fim.';error.classList.remove('hidden');return}
  const startIndex=state.overviewCandles.findIndex(c=>isoTime(c.start)===startValue);
  const endIndex=state.overviewCandles.findIndex(c=>isoTime(c.end)===endValue);
  if(startIndex<0||endIndex<0){
    error.textContent='Os horários precisam coincidir com as fronteiras dos candles exibidos neste timeframe.';
    error.classList.remove('hidden');return;
  }
  if(endIndex<startIndex){
    error.textContent='O horário final precisa ser posterior ao horário inicial.';
    error.classList.remove('hidden');return;
  }
  setSelectionIndices(startIndex,endIndex);
  ensureSelectionVisible();drawDayChart();
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
  state.dragStart=null;state.dragCurrent=null;state.dragMode=null;state.selection=null;state.indexLocation=null;
  state.zoom=1;state.viewStart=0;$('zoomRange').value='1';
  $('selectionInfo').classList.add('hidden');$('locateBtn').disabled=true;$('sliceBtn').disabled=true;$('zoomSelectionBtn').disabled=true;$('lineMapWrap').classList.add('hidden');
  $('startTimeInput').value='';$('endTimeInput').value='';$('timeSelectionError').classList.add('hidden');
  $('overviewEmpty').classList.toggle('hidden',state.overviewCandles.length>0);
  if(state.overviewMeta&&state.overviewMeta.tick_size)$('sliceTickInput').value=state.overviewMeta.tick_size;
  updateZoomStatus();drawDayChart();
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

function aggressionIntensityLabel(x){
  return ({SEM_AGRESSAO_DIRECIONADA:'Sem direção',BAIXA:'Baixa',MODERADA:'Moderada',ALTA:'Alta',EXTREMA:'Extrema'})[x]||x;
}
function aggressionResponseLabel(x){
  return ({IMPULSO_COMPATIVEL:'Impulso compatível',POSSIVEL_ABSORCAO:'Possível absorção',PRESSAO_SEM_CONFIRMACAO:'Pressão sem confirmação',DISPUTA_OU_INDEFINIDA:'Disputa / indefinida',SEM_JANELA_POS_AGRESSAO:'Sem janela pós-agressão'})[x]||x;
}
function topAgentText(rows){
  if(!rows||!rows.length)return '—';
  const x=rows[0];
  return esc(x.agent)+' · '+n(x.quantity,0)+' ('+pct(x.share)+')';
}
function agentRankingHtml(rows){
  return (rows||[]).map((x,i)=>'<div class="agent-row"><span><b>#'+(i+1)+'</b> '+esc(x.agent)+'<br><small>'+n(x.trades,0)+' negócio(s)</small></span><strong>'+n(x.quantity,0)+' · '+pct(x.share)+'</strong></div>').join('')||'<p class="muted">Sem agente identificável neste lado.</p>';
}
function renderAggression(d){
  const a=d.aggression;if(!a)return;
  const sm=a.summary;
  const items=[
    ['Compra agressora',n(sm.buy_aggression,0)],
    ['Venda agressora',n(sm.sell_aggression,0)],
    ['Delta',n(sm.delta,0)],
    ['Cobertura agressor',pct(sm.aggressor_coverage)],
    ['Identidade agente',pct(sm.agent_identity_coverage)],
    ['Direção',sm.direction],
    ['RLP',n(sm.rlp_volume,0)]
  ];
  $('aggressionKpis').innerHTML=items.map(v=>'<div class="kpi"><span>'+v[0]+'</span><strong>'+v[1]+'</strong></div>').join('');
  $('topBuyAggressors').innerHTML=agentRankingHtml(a.top_buy_aggressors);
  $('topSellAggressors').innerHTML=agentRankingHtml(a.top_sell_aggressors);
  $('aggressionBody').innerHTML=(a.levels||[]).map(x=>{
    const dom=x.dominance==null?'—':pct(x.dominance);
    return '<tr class="aggr-'+String(x.intensity||'').toLowerCase()+'">'+
      '<td><strong>'+n(x.price)+'</strong><br><small>'+n(x.volume,0)+' total</small></td>'+
      '<td>'+n(x.buy_aggression,0)+'</td>'+
      '<td>'+n(x.sell_aggression,0)+'</td>'+
      '<td class="'+(x.delta>0?'delta-buy':x.delta<0?'delta-sell':'')+'">'+n(x.delta,0)+'</td>'+
      '<td><span class="intensity intensity-'+String(x.intensity||'').toLowerCase()+'">'+aggressionIntensityLabel(x.intensity)+'</span><br><small>'+pct(x.share_of_candle_directed_aggression)+' do candle</small></td>'+
      '<td>'+dom+'</td>'+
      '<td>'+topAgentText(x.top_buy_aggressors)+'</td>'+
      '<td>'+topAgentText(x.top_sell_aggressors)+'</td>'+
      '<td>'+aggressionResponseLabel(x.response)+'<br><small>'+n(x.visits,0)+' visita(s) · favorável '+n(x.favorable_excursion_ticks_after_level,0)+' tick(s)</small></td>'+
    '</tr>';
  }).join('');
  $('aggressionMethod').textContent=a.method+' '+a.intensity_method+' '+a.limitations;
}

function waveTypeLabel(x){
  return ({EXAUSTAO:'Exaustão',NEUTRALIZACAO:'Neutralização',TROCA_CONTROLE:'Troca de controle'})[x]||x;
}
function waveOutcomeLabel(x){
  return ({REVERSAO_COMPATIVEL:'Reversão compatível',CONTINUACAO:'Continuação',ESTAGNACAO_OU_DISPUTA:'Estagnação / disputa',SEM_JANELA_POSTERIOR:'Sem janela posterior'})[x]||x;
}
function drawWaveTerminationMarkers(canvas,d){
  const waves=d.aggression_waves;if(!waves||!waves.termination_events||!waves.termination_events.length)return;
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
  const total=Math.max(d.timeline.length-1,1);
  const visibleEvents=waves.termination_events.filter(e=>e.end_index<state.replay);
  visibleEvents.forEach((e,i)=>{
    const x=18+(w-36)*(e.end_index/total);
    ctx.save();
    ctx.setLineDash([5,4]);
    ctx.lineWidth=2;
    ctx.strokeStyle=e.side==='BUY'?'#f0b966':'#c995ff';
    ctx.beginPath();ctx.moveTo(x,12);ctx.lineTo(x,h-12);ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle=e.side==='BUY'?'#f0b966':'#c995ff';
    ctx.font='bold 11px Segoe UI';
    ctx.fillText('T'+(i+1),Math.min(w-28,x+4),18);
    ctx.restore();
  });
}
function renderAggressionWaves(d){
  const w=d.aggression_waves;if(!w)return;
  const detected=(w.termination_events||[]).filter(e=>e.end_index<state.replay);
  const completeReplay=state.replay>=d.timeline.length;
  const sm=w.summary||{};
  const items=[
    ['Términos',n(detected.length,0)],
    ['Exaustão',n(detected.filter(e=>e.termination_type==='EXAUSTAO').length,0)],
    ['Neutralização',n(detected.filter(e=>e.termination_type==='NEUTRALIZACAO').length,0)],
    ['Troca de controle',n(detected.filter(e=>e.termination_type==='TROCA_CONTROLE').length,0)]
  ];
  $('waveSummary').innerHTML=items.map(v=>'<div class="kpi"><span>'+v[0]+'</span><strong>'+v[1]+'</strong></div>').join('');

  $('waveBody').innerHTML=detected.map((e,i)=>{
    const agent=e.top_aggressors&&e.top_aggressors.length
      ? esc(e.top_aggressors[0].agent)+' · '+n(e.top_aggressors[0].quantity,0)
      : '—';
    const post=completeReplay
      ? waveOutcomeLabel(e.post_event.outcome)+'<br><small>reversão máx. '+n(e.post_event.max_reversal_ticks,0)+' ticks · continuação máx. '+n(e.post_event.max_continuation_ticks,0)+' ticks</small>'
      : '<span class="expost-hidden">Disponível ao final do replay</span>';
    return '<tr>'+
      '<td>'+clock(e.start_ts)+'<br><small>#'+n(e.start_trade_number,0)+'</small></td>'+
      '<td><strong>'+e.side+'</strong></td>'+
      '<td>'+clock(e.end_ts)+'<br><small>#'+n(e.end_trade_number,0)+' · T'+(i+1)+'</small></td>'+
      '<td>'+waveTypeLabel(e.termination_type)+'</td>'+
      '<td>'+pct(e.pressure_decay)+'<br><small>pico '+n(e.peak_side_window_qty,0)+' → '+n(e.end_window_side_qty,0)+'</small></td>'+
      '<td>'+n(e.end_price)+'</td>'+
      '<td>'+agent+'</td>'+
      '<td>'+post+'</td>'+
    '</tr>';
  }).join('')||'<tr><td colspan="8">Nenhum término de onda confirmado até este ponto do replay.</td></tr>';

  if(completeReplay&&w.open_episode){
    $('openWaveBox').classList.remove('hidden');
    const o=w.open_episode,agent=o.top_aggressors&&o.top_aggressors.length?o.top_aggressors[0].agent:'—';
    $('openWaveBox').textContent='O candle terminou com uma onda '+o.side+' ainda aberta. Início '+clock(o.start_ts)+' · principal agressor '+agent+'.';
  }else{
    $('openWaveBox').classList.add('hidden');
    $('openWaveBox').textContent='';
  }
  $('waveMethod').textContent=w.method+' '+w.limitations+' Janela: '+w.parameters.window_trades+' negócios; a reação posterior é EX-POST e não participa da detecção.';
}

function renderDetail(){
  const d=state.detail;if(!d)return;const dna=d.dna;
  const items=[['Range',dna.range_ticks+' ticks'],['Eficiência',pct(dna.directional_efficiency)],['Reversões',dna.reversals],['Revisitas',dna.total_revisits],['VWAP',n(dna.vwap)],['Trades/s',n(dna.trades_per_second,2)]];
  $('dnaKpis').innerHTML=items.map(v=>'<div class="kpi"><span>'+v[0]+'</span><strong>'+v[1]+'</strong></div>').join('');
  draw($('pathCanvas'),d.timeline,state.replay);drawWaveTerminationMarkers($('pathCanvas'),d);draw($('counterCanvas'),d.counterfactual.prices);
  $('volumeLevels').innerHTML=d.volume_by_price.slice(0,40).map(x=>'<div class="level"><span>'+n(x.price)+'</span><strong>'+n(x.volume,0)+' · Δ '+n(x.delta,0)+'</strong></div>').join('');
  renderAggression(d);
  renderAggressionWaves(d);
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

$('dayCanvas').addEventListener('mousedown',e=>{
  if(!state.overviewCandles.length)return;
  const hit=markerHitFromEvent(e);
  if(hit){state.dragMode=hit;return}
  state.dragMode='new';state.selection=null;invalidateLocatedSlice();
  state.dragStart=dayIndexFromEvent(e);state.dragCurrent=state.dragStart;updateSelectionUI();drawDayChart();
});
$('dayCanvas').addEventListener('mousemove',e=>{
  if(!state.dragMode||e.buttons!==1){
    $('dayCanvas').style.cursor=markerHitFromEvent(e)?'ew-resize':'crosshair';
    return;
  }
  $('dayCanvas').style.cursor=state.dragMode==='new'?'crosshair':'ew-resize';
  if(state.dragMode==='new'){
    state.dragCurrent=dayIndexFromEvent(e);drawDayChart();return;
  }
  const boundary=markerBoundaryFromEvent(e);
  if(state.dragMode==='start'&&state.selection){
    const newStart=Math.min(state.selection.endIndex,Math.max(0,boundary));
    setSelectionIndices(newStart,state.selection.endIndex,{keepOrder:true});
  }else if(state.dragMode==='end'&&state.selection){
    const endBoundary=Math.max(state.selection.startIndex+1,boundary);
    setSelectionIndices(state.selection.startIndex,endBoundary-1,{keepOrder:true});
  }
});
$('dayCanvas').addEventListener('mouseup',e=>{
  if(state.dragMode==='new')finalizeSelection();
  state.dragMode=null;
  $('dayCanvas').style.cursor=markerHitFromEvent(e)?'ew-resize':'crosshair';
});
$('dayCanvas').addEventListener('mouseleave',e=>{
  if(state.dragMode==='new'&&e.buttons===1)finalizeSelection();
  state.dragMode=null;
});
$('dayCanvas').addEventListener('wheel',e=>{
  if(!e.ctrlKey)return;
  e.preventDefault();
  const center=dayIndexFromEvent(e);
  setZoom(state.zoom+(e.deltaY<0?1:-1),center);
},{passive:false});

$('clearSelectionBtn').onclick=clearSelection;
$('applyTimeSelectionBtn').onclick=applyTimeSelection;
$('startTimeInput').addEventListener('change',()=>{if($('endTimeInput').value)applyTimeSelection()});
$('endTimeInput').addEventListener('change',()=>{if($('startTimeInput').value)applyTimeSelection()});
$('zoomRange').addEventListener('input',e=>setZoom(Number(e.target.value)));
$('zoomInBtn').onclick=()=>setZoom(state.zoom+1);
$('zoomOutBtn').onclick=()=>setZoom(state.zoom-1);
$('panLeftBtn').onclick=()=>panChart(-1);
$('panRightBtn').onclick=()=>panChart(1);
$('resetZoomBtn').onclick=()=>{state.zoom=1;state.viewStart=0;$('zoomRange').value='1';updateZoomStatus();drawDayChart()};
$('zoomSelectionBtn').onclick=zoomToSelection;

function formatBytes(value){
  let bytes=Number(value||0);
  if(!Number.isFinite(bytes)||bytes<=0)return '0 B';
  const units=['B','KB','MB','GB','TB'];
  let i=0;
  while(bytes>=1024&&i<units.length-1){bytes/=1024;i++}
  return bytes.toLocaleString('pt-BR',{maximumFractionDigits:i===0?0:1})+' '+units[i];
}

function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms))}

function showIndexProgress(progress={},status='running'){
  const wrap=$('indexProgressWrap');
  wrap.classList.remove('hidden');
  const pct=Math.max(0,Math.min(100,Number(progress.percent||0)));
  $('indexProgressPct').textContent=pct.toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
  $('indexProgressBar').style.width=pct+'%';
  const rows=Number(progress.rows||0),done=Number(progress.bytes_processed||0),total=Number(progress.bytes_total||0);
  const minutes=Number(progress.minutes_indexed||0);
  if(status==='queued'){
    $('indexProgressText').textContent='Preparando a leitura do arquivo…';
  }else if(total>0){
    $('indexProgressText').textContent=
      n(rows,0)+' linhas · '+formatBytes(done)+' de '+formatBytes(total)+' · '+n(minutes,0)+' minutos indexados';
  }else{
    $('indexProgressText').textContent='Lendo o arquivo… '+n(rows,0)+' linhas processadas';
  }
}

async function runIndexJob(payload){
  const started=await api('/api/time-index/start',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
  });
  while(true){
    const job=await api('/api/time-index/jobs/'+encodeURIComponent(started.job_id));
    showIndexProgress(job.progress||{},job.status);
    if(job.status==='completed')return job.result;
    if(job.status==='failed')throw new Error(job.error||'Falha durante a indexação.');
    await sleep(450);
  }
}

function showSliceProgress(progress={},status='running'){
  $('sliceProgressWrap').classList.remove('hidden');
  const pct=Math.max(0,Math.min(100,Number(progress.percent||0)));
  $('sliceProgressPct').textContent=pct.toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
  $('sliceProgressBar').style.width=pct+'%';

  const phase=progress.phase||status;
  const message=progress.message||'Processando o recorte…';
  const done=Number(progress.bytes_processed||0),total=Number(progress.bytes_total||0);
  const matched=Number(progress.matched_rows||progress.trades||0);

  let detail=message;
  if(phase==='extract'&&total>0){
    detail+=' · '+formatBytes(done)+' de '+formatBytes(total);
    if(matched)detail+=' · '+n(matched,0)+' negócios';
  }else if(phase==='store'&&progress.trades){
    detail+=' · '+n(progress.trades,0)+' negócios';
  }else if(phase==='catalog'&&progress.inserted!=null){
    detail+=' · '+n(progress.inserted,0)+' inseridos';
    if(progress.duplicates)detail+=' · '+n(progress.duplicates,0)+' já existentes';
  }
  $('sliceProgressText').textContent=detail;
}

async function runSliceJob(payload){
  const started=await api('/api/slice-import/start',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
  });
  while(true){
    const job=await api('/api/slice-import/jobs/'+encodeURIComponent(started.job_id));
    showSliceProgress(job.progress||{},job.status);
    if(job.status==='completed')return job.result;
    if(job.status==='failed')throw new Error(job.error||'Falha durante o recorte/importação.');
    await sleep(350);
  }
}

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
  $('lineMapWrap').classList.add('hidden');
  showIndexProgress({percent:0,rows:0,bytes_processed:0,bytes_total:0,minutes_indexed:0},'queued');
  $('indexResult').textContent='Preparando o índice temporal. O progresso da leitura aparece acima.';
  try{
    const payload={
      source_path:path,symbol:state.overviewMeta.symbol,start:state.selection.start,end:state.selection.end,
      interval_seconds:state.overviewMeta.interval_seconds,candle_starts:selectedCandleStarts()
    };
    const r=await runIndexJob(payload);
    state.indexLocation=r;
    renderLineMap(r);
    const mode=r.index_built_now?'Índice criado agora':'Índice existente reutilizado';
    showIndexProgress({
      percent:100,rows:r.index.rows,bytes_processed:r.index.source_size,bytes_total:r.index.source_size,
      minutes_indexed:r.index.minutes_indexed
    },'completed');
    $('indexProgressText').textContent=r.index_built_now
      ? 'Leitura concluída · '+n(r.index.rows,0)+' linhas · '+formatBytes(r.index.source_size)
      : 'Índice reutilizado · nenhuma nova leitura integral foi necessária.';
    $('indexResult').textContent=
      mode+'.\n'+
      'Layout: '+(r.index.layout_profile||'—')+'.\n'+
      'Arquivo: '+n(r.index.rows,0)+' linhas · '+r.index.minutes_indexed+' minutos indexados · '+formatBytes(r.index.source_size)+'.\n'+
      'Seleção: linhas '+n(r.selection.source_row_min,0)+'–'+n(r.selection.source_row_max,0)+
      ' · '+n(r.selection.trades,0)+' negócios · '+formatBytes(r.selection.byte_length)+'.\n'+
      'Abertura cronológica na linha '+n(r.selection.chronological_open_row,0)+
      '; fechamento cronológico na linha '+n(r.selection.chronological_close_row,0)+'.';
    $('sliceBtn').disabled=false;
    $('sliceResult').textContent='Linhas localizadas. Clique em “Recortar e importar intervalo localizado”.';
  }catch(err){
    state.indexLocation=null;$('lineMapWrap').classList.add('hidden');
    $('indexProgressWrap').classList.add('hidden');
    $('indexResult').textContent='Erro: '+err.message;
  }finally{$('locateBtn').disabled=false}
};

$('sliceBtn').onclick=async()=>{
  if(!state.selection||!state.overviewMeta||!state.indexLocation)return;
  const path=$('localTradesPath').value.trim();
  if(!path){$('sliceResult').textContent='Cole primeiro o caminho do CSV grande de Trades.';return}
  $('sliceBtn').disabled=true;
  showSliceProgress({percent:0,phase:'queued',message:'Preparando a tarefa de recorte.'},'queued');
  $('sliceResult').textContent='Recortando e importando o intervalo. O progresso aparece acima.';
  try{
    const payload={
      source_path:path,symbol:state.overviewMeta.symbol,start:state.selection.start,end:state.selection.end,
      tick_size:Number($('sliceTickInput').value),interval_seconds:state.overviewMeta.interval_seconds,
      candle_starts:selectedCandleStarts()
    };
    const r=await runSliceJob(payload);
    showSliceProgress({
      percent:100,phase:'completed',
      message:'Recorte criado, validado e importado com sucesso.',
      inserted:r.import&&r.import.inserted,duplicates:r.import&&r.import.duplicates
    },'completed');
    $('sliceResult').textContent='Recorte concluído por acesso indexado.\n\n'+JSON.stringify(r,null,2);
    await refresh();
    if([...$('symbolSelect').options].some(o=>o.value===payload.symbol)){$('symbolSelect').value=payload.symbol;await loadSessions()}
    const date=state.overviewMeta.session_date;
    if([...$('sessionSelect').options].some(o=>o.value===date)){$('sessionSelect').value=date;$('intervalSelect').value=String(state.overviewMeta.interval_seconds);await loadCandles()}
  }catch(err){
    $('sliceProgressWrap').classList.add('hidden');
    $('sliceResult').textContent='Erro: '+err.message;
  }finally{$('sliceBtn').disabled=false}
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
