from __future__ import annotations
import asyncio,os,signal,uuid,subprocess
SESSIONS={}
class Session:
    def __init__(self,command,cwd):
        self.id=uuid.uuid4().hex; self.command=command; self.cwd=cwd; self.proc=None; self.master=None
    async def start(self):
        if os.name!="nt":
            import pty
            self.master,self.slave=pty.openpty()
            self.proc=await asyncio.create_subprocess_shell(self.command,cwd=self.cwd,stdin=self.slave,stdout=self.slave,stderr=self.slave,preexec_fn=os.setsid)
            os.close(self.slave); asyncio.create_task(self._read_pty())
        else:
            try:
                import winpty
                self.winpty=winpty.PtyProcess.spawn(self.command,cwd=self.cwd)
                self.pid=self.winpty.pid
                asyncio.create_task(self._read_winpty())
            except ImportError:
                flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
                self.proc=await asyncio.create_subprocess_shell(self.command,cwd=self.cwd,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,creationflags=flags)
                asyncio.create_task(self._read_pipe())
        return self
    async def _read_pty(self):
        loop=asyncio.get_running_loop()
        while self.proc and self.proc.returncode is None:
            try:data=await loop.run_in_executor(None,os.read,self.master,4096)
            except Exception:break
            if data: await self.queue.put(data.decode(errors="replace"))
            else:break
    async def _read_winpty(self):
        loop=asyncio.get_running_loop()
        while getattr(self,"winpty",None) and self.winpty.isalive():
            try:
                data=await loop.run_in_executor(None,self.winpty.read,4096)
                if data: await self.queue.put(data)
            except Exception: break
    async def _read_pipe(self):
        while self.proc:
            data=await self.proc.stdout.read(4096)
            if not data:break
            await self.queue.put(data.decode(errors="replace"))
    async def write(self,data):
        if os.name!="nt":
            if not self.proc:return
            os.write(self.master,data.encode()); return
        if getattr(self,"winpty",None):
            self.winpty.write(data); return
        if not self.proc:return
        if self.proc.stdin:self.proc.stdin.write(data.encode()); await self.proc.stdin.drain()

    async def resize(self,cols,rows):
        if os.name!="nt" and self.master:
            import fcntl,termios,struct
            fcntl.ioctl(self.master,termios.TIOCSWINSZ,struct.pack("HHHH",rows,cols,0,0))
        elif getattr(self,"winpty",None):
            try:self.winpty.setwinsize(cols,rows)
            except Exception:pass

    async def stop(self):
        if os.name=="nt" and getattr(self,"winpty",None):
            self.winpty.terminate(); return
        if not self.proc:return
        try:
            if os.name!="nt":os.killpg(os.getpgid(self.proc.pid),signal.SIGTERM)
            else:self.proc.terminate()
        except ProcessLookupError:pass
    async def kill(self):
        if os.name=="nt" and getattr(self,"winpty",None):
            self.winpty.terminate(force=True); return
        if self.proc:
            try:self.proc.kill()
            except Exception:pass
async def create(command,cwd):
    s=Session(command,cwd); s.queue=asyncio.Queue(); await s.start(); SESSIONS[s.id]=s; return s
