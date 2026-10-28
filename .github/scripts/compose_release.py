"""Build Compose candidates or publish an immutable multi-platform image index."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess  # nosec B404
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tg2cloud.compose.packaging import build_bundles
from tg2cloud.version import VERSION


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("registry redirects refused")


def request(path, *, token="", basic=""):
    # All requests stay on the one registry; no credentials in URL/arguments/logs.
    headers = {"Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    elif basic:
        headers["Authorization"] = "Basic " + basic
    req = urllib.request.Request("https://ghcr.io/" + path, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:  # nosec B310 - fixed HTTPS registry
            data = response.read(2 * 1024**2 + 1)
            if len(data) > 2 * 1024**2:
                raise ValueError("registry response too large")
            return data
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise ValueError("registry request failed; refusing publication") from None


def index(image):
    if not re.fullmatch(r"ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+:[0-9]+\.[0-9]+\.[0-9]+", image):
        raise ValueError("expected a stable version in GHCR")
    repository, tag = image.removeprefix("ghcr.io/").split(":")
    user, secret = os.environ.get("GITHUB_ACTOR", ""), os.environ.get("GH_TOKEN", "")
    basic = base64.b64encode((user + ":" + secret).encode()).decode() if secret else ""
    auth = request("token?" + urllib.parse.urlencode({"service": "ghcr.io", "scope": "repository:" + repository + ":pull"}), basic=basic)
    if auth is None:
        raise ValueError("registry authorization unavailable")
    token = json.loads(auth)["token"]
    data = request("v2/" + repository + "/manifests/" + tag, token=token)
    return (data, json.loads(data)) if data is not None else (None, None)


def native_identity(repository, digest, architecture, commit, version):
    """Verify the immutable child config; Docker v2 lists cannot hold annotations."""
    result = subprocess.run([
        "docker", "buildx", "imagetools", "inspect", repository + "@" + digest,
        "--format", "{{json .Image}}",
    ], check=True, capture_output=True, text=True, timeout=60)  # nosec B603 B607 - fixed executable and validated references
    if len(result.stdout) > 2 * 1024**2:
        raise ValueError("image configuration too large")
    config = json.loads(result.stdout)
    labels = config.get("config", {}).get("Labels", {})
    if (config.get("os") != "linux" or config.get("architecture") != architecture
            or labels.get("org.opencontainers.image.revision") != commit
            or labels.get("org.opencontainers.image.version") != version):
        raise ValueError("native image identity mismatch; never overwrite")


def validate_index(image, commit, manifest, expected=None):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid source commit")
    if manifest.get("mediaType") not in (
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json"):
        raise ValueError("expected an image index or manifest list")
    revision = manifest.get("annotations", {}).get("org.opencontainers.image.revision")
    if revision is not None and revision != commit:
        raise ValueError("existing image belongs to another commit; never overwrite")
    children = manifest.get("manifests", [])
    platforms = {(item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
                 for item in children}
    if len(children) != 2 or platforms != {("linux", "amd64"), ("linux", "arm64")}:
        raise ValueError("image does not contain exactly both native Linux platforms")
    digests = {item["platform"]["architecture"]: item.get("digest", "") for item in children}
    if (not all(re.fullmatch(r"sha256:[0-9a-f]{64}", d) for d in digests.values())
            or len(set(digests.values())) != 2 or (expected is not None and digests != expected)):
        raise ValueError("native image digest mismatch; never overwrite")
    repository, version = image.rsplit(":", 1)
    for architecture, digest in digests.items():
        native_identity(repository, digest, architecture, commit, version)
    return digests


def inspect_index(image, commit):
    _, manifest = index(image)
    if manifest is None:
        return {"reuse": "false"}
    digests = validate_index(image, commit, manifest)
    return {"reuse": "true", **digests}


def publish_index(image, commit, amd64, arm64):
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not all(re.fullmatch(r"sha256:[0-9a-f]{64}", d) for d in (amd64, arm64)):
        raise ValueError("invalid commit or native image digests")
    data, manifest = index(image)
    if data is None:
        repository = image.split(":", 1)[0]
        # Validate the children before creating any public version tag.
        for architecture, digest in (("amd64", amd64), ("arm64", arm64)):
            native_identity(repository, digest, architecture, commit, image.rsplit(":", 1)[1])
        subprocess.run(["docker", "buildx", "imagetools", "create", "--annotation",
                        "index:org.opencontainers.image.revision=" + commit, "--tag", image,
                        repository + "@" + amd64, repository + "@" + arm64], check=True)  # nosec B603 B607 - fixed executable and validated inputs
        data, manifest = index(image)
    if manifest is None:
        raise ValueError("published index unavailable")
    validate_index(image, commit, manifest, {"amd64": amd64, "arm64": arm64})
    return image.split(":", 1)[0] + "@sha256:" + hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bundle", "publish-index", "inspect-index"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--image", default="ghcr.io/luopojunzi/tg2cloud:" + VERSION)
    parser.add_argument("--commit", default="")
    parser.add_argument("--amd64")
    parser.add_argument("--arm64")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "bundle":
            if args.directory is None:
                parser.error("bundle requires --directory")
            for archive in build_bundles(ROOT, args.directory, args.image, args.commit):
                print(archive.name)
        elif args.action == "inspect-index":
            outputs = inspect_index(args.image, args.commit)
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as out:
                    for key, value in outputs.items():
                        out.write(key + "=" + value + "\n")
            print("COMPOSE_INDEX_REUSE=" + outputs["reuse"])
        else:
            image = publish_index(args.image, args.commit, args.amd64 or "", args.arm64 or "")
            print(image)
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as out:
                    out.write("image=" + image + "\n")
        return 0
    except Exception:  # noqa: BLE001 - registry errors may carry private response details
        print("Compose release validation failed; no secrets or registry response printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
