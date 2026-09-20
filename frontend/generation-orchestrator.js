(function () {
  function esc(v){const d=document.createElement('div');d.textContent=String(v??'');return d.innerHTML;}
  function ensure(){
    const host=document.getElementById('generateCard'); if(!host||document.getElementById('generationPipeline'))return;
    const card=document.createElement('div');card.id='generationPipeline';card.className='dc-gen-pipeline';
    card.innerHTML='<div class="card-head"><span>◈ Generation Pipeline</span><span class="badge" id="genPipelineBadge">IDLE</span></div>'+
      '<div id="genPipelineStages" class="dc-gen-stages"></div><div id="genPipelineModels" class="dc-gen-models"></div>'+
      '<div id="genPipelineTasks" class="dc-gen-tasks"></div><div id="genPipelineValidation" class="muted"></div><div id="genPipelineReview" class="muted"></div>';
    host.appendChild(card);
  }
  function render(data){
    ensure(); const b=document.getElementById('genPipelineBadge');if(!b)return;
    const multi=data?.source==='orchestrator'; b.textContent=multi?'TASK GRAPH':'FALLBACK'; b.className='badge '+(multi?'ok':'');
    const stages=document.getElementById('genPipelineStages');
    const pipeline=data?.pipeline||[];
    stages.innerHTML=pipeline.map((x,i)=>'<span class="dc-stage"><i>'+((i+1))+'</i>'+esc(x)+'</span>').join('');
    const m=data?.models||{}; document.getElementById('genPipelineModels').innerHTML=Object.entries(m).flatMap(([k,v])=>{
      if(v&&typeof v==='object')return Object.entries(v).map(([a,z])=>'<span class="dc-gen-model"><b>'+esc(a)+'</b> → '+esc(z)+'</span>');
      return '<span class="dc-gen-model"><b>'+esc(k)+'</b> → '+esc(v)+'</span>';
    }).join('');
    const tasks=data?.tasks||data?.plan?.tasks||[];
    document.getElementById('genPipelineTasks').innerHTML=tasks.map(t=>'<div class="dc-gen-task"><span>●</span><div><b>'+esc(t.task_id||t.id||t.role||'task')+'</b> · '+esc(t.model||t.role||'')+'<div>'+esc(t.description||'')+'</div></div></div>').join('');
    const v=data?.validation||{}; document.getElementById('genPipelineValidation').innerHTML='<b>Validation:</b> '+(v.ok?'✓ passed':v.skipped?'↷ skipped':'✗ failed')+(v.command?' · '+esc(v.command):'')+(v.stderr?' · '+esc(v.stderr.slice(-300)):'');
    const r=data?.review;document.getElementById('genPipelineReview').innerHTML=r?'<b>Review:</b> '+esc(r.summary||'')+' · '+((r.issues||[]).length)+' issue(s)':'';
  }
  const style=document.createElement('style');style.textContent='.dc-gen-pipeline{margin-top:8px;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--panel)}.dc-gen-stages{display:flex;gap:4px;flex-wrap:wrap}.dc-stage{padding:4px 6px;border:1px solid var(--border);border-radius:5px;font-size:10px}.dc-stage i{font-style:normal;margin-right:4px}.dc-gen-models{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0}.dc-gen-model{padding:4px 6px;border:1px solid var(--border);border-radius:5px;font-size:10px}.dc-gen-tasks{display:grid;gap:4px}.dc-gen-task{display:flex;gap:6px;padding:5px;border:1px solid var(--border);border-radius:5px;font-size:10px}.dc-gen-task>span{color:var(--accent2)}';document.head.appendChild(style);
  ensure();
  const fetch0=window.fetch;
  window.fetch=function(input,init){return fetch0.apply(this,arguments).then(r=>{const u=typeof input==='string'?input:(input&&input.url)||'';if(u.includes('/api/ai/generate-project')&&!u.includes('/zip')&&!u.includes('/build'))r.clone().json().then(render).catch(()=>{});return r;});};
  window.addEventListener('dreamcoder:generation',e=>render(e.detail||{}));
})();