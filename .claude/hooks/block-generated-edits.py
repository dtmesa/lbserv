#!/usr/bin/env python3
"""PreToolUse hook: block direct edits to generated API code and the exported OpenAPI contract."""

import json
import re
import sys

PROTECTED = re.compile(r"(^|/)(frontend/src/api/generated/|openapi/openapi\.json$)")

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input") or {}
path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

if PROTECTED.search(path):
    print(
        f"Blocked: {path} is generated. Change backend/app/schemas.py (or routes) and run "
        "`make openapi gen` instead of editing generated files. See CLAUDE.md.",
        file=sys.stderr,
    )
    sys.exit(2)
