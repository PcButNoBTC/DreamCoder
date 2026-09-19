import asyncio
from provider_runtime import ProviderRuntime

def test_concurrent_provider_calls():
    rt=ProviderRuntime()
    async def one(i):
        async def f(): return i
        return await rt.call("test",f,retries=0,timeout=2)
    async def run_all():
        return await asyncio.gather(*[one(i) for i in range(20)])
    out=asyncio.run(run_all())
    assert sorted(out)==list(range(20))
