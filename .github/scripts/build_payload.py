"""Assemble an Edition Docker context locally; never build or deploy it."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tg2cloud.deployment.fingerprints import fingerprint
from tg2cloud.deployment.payload import build_payload
from tg2cloud.deployment.profiles import PRODUCTS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", required=True, choices=tuple(PRODUCTS) + ("all",))
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.directory.exists():
        raise ValueError("output must not exist; refusing to replace a context")
    products = tuple(PRODUCTS.values()) if args.edition == "all" else (PRODUCTS[args.edition],)
    if args.edition == "all":
        args.directory.mkdir(mode=0o700, parents=True)
    else:
        args.directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for product in products:
        destination = args.directory / product.key if args.edition == "all" else args.directory
        build_payload(ROOT, product, destination)
        print(product.key + " " + fingerprint(destination / "app"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
