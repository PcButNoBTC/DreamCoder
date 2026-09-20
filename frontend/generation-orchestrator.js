(function () {
  const API = () => (window.DREAMCODER_API || 'http://127.0.0.1:8000').replace(/\/$/, '');
  function esc(v) { const d=document.createElement('div'); d.textContent=String(v ?? ''); return d.innerHTML; }
  function ensureCard() {
    const host=document.getElementById('generateCard'); if(!host || document.getElementById('generationPipeline')) return;
    const card=document.createElement('div'); card.id='generationPipeline'; card.className='dc-gen-pipeline';
    card.innerHTML='<div class="card-head"><span>◈ Generation Pipeline</span><span class="badge" id="genPipelineBadge">IDLE</span></div>'
      +'<div id="genPipelineModels" class="dc-gen-models"></div>'
      +'<div id="genPipelineTasks" class="dc-gen-tasks"></div>'
      +'<div id="genPipelineReview" class="muted"></div>';
    host.appendChild(card);
  }
  function render(data) {
    ensureCard();
    const badge=document.getElementById('genPipelineBadge');
    const models=document.getElementById('genPipelineModels');
    const tasks=document.getElementById('genPipelineTasks');
    const review=document.getElementById('genPipelineReview');
    if(!badge || !models || !tasks) return;
    badge.textContent=(data && data.source==='orchestrator') ? 'MULTI-MODEL' : 'FALLBACK';
    const m=data?.models || {};
    models.innerHTML=Object.keys(m).map(k=>'<span class="dc-gen-model"><b>'+esc(k)+'</b> → '+esc(m[k])+'</span>').join('');
    const plan=data?.plan || {}; const taskList=plan.tasks || [];
    tasks.innerHTML=taskList.map(t=>'<div class="dc-gen-task"><span class="dc-gen-dot">●</span><div><b>'+esc(t.id || t.role || 'task')+'</b><div>'+esc(t.description || '')+'</div></div></div>').join('');
    const r=data?.review; review.innerHTML=r ? '<b>Review:</b> '+esc(r.summary || '')+' · '+((r.issues||[]).length)+' issue(s)' : '';
  }
  function decorateExistingResult() {
    if(window.lastGenerated) render(window.lastGenerated);
  }
  const style=document.createElement('style');
  style.textContent='.dc-gen-pipeline{margin-top:8px;padding:8px;border:1px solid var(--border);border-radius:8px;background:var(--panel)}.dc-gen-models{display:flex;gap:5px;flex-wrap:wrap;margin:6px 0}.dc-gen-model{padding:4px 6px;border:1px solid var(--border);border-radius:5px;font-size:10px}.dc-gen-tasks{display:grid;gap:4px}.dc-gen-task{display:flex;gap:6px;padding:5px;border:1px solid var(--border);border-radius:5px;font-size:10px}.dc-gen-dot{color:var(--accent2)}';
  document.head.appendChild(style);
  ensureCard();
  const originalFetch=window.fetch;
  window.fetch=function(input, init){
    return originalFetch.apply(this, arguments).then(function(response){
      const url=typeof input==='string' ? input : (input && input.url) || '';
      if(url.indexOf('/api/ai/generate-project') !== -1 && !(url.indexOf('/zip')!==-1 || url.indexOf('/build')!==-1)){
        response.clone().json().then(render).catch(function(){});
      }
      return response;
    });
  };
})();