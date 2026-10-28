"""Ponto de entrada do .exe (PyInstaller)."""
import multiprocessing
import sys

from crlocal.tools import dispatch_tool, ensure_std_streams

if __name__ == "__main__":
    multiprocessing.freeze_support()
    code = dispatch_tool(sys.argv)
    if code is not None:
        sys.exit(code)
    if len(sys.argv) > 1 and sys.argv[1] not in ("--gui",):
        from crlocal.__main__ import main as cli

        ensure_std_streams()

        sys.exit(cli(sys.argv[1:]))
    from crlocal.gui import main as gui

    gui()
