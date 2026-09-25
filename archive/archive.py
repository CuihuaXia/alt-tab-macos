#!/usr/bin/env python3
"""Keep a long-term archive of AltTab release packages, and install them later.

Upstream (lwouis/alt-tab-macos) ships every release as a single notarized
`AltTab-<version>.zip` holding `AltTab.app`; there is no .dmg. The Sparkle feed
`appcast.xml` lists every stable release with its download URL, byte length,
minimum macOS and EdDSA signature, so it is the source of truth for the manifest.

The binaries are never committed to git: they are re-uploaded as assets of
GitHub Releases on the fork (see .github/workflows/archive_releases.yml).
`archive/releases.json` and `archive/SHA256SUMS` are the only files in git.

Only the Python 3 standard library is used, so it runs on stock macOS and on CI.

  archive.py list                          show archived versions
  archive.py download 11.6.1 [--dir DIR]   download + verify the zip
  archive.py install 11.6.1                download + verify + copy to /Applications (macOS)
  archive.py manifest --count 10           refresh the manifest from upstream appcast.xml
"""
import argparse
import datetime
import email.utils
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "releases.json")
SUMS = os.path.join(HERE, "SHA256SUMS")
UPSTREAM = "lwouis/alt-tab-macos"
UPSTREAM_APPCAST = f"https://raw.githubusercontent.com/{UPSTREAM}/master/appcast.xml"
SPARKLE = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"


def version_key(v):
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "alt-tab-archive"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def load_manifest():
    if not os.path.exists(MANIFEST):
        return {"upstream": UPSTREAM, "archive_repo": None, "releases": []}
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(m):
    m["releases"].sort(key=lambda r: version_key(r["version"]), reverse=True)
    with open(MANIFEST, "w") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(SUMS, "w") as f:
        for r in m["releases"]:
            f.write(f"{r['sha256']}  {r['asset']}\n")


def parse_appcast(xml_bytes):
    items = []
    for item in ET.fromstring(xml_bytes).iter("item"):
        enc = item.find("enclosure")
        if enc is None:
            continue
        version = enc.get(f"{SPARKLE}shortVersionString") or enc.get(f"{SPARKLE}version")
        pub = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        items.append({
            "version": version,
            "tag": f"v{version}",
            "published_at": pub.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "minimum_macos": item.findtext(f"{SPARKLE}minimumSystemVersion"),
            "asset": enc.get("url").rsplit("/", 1)[1],
            "size": int(enc.get("length")),
            "sparkle_ed_signature": enc.get(f"{SPARKLE}edSignature"),
            "upstream_url": enc.get("url"),
            "upstream_release_page": f"https://github.com/{UPSTREAM}/releases/tag/v{version}",
        })
    items.sort(key=lambda r: version_key(r["version"]), reverse=True)
    return items


def cmd_manifest(args):
    """Add the newest `count` appcast releases to the manifest. Older entries are kept, never pruned."""
    xml_bytes = open(args.appcast, "rb").read() if args.appcast else fetch(UPSTREAM_APPCAST)
    m = load_manifest()
    m["upstream"] = UPSTREAM
    if args.archive_repo:
        m["archive_repo"] = args.archive_repo
    known = {r["version"]: r for r in m["releases"]}
    before = json.dumps(m, sort_keys=True)
    for rel in parse_appcast(xml_bytes)[: args.count]:
        if rel["version"] in known and known[rel["version"]].get("sha256"):
            continue
        data = fetch(rel["upstream_url"])
        if len(data) != rel["size"]:
            sys.exit(f"{rel['asset']}: size {len(data)} != appcast length {rel['size']}")
        rel["sha256"] = hashlib.sha256(data).hexdigest()
        if args.save_dir:
            os.makedirs(args.save_dir, exist_ok=True)
            with open(os.path.join(args.save_dir, rel["asset"]), "wb") as f:
                f.write(data)
        known[rel["version"]] = rel
        print(f"added {rel['version']}  {rel['sha256']}")
    repo = m.get("archive_repo")
    for rel in known.values():
        if repo:
            rel["archive_url"] = f"https://github.com/{repo}/releases/download/{rel['tag']}/{rel['asset']}"
            rel["archive_release_page"] = f"https://github.com/{repo}/releases/tag/{rel['tag']}"
    m["releases"] = sorted(known.values(), key=lambda r: version_key(r["version"]), reverse=True)
    if json.dumps(m, sort_keys=True) != before:
        m["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_manifest(m)


def find(version):
    version = version.lstrip("v")
    for r in load_manifest()["releases"]:
        if r["version"] == version:
            return r
    sys.exit(f"{version} is not in {MANIFEST}. Run `archive.py list` to see archived versions.")


def cmd_list(_):
    for r in load_manifest()["releases"]:
        print(f"{r['version']:<10} {r['published_at'][:10]}  macOS {r['minimum_macos']:<8} {r['size'] / 1e6:5.1f} MB")


def download(rel, dest_dir):
    """Try the fork's archive first (it survives upstream deleting assets), then upstream."""
    urls = [u for u in (rel.get("archive_url"), rel["upstream_url"]) if u]
    for url in urls:
        try:
            data = fetch(url)
        except Exception as e:
            print(f"  {url}: {e}", file=sys.stderr)
            continue
        if hashlib.sha256(data).hexdigest() != rel["sha256"]:
            print(f"  {url}: SHA-256 mismatch, ignoring", file=sys.stderr)
            continue
        path = os.path.join(dest_dir, rel["asset"])
        with open(path, "wb") as f:
            f.write(data)
        print(f"{path}  (from {url}, SHA-256 verified)")
        return path
    sys.exit("no source returned a file with the expected SHA-256")


def cmd_download(args):
    download(find(args.version), args.dir)


def cmd_install(args):
    if sys.platform != "darwin":
        sys.exit("install only works on macOS; use `download` instead")
    rel = find(args.version)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = download(rel, tmp)
        subprocess.run(["ditto", "-x", "-k", zip_path, tmp], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", os.path.join(tmp, "AltTab.app")], check=True)
        subprocess.run(["osascript", "-e", 'quit app "AltTab"'], check=False)
        target = os.path.join(args.applications, "AltTab.app")
        if os.path.exists(target):
            shutil.rmtree(target)
        subprocess.run(["ditto", os.path.join(tmp, "AltTab.app"), target], check=True)
    print(f"installed AltTab {rel['version']} to {target}")
    print("Tip: in AltTab settings, set updates to \"Don’t check for updates periodically\", or it will offer the newest version again.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    d = sub.add_parser("download")
    d.add_argument("version")
    d.add_argument("--dir", default=".")
    d.set_defaults(func=cmd_download)
    i = sub.add_parser("install")
    i.add_argument("version")
    i.add_argument("--applications", default="/Applications")
    i.set_defaults(func=cmd_install)
    mf = sub.add_parser("manifest")
    mf.add_argument("--count", type=int, default=10)
    mf.add_argument("--appcast", help="local appcast.xml; default is upstream master")
    mf.add_argument("--archive-repo", help="owner/repo whose Releases hold the archived zips")
    mf.add_argument("--save-dir", help="also keep the downloaded zips here")
    mf.set_defaults(func=cmd_manifest)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
