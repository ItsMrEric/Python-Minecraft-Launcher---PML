import json
import os
import platform
import subprocess
import time
import uuid
import zipfile
import tarfile
from pathlib import Path

import requests
import certifi

# ================= HTTP SESSION =================

SESSION = requests.Session()
SESSION.verify = certifi.where()
SESSION.headers.update({
    "User-Agent": "SimpleMinecraftLauncher/1.0"
})

# ================= CONFIG =================

BASE_DIR = Path("mc")
VERSIONS_DIR = BASE_DIR / "versions"
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
RUNTIMES_DIR = BASE_DIR / "java"

MAX_RAM = "4G"

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"

# ================= FILE SYSTEM =================

def ensure_dirs():
    for d in [VERSIONS_DIR, LIBRARIES_DIR, ASSETS_DIR, RUNTIMES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# ================= UTIL =================

def download_with_progress(url, path, label=None):
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    r = SESSION.get(url, stream=True)
    r.raise_for_status()

    total = int(r.headers.get("Content-Length", 0))
    downloaded = 0
    start = time.time()

    name = label or path.name
    print(f"⬇ {name}")

    with open(path, "wb") as f:
        for chunk in r.iter_content(1024 * 64):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)

            elapsed = time.time() - start
            speed = downloaded / elapsed if elapsed > 0 else 0

            if total:
                percent = downloaded / total * 100
                print(
                    f"\r  {percent:6.2f}% | "
                    f"{downloaded/1024/1024:6.2f} / "
                    f"{total/1024/1024:6.2f} MB | "
                    f"{speed/1024/1024:5.2f} MB/s",
                    end="",
                    flush=True
                )

    print()

# ================= JAVA =================

def get_required_java(version_json):
    return version_json.get("javaVersion", {}).get("majorVersion", 8)

def download_java(java_major, dest):
    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "darwin":
        os_name = "mac"
        arch = "aarch64" if "arm" in arch else "x64"
        ext = "tar.gz"
    elif system == "windows":
        os_name = "windows"
        arch = "x64"
        ext = "zip"
    else:
        os_name = "linux"
        arch = "x64"
        ext = "tar.gz"

    url = (
        f"https://api.adoptium.net/v3/binary/latest/"
        f"{java_major}/ga/{os_name}/{arch}/jdk/"
        f"hotspot/normal/eclipse"
    )

    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / f"java{java_major}.{ext}"

    print(f"Downloading Java {java_major}...")
    download_with_progress(url, archive, f"Java {java_major}")

    print("Extracting Java...")
    if ext == "zip":
        zipfile.ZipFile(archive).extractall(dest)
    else:
        tarfile.open(archive).extractall(dest)

    archive.unlink()

def find_java(java_dir):
    system = platform.system()

    if system == "Darwin":
        for p in java_dir.glob("**/Contents/Home/bin/java"):
            return p

    for p in java_dir.rglob("bin/java"):
        return p
    for p in java_dir.rglob("bin/java.exe"):
        return p

    return None

# ================= MINECRAFT DOWNLOAD =================

def get_version_manifest():
    return SESSION.get(MANIFEST_URL).json()

def download_libraries(version_json):
    for lib in version_json.get("libraries", []):
        artifact = lib.get("downloads", {}).get("artifact")
        if not artifact:
            continue
        path = LIBRARIES_DIR / artifact["path"]
        download_with_progress(
            artifact["url"],
            path,
            artifact["path"].split("/")[-1]
        )

def download_version(version_id):
    manifest = get_version_manifest()
    info = next(v for v in manifest["versions"] if v["id"] == version_id)

    version_json = SESSION.get(info["url"]).json()

    version_dir = VERSIONS_DIR / version_id
    version_dir.mkdir(parents=True, exist_ok=True)

    with open(version_dir / f"{version_id}.json", "w") as f:
        json.dump(version_json, f, indent=2)

    download_with_progress(
        version_json["downloads"]["client"]["url"],
        version_dir / f"{version_id}.jar",
        f"Minecraft {version_id}"
    )

    download_libraries(version_json)
    return version_json

# ================= ASSETS (SOUNDS + BACKGROUND) =================

def download_assets(version_json):
    asset_index = version_json["assetIndex"]
    index_id = asset_index["id"]

    index_dir = ASSETS_DIR / "indexes"
    index_dir.mkdir(parents=True, exist_ok=True)

    index_path = index_dir / f"{index_id}.json"

    download_with_progress(
        asset_index["url"],
        index_path,
        f"Asset index {index_id}"
    )

    index_data = json.load(open(index_path))
    objects = index_data["objects"]

    print(f"Downloading {len(objects)} assets...")

    for name, info in objects.items():
        h = info["hash"]
        sub = h[:2]
        obj_path = ASSETS_DIR / "objects" / sub / h

        if obj_path.exists():
            continue

        url = f"https://resources.download.minecraft.net/{sub}/{h}"
        download_with_progress(url, obj_path, name)

# ================= AUTH =================

def offline_auth(username):
    return {
        "username": username,
        "uuid": str(uuid.uuid4()).replace("-", ""),
        "access_token": "offline"
    }

# ================= LAUNCH =================

def build_classpath(version_json, version_id):
    sep = ";" if platform.system() == "Windows" else ":"
    cp = []

    for lib in version_json.get("libraries", []):
        artifact = lib.get("downloads", {}).get("artifact")
        if artifact:
            cp.append(str(LIBRARIES_DIR / artifact["path"]))

    cp.append(str(VERSIONS_DIR / version_id / f"{version_id}.jar"))
    return sep.join(cp)

def launch(version_id, auth, java_path):
    version_dir = VERSIONS_DIR / version_id
    version_json = json.load(open(version_dir / f"{version_id}.json"))

    cmd = [
        str(java_path),
        "-XstartOnFirstThread" if platform.system() == "Darwin" else "",
        f"-Xmx{MAX_RAM}",
        "-cp", build_classpath(version_json, version_id),
        version_json["mainClass"],
        "--username", auth["username"],
        "--uuid", auth["uuid"],
        "--accessToken", auth["access_token"],
        "--gameDir", str(BASE_DIR),
        "--assetsDir", str(ASSETS_DIR),
        "--assetIndex", version_json["assets"],
        "--version", version_id
    ]

    cmd = [c for c in cmd if c]

    print("Launching Minecraft...")
    subprocess.run(cmd)

# ================= MAIN =================

def main():
    ensure_dirs()

    username = input("Username (offline): ")
    version = input("Minecraft version (e.g. 1.20.1): ")

    auth = offline_auth(username)

    version_json = download_version(version)
    download_assets(version_json)

    java_major = get_required_java(version_json)
    java_dir = RUNTIMES_DIR / f"java{java_major}"

    if not find_java(java_dir):
        download_java(java_major, java_dir)

    java_path = find_java(java_dir)
    if not java_path:
        raise RuntimeError("Java executable not found")

    launch(version, auth, java_path)

if __name__ == "__main__":
    main()
