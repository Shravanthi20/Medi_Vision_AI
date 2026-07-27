"""
MediVision Mobile — Vendor Activation Tool
Issue a time-boxed unlock code for a customer's phone (30-day billing cycle
by default). The phone shows a DEVICE CODE on its lock screen; paste it here
to generate the UNLOCK CODE to send back.

Codes are signed with an ECDSA P-256 private key (mobile_signing_key.pem,
generated once, NEVER committed — see .gitignore). Only the matching public
key ships inside the app; a decompiled APK cannot forge new codes from it.
If mobile_signing_key.pem is missing, run --keygen once to create it.

USAGE:
    python mobile_activate.py --keygen                     (one-time setup)
    python mobile_activate.py XXXX-XXXX-XXXX-XXXX
    python mobile_activate.py XXXX-XXXX-XXXX-XXXX --days 30

KEEP mobile_signing_key.pem PRIVATE. Losing it means re-issuing every
customer's code (against a new keypair); leaking it means anyone can forge
licenses. Do not ship it, email it, or commit it.
"""
import sys
import os
import base64
import argparse
from datetime import datetime, timedelta

KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_signing_key.pem")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def keygen():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    if os.path.exists(KEY_PATH):
        print(f"A signing key already exists at {KEY_PATH}.")
        print("Refusing to overwrite it — that would invalidate every code issued so far.")
        return

    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(KEY_PATH, "wb") as f:
        f.write(pem)

    pub = priv.public_key().public_numbers()
    x, y = pub.x.to_bytes(32, "big"), pub.y.to_bytes(32, "big")
    print(f"Signing key created: {KEY_PATH}")
    print("Back this file up somewhere safe (outside git). If you lose it, every phone")
    print("needs re-activation against a new key.\n")
    print("Public key JWK (for mobile/www/license-lock.js PUBLIC_KEY_JWK — already set):")
    print(f'  {{"kty":"EC","crv":"P-256","x":"{_b64url(x)}","y":"{_b64url(y)}"}}')


def load_private_key():
    from cryptography.hazmat.primitives import serialization

    if not os.path.exists(KEY_PATH):
        print(f"No signing key found at {KEY_PATH}.")
        print("Run: python mobile_activate.py --keygen")
        sys.exit(1)
    with open(KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign_code(device_code: str, expiry_yyyymmdd: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    priv = load_private_key()
    msg = f"{device_code}|{expiry_yyyymmdd}".encode()
    der_sig = priv.sign(msg, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    # Web Crypto's ECDSA verify expects raw IEEE P1363 (r||s, fixed 32B each),
    # not the DER encoding `cryptography` produces by default.
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{expiry_yyyymmdd}.{_b64url(raw_sig)}"


def main():
    ap = argparse.ArgumentParser(description="Generate a signed mobile unlock code.")
    ap.add_argument("device_code", nargs="?", help="Device code shown on the phone's lock screen")
    ap.add_argument("--days", type=int, default=30, help="Validity period in days (default 30)")
    ap.add_argument("--keygen", action="store_true", help="One-time: generate the vendor signing keypair")
    args = ap.parse_args()

    print("=" * 60)
    print(" MediVision AI - Mobile Vendor Activation Tool")
    print("=" * 60)

    if args.keygen:
        keygen()
        return

    dc = args.device_code or input("Enter customer's DEVICE CODE (XXXX-XXXX-XXXX-XXXX): ").strip()
    if not dc or len(dc.replace("-", "")) != 16:
        print("Invalid device code. Expected 16 hex chars + dashes.")
        return
    dc = dc.upper()

    expiry_date = datetime.now() + timedelta(days=args.days)
    expiry_yyyymmdd = expiry_date.strftime("%Y%m%d")
    code = sign_code(dc, expiry_yyyymmdd)

    print()
    print(f"  Device Code    : {dc}")
    print(f"  Valid until    : {expiry_date.strftime('%d-%b-%Y')} ({args.days} days)")
    print(f"  Unlock Code    : {code}")
    print()
    print("Send the Unlock Code exactly as printed — it's meant to be copy-pasted")
    print("(WhatsApp/SMS), not retyped. It only works on that phone.")


if __name__ == "__main__":
    main()
