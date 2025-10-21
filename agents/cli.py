#!/usr/bin/env python3
import argparse
import asyncio
import importlib
import inspect
import sys


def run_module_main(mod_name: str):
    mod = importlib.import_module(mod_name)
    if hasattr(mod, "main"):
        fn = getattr(mod, "main")
        if inspect.iscoroutinefunction(fn):
            return asyncio.run(fn())
        return fn()
    raise SystemExit(f"Module {mod_name} has no main() function")


def run_agent_entry(mod_name: str, func_name: str):
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name)
    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn())
    return fn()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pc28-agents", description="Run PC28 agents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run a module's main()")
    p_run.add_argument("module", help="Python module path, e.g. agent_exec")

    p_call = sub.add_parser("call", help="Call a specific function in a module")
    p_call.add_argument("module", help="Module path, e.g. agent_exec")
    p_call.add_argument("func", help="Function name to call, e.g. main or execute_*()")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return run_module_main(args.module)
    if args.cmd == "call":
        return run_agent_entry(args.module, args.func)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
