"""Manages the beta's sign-in (deploy/pages/beta-gate.js; docs/web/hosting.md,
"The beta sign-in"): who is invited, and the one password.

The invited emails live in ~/.vivome-beta/emails.txt, outside the repository:
one a line, "#" starts a comment. scripts/build_pages_site.py writes them into
the site, so a change reaches it with the next deploy.

The password is kept as two Pages secrets, set with Wrangler: its salted hash
(BETA_PASSWORD_HASH) and a new key for the session cookies (BETA_SESSION_KEY),
so a new password signs everyone out. The password itself is never stored by
the site; --generate also saves the one it makes to ~/.vivome-beta/password.txt
for the owner to pass on. Secrets reach the site with its next deploy too.

    python scripts/beta_access.py list
    python scripts/beta_access.py add someone@example.org
    python scripts/beta_access.py remove someone@example.org
    python scripts/beta_access.py password               # asks for it, twice, without showing it
    python scripts/beta_access.py password --generate    # makes one and saves it
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from build_pages_site import BETA_EMAILS, PROJECT, REPO, invited

PASSWORD_FILE = BETA_EMAILS.parent / "password.txt"
MIN_LENGTH = 12
# Lowercase letters and digits that cannot be mistaken for one another.
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def password_hash(password: str, salt: bytes | None = None) -> str:
    """"sha256$<salt hex>$<SHA-256 of the salt bytes then the password's UTF-8,
    hex>", as deploy/pages/beta-gate.js checks it."""
    salt = secrets.token_bytes(16) if salt is None else salt
    return f"sha256${salt.hex()}${hashlib.sha256(salt + password.encode('utf-8')).hexdigest()}"


def generate_password() -> str:
    """Three groups of five, such as k7m2p-x9q4r-t3w8z: about 74 bits."""
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(3))


def add(path: Path, email: str) -> bool:
    """Adds `email` to the file; False when it is already there."""
    email = email.strip().lower()
    known = invited(path) if path.exists() else []
    if email in known:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else "# VivOME beta: invited emails, one a line\n"
    path.write_bytes((text + ("" if text.endswith("\n") else "\n") + email + "\n").encode("utf-8"))
    invited(path)  # refuses a line that is not an email
    return True


def remove(path: Path, email: str) -> bool:
    """Removes every line naming `email`; False when none did."""
    email = email.strip().lower()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    kept = [line for line in lines if line.split("#", 1)[0].strip().lower() != email]
    if len(kept) == len(lines):
        return False
    path.write_bytes(("\n".join(kept) + "\n").encode("utf-8"))
    return True


def put_secret(name: str, value: str) -> None:
    """Sets a Pages secret on the production site; the value goes in on stdin."""
    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("npx was not found: install Node.js")
    subprocess.run([npx, "wrangler@4", "pages", "secret", "put", name, "--project-name", PROJECT],
                   input=value, text=True, cwd=REPO, check=True)


def set_password(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise SystemExit(f"use at least {MIN_LENGTH} characters: the site does not limit attempts")
    put_secret("BETA_PASSWORD_HASH", password_hash(password))
    put_secret("BETA_SESSION_KEY", secrets.token_hex(32))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="the invited emails")
    for name in ("add", "remove"):
        commands.add_parser(name, help=f"{name} an invited email").add_argument("email")
    password = commands.add_parser("password", help="set the beta's password (signs everyone out)")
    password.add_argument("--generate", action="store_true", help=f"make one and save it to {PASSWORD_FILE}")
    args = parser.parse_args(argv)
    deploy = "Deploy the site for it to take effect (docs/web/hosting.md, Publishing)."
    if args.command == "list":
        emails = invited(BETA_EMAILS) if BETA_EMAILS.exists() else []
        print("\n".join(emails) if emails else f"no invited emails ({BETA_EMAILS})")
    elif args.command == "add":
        print(f"added {args.email.lower()}. {deploy}" if add(BETA_EMAILS, args.email) else "already invited")
    elif args.command == "remove":
        print(f"removed {args.email.lower()}. {deploy}" if remove(BETA_EMAILS, args.email) else "not on the list")
    elif args.generate:
        new = generate_password()
        set_password(new)
        PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        PASSWORD_FILE.write_bytes((new + "\n").encode("utf-8"))
        print(f"password set and saved to {PASSWORD_FILE}. {deploy}")
    else:
        new = getpass.getpass("New beta password: ")
        if new != getpass.getpass("Again: "):
            raise SystemExit("the two entries differ; nothing changed")
        set_password(new)
        print(f"password set. {deploy}")


if __name__ == "__main__":
    main(sys.argv[1:])
