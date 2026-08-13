import sys
import asyncio
import uvicorn

if sys.platform == "win32":
    # 1. Set policy for the current process (the Uvicorn parent reloader process)
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 2. Monkey-patch Uvicorn so worker processes don't revert to SelectorEventLoop
    # Uvicorn's default auto/asyncio loop setups hardcode WindowsSelectorEventLoopPolicy,
    # which has a limit of 512 connections on Windows and causes crashes under load.
    try:
        import uvicorn.loops.asyncio
        import uvicorn.loops.auto
        
        def _proactor_setup(*args, **kwargs):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        uvicorn.loops.asyncio.asyncio_setup = _proactor_setup
        uvicorn.loops.auto.auto_loop_setup = _proactor_setup
    except ImportError:
        pass

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
