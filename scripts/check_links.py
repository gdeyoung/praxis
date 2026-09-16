#!/usr/bin/env python3
"""Check relative markdown links in a repo. Exit 1 on broken links.

Usage: python3 scripts/check_links.py [repo_root]   (default: cwd)
Skips .git. Reports path -> target for every broken .md relative link.
Run BEFORE every push; moves/restructures routinely break one directory level.
"""
import re, os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
bad = []
for dirpath, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d != ".git"]
    for f in files:
        if not f.endswith(".md"):
            continue
        p = os.path.join(dirpath, f)
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"\]\(([^)#\s]+?\.md)\)", text):
            target = os.path.normpath(os.path.join(dirpath, m.group(1)))
            if not os.path.exists(target):
                bad.append(f"{p} -> {m.group(1)}")

if bad:
    print("BROKEN LINKS:")
    for b in bad:
        print(" ", b)
    sys.exit(1)
print("OK: no broken relative markdown links")
