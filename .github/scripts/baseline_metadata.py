"""Print a reviewable baseline entry from an explicit local immutable Git object."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tg2cloud.deployment import baselines, releases
from tg2cloud.deployment.profiles import PRODUCTS


def entry(tag: str, commit: str) -> dict:
    if not releases.TAG.fullmatch(tag) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("explicit stable tag and full commit required")
    git = shutil.which("git")
    if not git:
        raise ValueError("Git required")
    with tempfile.TemporaryDirectory(prefix="tg2cloud-baseline-") as temporary:
        directory = Path(temporary).resolve()
        archive = directory / "source.tar.gz"
        subprocess.run([git, "-C", str(ROOT), "archive", "--format=tar.gz", "--prefix=source/",
                        "--output=" + str(archive), commit], check=True, capture_output=True)  # nosec B603
        source = directory / "source"
        releases.extract_source(archive, source)
        if releases.source_version(source) != tag[1:]:
            raise ValueError("commit version mismatch")
        return {"commit": commit, "payloads": {key: baselines.payload_digest(source, product)
                                               for key, product in PRODUCTS.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    print(json.dumps({args.tag: entry(args.tag, args.commit)}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
