#!/usr/bin/env python3
"""
Small admin CLI.

    python manage.py model                     show the active model
    python manage.py model --list              ask the provider what it serves
    python manage.py model llama-3.1-8b-instant   switch to it
    python manage.py model --reset             fall back to ASSISTANT_MODEL in .env
    python manage.py model --base-url URL      point at another OpenAI-compatible provider

Changes take effect on the next message. No restart.
"""

import argparse
import asyncio
import sys

import store
from services.assistant import ENV_BASE_URL, ENV_MODEL, active_config, list_models


def cmd_model(args):
    store.init_store()

    if args.list:
        result = asyncio.run(list_models())
        if result["source"] == "provider":
            print(f"Models available at {result['base_url']}:\n")
            for name in result["models"]:
                print(f"  {'*' if name == result['current'] else ' '} {name}")
            print("\n* = active")
        elif result["source"] == "unconfigured":
            print("No API key set. Add ASSISTANT_API_KEY to .env first.")
        else:
            print(f"Could not reach the provider: {result.get('error')}")
        return

    updates = {}
    if args.reset:
        updates["assistant_model"] = ""
        updates["assistant_base_url"] = ""
    if args.base_url:
        updates["assistant_base_url"] = args.base_url
    if args.name:
        updates["assistant_model"] = args.name

    if updates:
        store.set_settings(updates)

    config = active_config()
    settings = store.get_settings()

    print(f"model:    {config['model']}"
          f"{'' if settings.get('assistant_model') else f'   (from .env: {ENV_MODEL})'}")
    print(f"base_url: {config['base_url']}"
          f"{'' if settings.get('assistant_base_url') else f'   (from .env: {ENV_BASE_URL})'}")


def main():
    parser = argparse.ArgumentParser(description="Dashboard admin commands")
    sub = parser.add_subparsers(dest="command", required=True)

    model = sub.add_parser("model", help="show or change the assistant model")
    model.add_argument("name", nargs="?", help="model id to switch to")
    model.add_argument("--list", action="store_true", help="list models the provider serves")
    model.add_argument("--reset", action="store_true", help="fall back to the .env value")
    model.add_argument("--base-url", help="switch to another OpenAI-compatible endpoint")
    model.set_defaults(func=cmd_model)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
