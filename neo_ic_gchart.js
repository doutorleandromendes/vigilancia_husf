// ═══════════════════════════════════════════════════════════════════════════
// Peças novas para o indicadores.html — barra de erro (IC95%) + g-chart na Neo.
// Aplicar numa CÓPIA e testar (React/Recharts não roda fora do navegador).
// ═══════════════════════════════════════════════════════════════════════════

// ── 1. Helper: IC95% de Poisson (aprox. de Byar) → [lo, hi] em /1000 cat-dia ──
// Colar logo após o fechamento do SAHE_TXT (a linha `};` ~linha 90).
function poisIC(n, cd){
  if(cd==null || cd<=0) return null;
  var z=1.96;
  var lo = n<=0 ? 0 : n*Math.pow(1 - 1/(9*n)     - z/(3*Math.sqrt(n)),     3);
  var hi = (n+1) *Math.pow(1 - 1/(9*(n+1)) + z/(3*Math.sqrt(n+1)), 3);
  return [Math.max(lo,0)/cd*1000, hi/cd*1000];
}

// Reconstrói a sequência de eventos (posição em cat-dia acumulado) e os
// intervalos entre IPCS consecutivas, a partir da série ipcs [{p,v,n,cd}].
function gchartSerie(serie){
  var ev=[], cum=0;
  serie.forEach(function(pt){
    var n=pt.n||0, cd=pt.cd||0;
    for(var k=0;k<n;k++) ev.push({x:cum + cd*(k+0.5)/n, p:pt.p});
    cum += cd;
  });
  var out=[];
  for(var i=0;i<ev.length;i++){
    out.push({ i:i+1,
      gap: i===0 ? Math.round(ev[0].x) : Math.round(ev[i].x - ev[i-1].x),
      p: ev[i].p });
  }
  return out;
}
// Limite inferior = intervalo esperado se a taxa DOBRAR, ancorado no P50 do SAHE
// (a mesma referência do resto do dashboard). p50 em /1000 cat-dia.
function gchartLCL(p50){
  if(!p50||p50<=0) return null;
  return Math.round(1000/(2*p50));
}
// Marca como cluster os eventos em runs de >=3 intervalos consecutivos abaixo do limite.
function marcarClusters(gs, lcl){
  if(lcl==null) return gs;
  var below=gs.map(function(d){return d.gap<lcl;}), i=0;
  while(i<below.length){
    if(below[i]){ var j=i; while(j<below.length&&below[j]) j++;
      if(j-i>=3) for(var k=i;k<j;k++) gs[k].cluster=true; i=j; }
    else i++;
  }
  return gs;
}

// ── 2. Componente do g-chart (novo) ──────────────────────────────────────────
// Colar junto dos outros componentes (ex.: logo após BarS).
function GChart(props){
  var serie=props.serie||[];              // ipcs [{p,v,n,cd}]
  var gs=gchartSerie(serie);
  var lcl=gchartLCL(props.p50);           // props.p50 = SAHE.utiNeo.ipcs.p50
  gs=marcarClusters(gs, lcl);
  var maxY=Math.max.apply(null, gs.map(function(d){return d.gap;}).concat([lcl?lcl*3:60]));
  var infoRef=useState(false), open=infoRef[0], setOpen=infoRef[1];
  if(!gs.length) return null;
  return h('div',{style:{background:WHITE,border:'1px solid '+BRDR,borderRadius:8,
      padding:'14px 14px 8px',boxShadow:'0 1px 3px rgba(0,0,0,0.06)',position:'relative'}},
    h('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}},
      h('span',{style:{fontFamily:"'IBM Plex Sans',sans-serif",fontSize:11,fontWeight:600,
        color:NAVY,maxWidth:'80%',lineHeight:1.35}},
        'g-chart — cateter-dia entre IPCS consecutivas',
        h('span',{className:'info-dot',role:'button',tabIndex:0,
          onClick:function(e){e.stopPropagation();setOpen(!open);},'aria-label':'Saiba mais'},'ⓘ')),
      h('span',{style:{fontSize:7,color:'#9eaab8',fontFamily:"'IBM Plex Mono',monospace"}},
        'evento = cada IPCS')),
    open?h('div',{className:'sahe-pop open',style:{maxWidth:300}},
      h('div',{className:'sp-body'},SAHE_TXT.gchart.b),
      h('div',{className:'sp-tip'},SAHE_TXT.gchart.t)):null,
    h(RCont,{width:'100%',height:props.h||200},
      h(LineChart,{data:gs,margin:{top:12,right:14,left:-8,bottom:4}},
        h(CartGrid,{strokeDasharray:'3 3',stroke:GRID,vertical:false}),
        h(XAxis,{dataKey:'i',tick:{fill:LIGHT,fontSize:8,fontFamily:"'IBM Plex Mono',monospace"},
          axisLine:false,tickLine:false}),
        h(YAxis,{domain:[0,Math.ceil(maxY*1.1)],tick:{fill:LIGHT,fontSize:8,
          fontFamily:"'IBM Plex Mono',monospace"},axisLine:false,tickLine:false}),
        h(RCTip,{content:function(o){
          if(!o||!o.active||!o.payload||!o.payload.length) return null;
          var d=o.payload[0].payload;
          return h('div',{style:{background:'#fff',border:'1px solid '+BRDR,borderRadius:6,
            padding:'6px 9px',fontFamily:"'IBM Plex Mono',monospace",fontSize:9,color:NAVY}},
            'IPCS #'+d.i+' ('+d.p+')',h('br'),'intervalo: '+d.gap+' cat-dia');
        }}),
        lcl!=null?h(RefLine,{y:lcl,stroke:'#c62828',strokeDasharray:'5 3',strokeWidth:1.1,
          label:{value:'limite inferior',position:'insideBottomRight',fill:'#c62828',fontSize:7}}):null,
        h(Line,{type:'linear',dataKey:'gap',stroke:HIST,strokeWidth:1.5,
          dot:function(o){var cl=o.payload.cluster;
            return h('circle',{cx:o.cx,cy:o.cy,r:cl?5:4,fill:cl?'#c62828':BLUE,key:o.payload.i});},
          activeDot:{r:5}})
      )));
}

// ── 3. Textos do (i) — adicionar dentro do SAHE_TXT (chaves novas) ───────────
// ic:{
//   b:'A faixa vertical é o intervalo de 95% de confiança do indicador e funciona, em linhas gerais, como margem de erro. Com poucos casos e denominador pequeno (o que é comum na Neo), a faixa fica larga, mostrando que a taxa absoluta é imprecisa e oscila muito só por acaso.',
//   t:'Se as faixas de dois meses se sobrepõem, não há diferença estatística entre eles.'
// },
// gchart:{
//   b:'Em vez de taxa por mês, mostra quanto tempo (em cateter-dia) passa entre uma infecção e a próxima. Queremos que esse número seja grande (ou seja, que muito tempo se passe sem nenhuma infecção).',
//   t:'Quedas sucessivas abaixo da linha vermelha indicam infecções acontecendo mais próximas umas das outras do que o esperado.'
// }

// ── 4. Barra de erro no BarS (integração) ────────────────────────────────────
// (a) No destructuring do Recharts (~linha 98), acrescentar ErrorBar:
//     var RefLine=RC.ReferenceLine,...,Legend=RC.Legend, ErrorBar=RC.ErrorBar;
// (b) No topo do BarS, derivar os dados com o IC quando props.ic:
//     var dd=data;
//     if(props.ic){ dd=data.map(function(d){
//       if(d.n!=null&&d.cd!=null){ var c=poisIC(d.n,d.cd);
//         if(c) return Object.assign({},d,{_ic:[Math.max(d.v-c[0],0),Math.max(c[1]-d.v,0)]}); }
//       return d; }); }
//     → e trocar `data:data` por `data:dd` no ComposedChart, e o `data.map(Cell)` por `dd.map(...)`.
// (c) Dentro do h(Bar,{...}, dd.map(Cell...)), acrescentar como último filho:
//     props.ic?h(ErrorBar,{dataKey:'_ic',width:5,strokeWidth:1.3,stroke:'#455a64',opacity:.85}):null

// ── 5. Ligar na Neo ──────────────────────────────────────────────────────────
// (a) SEC_DEFAULT.utiNeo, no chart 'ipcs', acrescentar ic:true (e subir maxY p/ caber o IC):
//     {id:'ipcs',...,src:'ipcs',maxY:120,h:220,sahe:'ipcs',ic:true}
// (b) No renderGrids, na chamada do BarS, repassar ic:
//     h(BarS,{title:c.title,data:ud[c.src],...,refLbl:c.refLbl, ic:c.ic})
// (c) Na UtiNeoSection, após renderGrids(...), renderizar o g-chart:
//     h(GChart,{serie:neo.ipcs||[], p50:(SAHE&&SAHE.utiNeo&&SAHE.utiNeo.ipcs)?SAHE.utiNeo.ipcs.p50:null}),
