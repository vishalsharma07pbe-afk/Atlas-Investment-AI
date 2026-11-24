#!/usr/bin/env python3
"""Conservative source-level API route compatibility gate.

Compare existing controller mapping declarations and Python route decorators to a
reviewed baseline. No endpoint discovery network calls, secrets or mutation.
Moving a route to another file requires explicit compatibility review.
"""
import argparse
import ast
import collections
import pathlib
import re
import subprocess
import sys

BASELINE = "059c9e01add361d5f0047bd4c3944d6e2ea8ded3"
JAVA_PREFIX = "backend/trading-core/src/main/java/"
PY_PREFIX = "intelligence/app/"
MAPPING = re.compile(r"@(RequestMapping|GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping)\b(?:\s*\(((?:[^()\"']|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\([^()]*\))*)\))?", re.S)

def git(*args):
    return subprocess.check_output(["git", *args], text=True)

def java_routes(source):
    # Keep literal paths and request conditions; normalize whitespace outside strings.
    def normalize(value):
        return "".join(token for token in re.findall(r'"(?:\\.|[^"\\])*"|\S', value or ""))
    return collections.Counter((m.group(1), normalize(m.group(2))) for m in MAPPING.finditer(source))

def python_routes(source):
    result = collections.Counter()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator,ast.Call) or not isinstance(decorator.func,ast.Attribute):
                continue
            if decorator.func.attr not in {"get","post","put","patch","delete","head","options","api_route","websocket"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0],ast.Constant) or not isinstance(decorator.args[0].value,str):
                continue
            path=decorator.args[0].value
            if not path.startswith("/"):
                continue
            methods=next((ast.dump(k.value,include_attributes=False) for k in decorator.keywords if k.arg=="methods"),"")
            result[(decorator.func.attr,path,methods)]+=1
    return result

def routes(path,source):
    if path.startswith(JAVA_PREFIX) and path.endswith(".java"):
        return java_routes(source)
    if path.startswith(PY_PREFIX) and path.endswith(".py"):
        return python_routes(source)
    return collections.Counter()

def compare(baseline):
    removed=[]
    count=0
    for path in git("ls-tree","-r","--name-only",baseline).splitlines():
        if not (path.startswith(JAVA_PREFIX) and path.endswith(".java") or path.startswith(PY_PREFIX) and path.endswith(".py")):
            continue
        before=routes(path,git("show",baseline+":"+path))
        if not before:
            continue
        count+=sum(before.values())
        current=pathlib.Path(path)
        after=routes(path,current.read_text(encoding="utf-8")) if current.is_file() else collections.Counter()
        for route,n in (before-after).items():
            removed.append((path,route,n))
    if count==0:
        raise RuntimeError("No baseline routes discovered")
    for path,route,n in removed:
        print(f"REMOVED OR CHANGED: {path} {route} ({n})",file=sys.stderr)
    print(f"Reviewed {count} baseline mapping declarations; {len(removed)} incompatible changes.")
    return 1 if removed else 0

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",default=BASELINE)
    sys.exit(compare(parser.parse_args().baseline))
