"""Production provider policy: retries, rate limits, tracing, capabilities and cost accounting."""
from __future__ import annotations
import asyncio,time,uuid,os
from dataclasses import dataclass
from typing import Any,Awaitable,Callable
import db
from security import redact
@dataclass
class ProviderStats:
    requests:int=0; successes:int=0; failures:int=0; total_ms:int=0; tokens:int=0; cost:float=0.0
    @property
    def success_rate(self): return self.successes/self.requests if self.requests else 0.0
    @property
    def avg_latency_ms(self): return self.total_ms/self.requests if self.requests else 0.0
class ProviderRuntime:
    def __init__(self):
        self.stats={}; self.capabilities={}; self.locks={}; self.last_call={}
    def register(self,provider,capabilities=None): self.capabilities[provider]=capabilities or {"chat","code","json"}
    def record_usage(self,provider,input_tokens=0,output_tokens=0,cost_usd=None):
        s=self.stats.setdefault(provider,ProviderStats()); total=input_tokens+output_tokens; s.tokens+=total
        s.cost+=float(cost_usd) if cost_usd is not None else total/1000*float(os.getenv("DREAMCODER_COST_PER_1K_TOKENS","0"))
    def rank(self,providers=None):
        names=providers or list(self.stats)
        return sorted(names,key=lambda p:(self.stats.get(p,ProviderStats()).success_rate*0.65)+(1/(1+self.stats.get(p,ProviderStats()).avg_latency_ms))*0.35,reverse=True)
    def snapshot(self):
        return {k:{"requests":v.requests,"successes":v.successes,"failures":v.failures,"success_rate":v.success_rate,"avg_latency_ms":v.avg_latency_ms,"tokens":v.tokens,"cost_usd":v.cost} for k,v in self.stats.items()}
    async def call(self,provider,fn,retries=2,timeout=120.0):
        s=self.stats.setdefault(provider,ProviderStats()); s.requests+=1; trace=uuid.uuid4().hex; started=time.perf_counter(); last=None
        sem=self.locks.setdefault(provider,asyncio.Semaphore(max(1,int(os.getenv("DREAMCODER_PROVIDER_CONCURRENCY","4")))))
        async with sem:
            for attempt in range(retries+1):
                interval=float(os.getenv("DREAMCODER_PROVIDER_MIN_INTERVAL","0"))
                wait=interval-(time.monotonic()-self.last_call.get(provider,0))
                if wait>0: await asyncio.sleep(wait)
                self.last_call[provider]=time.monotonic()
                try:
                    result=await asyncio.wait_for(fn(),timeout)
                    elapsed=int((time.perf_counter()-started)*1000); s.successes+=1; s.total_ms+=elapsed
                    db.add_history("provider",provider,trace,redact(str(result)[:2000]),elapsed); return result
                except Exception as exc:
                    last=exc
                    if attempt<retries: await asyncio.sleep(min(2**attempt,8))
        s.failures+=1; s.total_ms+=int((time.perf_counter()-started)*1000)
        raise last if last else RuntimeError("provider failed")
runtime=ProviderRuntime()
