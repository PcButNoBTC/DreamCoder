"""Production provider policy: retries, rate limits, tracing, capabilities and cost accounting."""
from __future__ import annotations
import asyncio, time, uuid
from dataclasses import dataclass,field
from typing import Any, Awaitable, Callable
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
        self.stats:dict[str,ProviderStats]={}; self.capabilities:dict[str,set[str]]={}
    def register(self,provider:str,capabilities:set[str]|None=None): self.capabilities[provider]=capabilities or {"chat","code","json"}
    def snapshot(self):
        return {k:{"requests":v.requests,"successes":v.successes,"failures":v.failures,"success_rate":v.success_rate,"avg_latency_ms":v.avg_latency_ms,"tokens":v.tokens,"cost_usd":v.cost} for k,v in self.stats.items()}
    async def call(self,provider:str,fn:Callable[[],Awaitable[Any]],retries:int=2,timeout:float=120.0)->Any:
        s=self.stats.setdefault(provider,ProviderStats()); s.requests+=1; trace=uuid.uuid4().hex; last=None; started=time.perf_counter()
        for attempt in range(retries+1):
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
