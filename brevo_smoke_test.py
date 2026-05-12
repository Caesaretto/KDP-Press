#!/usr/bin/env python3
"""Brevo dry-run smoke test.

Verifies BREVO_API_KEY auth and BREVO_LIST_ID lookup. Sends NOTHING.
Exits 0 on success, non-zero on auth/list/network failure.

Usage:
    BREVO_API_KEY=xkeysib-... BREVO_LIST_ID=42 python3 brevo_smoke_test.py
"""
from __future__ import annotations

import os
import sys

from email_sequence import get_account, get_list


def main() -> int:
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    list_id = os.environ.get("BREVO_LIST_ID", "").strip()

    if not api_key:
        print("ERROR: BREVO_API_KEY not set in env", file=sys.stderr)
        return 2
    if not list_id or not list_id.isdigit():
        print("ERROR: BREVO_LIST_ID not set or not numeric", file=sys.stderr)
        return 2

    status, body = get_account(api_key)
    if status != 200:
        print(f"AUTH FAIL ({status}): {body}", file=sys.stderr)
        return 3
    print(f"Account OK — email={body.get('email')} plan={[p.get('type') for p in body.get('plan', [])]}")

    status, body = get_list(api_key, int(list_id))
    if status != 200:
        print(f"LIST FAIL ({status}): {body}", file=sys.stderr)
        return 4
    print(
        f"List OK — id={body.get('id')} name={body.get('name')!r} "
        f"subscribers={body.get('totalSubscribers', 'n/a')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
