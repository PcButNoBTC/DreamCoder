import asyncio
from provider_runtime import ProviderRuntime

def test_retry_runtime():
    r=ProviderRuntime(); n={"x":0}
    async def f():
        n["x"]+=1
        if n["x"]<2: raise RuntimeError("temporary")
        return "ok"
    assert asyncio.run(r.call("test",f,retries=2))=="ok"
    assert r.snapshot()["test"]["successes"]==1
