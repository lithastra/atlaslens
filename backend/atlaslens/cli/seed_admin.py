"""Provision an admin user by inserting a hashed password into MongoDB.

Usage:
    python -m atlaslens.cli.seed_admin --username alice
"""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from atlaslens.api.auth import hash_password
from atlaslens.db import close_db, connect_db


async def _seed(username: str, password: str) -> None:
    db = await connect_db()
    try:
        existing = await db["users"].find_one(
            {"username": username}
        )
        if existing:
            print(f"User '{username}' already exists.")
            sys.exit(1)

        await db["users"].insert_one({
            "_id": username,
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now(UTC),
            "disabled": False,
        })
        print(f"Admin '{username}' created.")
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed an admin user"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--password",
        default=None,
        help="Password (prompted if omitted)",
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    asyncio.run(_seed(args.username, password))


if __name__ == "__main__":
    main()
