import asyncio
from provider_runtime import ProviderRuntime

def test_concurrent_provider_calls():
    rt=ProviderRuntime()
    async def one(i):
        async def f(): return i
        return await rt.call("test",f,retries=0,timeout=2)
    out=asyncio.run(asyncio.gather(*[one(i) for i in range(20)]))
    assert sorted(out)==list(range(20))
