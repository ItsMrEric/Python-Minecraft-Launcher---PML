import json
import os
import platform
import subprocess
import uuid
import hashlib
import shutil
import urllib.request
from pathlib import Path
import requests
import ssl
import tarfile
import zipfile
import re
import sys



ssl._create_default_https_context = ssl._create_unverified_context

BASE_DIR = Path("mc")
VERSIONS_DIR = BASE_DIR / "versions"
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"
JAVA_DOWNLOAD_URLS = {
    "Windows": "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jre/hotspot/normal/eclipse",
    "Linux": "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse",
    "Darwin": "https://api.adoptium.net/v3/binary/latest/17/ga/mac/x64/jre/hotspot/normal/eclipse",
}
LAUNCHER_CONFIG_PATH = Path(BASE_DIR / "launcher_config.json")
DEFAULT_CONFIG = {
    "manifest_url": "https://piston-meta.mojang.com/mc/game/version_manifest.json",
    "java_cmd": "java",
    "max_ram": "4G",
    "accounts": [],
    "selected_account": {"username": None, "online": None, "uuid": None},
    "version_display": {"old_alpha": True, "old_beta": True, "snapshot": True, "release": True},
    "selected_version": {
        "path": None,
        "id": None,
        "json_path": None
    }
}
JAVA_CMD = "java"
MAX_RAM = "2G"
# ---------------- CONFIG ----------------
JAVA_BASE_DIR = Path("java")
JAVA_DIR = BASE_DIR / "runtime"
# Java 17 (LTS) download URLs from Adoptium
JAVA_DOWNLOAD_URLS = {
    "Windows": "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jre/hotspot/normal/eclipse",
    "Linux":   "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse",
    "Darwin":  "https://api.adoptium.net/v3/binary/latest/17/ga/mac/x64/jre/hotspot/normal/eclipse",
}
# ----------------------------------------

def get_java_download_url(version, platform):
    urls = {
        "windows": f"https://api.adoptium.net/v3/binary/latest/{version}/ga/windows/x64/jre/hotspot/normal/eclipse",
        "linux":   f"https://api.adoptium.net/v3/binary/latest/{version}/ga/linux/x64/jre/hotspot/normal/eclipse",
        "mac":  f"https://api.adoptium.net/v3/binary/latest/{version}/ga/mac/x64/jre/hotspot/normal/eclipse",
    }
    return urls[platform]

def download_java(url, out_file):
    print("Downloading Java")
    urllib.request.urlretrieve(url, out_file)
    print("Download complete")

def find_local_java(required_major: int, java_root: str = "java"):
    """
    Checks if a specific Java major version exists under the java folder.
    Returns the java executable path if found, otherwise False.
    """
    java_root = Path(java_root)
    java_dir = java_root / f"java{required_major}"
    if sys.platform.startswith("win"):
        java_exe = java_dir / "bin" / "java.exe"
    else:
        java_exe = java_dir / "bin" / "java"
    if java_exe.exists():
        return str(java_exe)
    return False

def extract_java(archive_path, target_dir):
    print("Extracting Java...")
    target_dir.mkdir(parents=True, exist_ok=True)

    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(target_dir)
    else:
        with tarfile.open(archive_path, "r:*") as t:
            t.extractall(target_dir)

    print("Extraction complete.")

def find_java_executable():
    for root, dirs, files in os.walk(JAVA_DIR):
        if platform.system() == "Windows" and "java.exe" in files:
            return Path(root) / "java.exe"
        if platform.system() != "Windows" and "java" in files:
            return Path(root) / "java"
    return None

def main():
    system = platform.system()

    if system not in JAVA_DOWNLOAD_URLS:
        raise RuntimeError(f"Unsupported OS: {system}")

    JAVA_BASE_DIR.mkdir(exist_ok=True)

    archive_name = "java.zip" if system == "Windows" else "java.tar.gz"
    archive_path = JAVA_BASE_DIR / archive_name

    if not JAVA_DIR.exists():
        download_java(JAVA_DOWNLOAD_URLS[system], archive_path)
        extract_java(archive_path, JAVA_DIR)

    java_bin = find_java_executable()
    if not java_bin:
        raise RuntimeError("Java executable not found.")

    print("\nRunning local Java:")
    subprocess.run([str(java_bin), "-version"])

def get_java_major(java_path="java"):
    proc = subprocess.run(
        [java_path, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Java prints version info to stderr
    text = proc.stderr.decode("utf-8", errors="ignore")

    # Debug (keep this for now)
    print(text)

    # Match: version "21.0.4"
    match = re.search(r'version\s+"(\d+)', text)
    if match:
        return int(match.group(1))

    return None

def build_launch_command(version_json: dict, config: dict) -> list[str]:
    """
    Build the full Java launch command from a Minecraft version JSON
    and a config/context dict.
    """

    VAR = re.compile(r"\$\{([^}]+)\}")

    def expand(value: str) -> str:
        return VAR.sub(lambda m: str(config.get(m.group(1), "")), value)

    def rule_allows(rule: dict) -> bool:
        # OS checks
        os_rule = rule.get("os")
        if os_rule:
            if "name" in os_rule:
                sysname = platform.system()
                if os_rule["name"] == "osx" and sysname != "Darwin":
                    return False
                if os_rule["name"] == "windows" and sysname != "Windows":
                    return False
                if os_rule["name"] == "linux" and sysname != "Linux":
                    return False

            if "arch" in os_rule:
                if os_rule["arch"] not in platform.machine().lower():
                    return False
                
                

        # Feature checks
        for key, val in rule.get("features", {}).items():
            if config.get(key) != val:
                return False

        return True

    def rules_pass(entry: dict) -> bool:
        if "rules" not in entry:
            return True
        return any(
            rule_allows(rule)
            for rule in entry["rules"]
            if rule.get("action") == "allow"
        )

    def build_arg_list(entries: list) -> list[str]:
        args = []
        for entry in entries:
            if isinstance(entry, str):
                args.append(expand(entry))

            elif isinstance(entry, dict):
                if not rules_pass(entry):
                    continue

                value = entry["value"]
                if isinstance(value, list):
                    args.extend(expand(v) for v in value)
                else:
                    args.append(expand(value))

        return args

    # ---- JVM + GAME ARGS ----
    jvm_args = build_arg_list(version_json["arguments"]["jvm"])
    game_args = build_arg_list(version_json["arguments"]["game"])

    # ---- FINAL COMMAND ----
    return [
        config["java_path"],
        *jvm_args,
        version_json["mainClass"],
        *game_args,
    ]

def clear_folder_contents(folder: Path):
    if not folder.exists():
        return

    for item in folder.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

def load_or_fix_json(path, default_data):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    updated = False
    for key, value in default_data.items():
        if key not in data:
            data[key] = value
            updated = True
    if not path.exists() or updated:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    return data

def ensure_dirs():
    for d in [BASE_DIR, VERSIONS_DIR, LIBRARIES_DIR, ASSETS_DIR, INDEXES_DIR, OBJECTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def fetch_minecraft_versions():
    try:
        resp = requests.get(MC_MANIFEST_URL)
    except Exception:
        return False
    manifest = resp.json()
    return manifest

if __name__ == "__main__":
    print()
    print()
    print("Welcome to PML -- Python Minecraft Launcher by ItsMrEric")
    print("You can input stuff when you see \">\". The text behind it shows the current page")
    print("Input \"b\" to return (go back)")
    print("Ensuring dirs......")
    ensure_dirs()
    print("Reading configs......" )
    configs = load_or_fix_json(LAUNCHER_CONFIG_PATH, DEFAULT_CONFIG)
    MC_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    print()
    running = True
    while running:
        print("1: Versions")
        print("2: Accounts")
        print("3: Settings")
        print("4: Launch")
        c = input("Main > ")
        if c == "1":
            versions_running = True
            while versions_running:
                print("1: Download & install version")
                print("2: Delete installed version")
                print("3: Select installed version")
                print("4: List versions")
                c = input("Main-Versions > ")
                if c == "1":
                    print("Loading version list......")
                    version_list_raw = fetch_minecraft_versions()
                    if not version_list_raw:
                        input("Failed to fetch version list!")
                    else:
                        print("Version list:")
                        version_list = version_list_raw["versions"]
                        release = configs["version_display"]["release"]
                        snapshot = configs["version_display"]["snapshot"]
                        old_beta = configs["version_display"]["old_beta"]
                        old_alpha = configs["version_display"]["old_alpha"]
                        filtered_list = []
                        c = 0
                        for i in version_list:
                            if i["type"] == "release" and release:
                                print(f"{str(c)}: {i["id"]} ({i["type"]})")
                                filtered_list.append(i)
                                c += 1
                            elif i["type"] == "snapshot" and snapshot:
                                print(f"{str(c)}: {i["id"]} ({i["type"]})")
                                filtered_list.append(i)
                                c += 1
                            elif i["type"] == "old_beta" and old_beta:
                                print(f"{str(c)}: {i["id"]} ({i["type"]})")
                                filtered_list.append(i)
                                c += 1
                            elif i["type"] == "old_alpha" and old_alpha:
                                print(f"{str(c)}: {i["id"]} ({i["type"]})")
                                filtered_list.append(i)
                                c += 1
                        id = input("Select version to install> ")
                        if id == "b":
                            pass
                        elif not id.isdigit():
                            input("Unsupported input")
                        elif int(id) > c or int(id) < 0:
                            input("Unsupported input")
                        else:
                            c = 0
                            for i in filtered_list:
                                if int(id) == c:
                                    version = i
                                c += 1
                            json_url = version["url"]
                            version_id = version["id"]
                            version_folder = Path(VERSIONS_DIR / version_id)
                            print(f"Downloading {version_id} under \"{version_folder}\"!")
                            try:
                                version_folder.mkdir()
                                no_erase = False
                            except FileExistsError:
                                c = input("This version folder already exists! Do you want to erase it and reinstall? (Y/N)> ")
                                if c.upper() == "Y":
                                    clear_folder_contents(version_folder)
                                    no_erase = False
                                elif c.upper() == "N":
                                    no_erase = True
                                else:
                                    input("Unrecognized input")
                                    no_erase = True
                            if not no_erase:
                                
                                json_path = Path(version_folder / f"{version_id}.json")
                                try:
                                    print("Downloading version.json file")
                                    urllib.request.urlretrieve(json_url, json_path)
                                    go_client = True
                                    print("Done")
                                except Exception as e:
                                    input("Unable to download version.json file: " + str(e))
                                    go_client = False
                                if go_client:
                                    with open(json_path) as json_file:
                                        print("Downloading client.jar file")
                                        json_data = json.load(json_file)
                                        client_url = json_data["downloads"]["client"]["url"]
                                        client_path = Path(version_folder / f"{version_id}.jar")
                                        try:
                                            urllib.request.urlretrieve(client_url, client_path)
                                            go_asset_index = True
                                            print("Done")
                                        except Exception as e:
                                            input("Unable to download client.jar file: " + str(e))
                                            go_asset_index = False
                                    if go_asset_index:
                                        with open(json_path) as json_file:
                                            print("Downloading asset index")
                                            json_data = json.load(json_file)
                                            asset_index_url = json_data["assetIndex"]["url"]
                                            asset_index_id = json_data["assetIndex"]["id"]
                                            asset_index_path = Path(ASSETS_DIR / "indexes" / f"{asset_index_id}.json")
                                            go = False
                                            if asset_index_path.exists():
                                                passed = False
                                                while not passed:
                                                    c = input("The asset index file already exists! Do you want to erase it (or skip: \"S\") and download it again? (Y/N/S)> ")
                                                    if c.upper() == "Y":
                                                        asset_index_path.unlink()
                                                        go = True
                                                        passed = True
                                                    elif c.upper() == "N":
                                                        go = False
                                                        passed = True
                                                    elif c.upper() == "S":
                                                        go = True
                                                        passed = True
                                                    else:
                                                        input("Unrecognized input")
                                            else:
                                                go = True
                                            if go:
                                                try:
                                                    urllib.request.urlretrieve(asset_index_url, asset_index_path)
                                                    go_assets = True
                                                except Exception as e:
                                                    input("Unable to download asset_index.json file: " + str(e))
                                                    go_assets = False
                                                    
                                        if go_assets:
                                            n = 0
                                            with open(asset_index_path) as asset_index_file:
                                                print("Downloading assets (this is going to be slow though =D)")
                                                assets_index_data = json.load(asset_index_file)
                                                go_libraries = True
                                                for asset_name, asset_data in assets_index_data["objects"].items():
                                                    print(f"Total files: {len(assets_index_data["objects"])}, currently downloaded: {str(n)} ({str(int(n / len(assets_index_data["objects"]) * 100))}%)")
                                                    asset_hash = asset_data["hash"]
                                                    sub_dir = asset_hash[:2]
                                                    out_dir = OBJECTS_DIR / sub_dir
                                                    out_dir.mkdir(parents=True, exist_ok=True)
                                                    out_file = out_dir / asset_hash
                                                    url = f"https://resources.download.minecraft.net/{sub_dir}/{asset_hash}"
                                                    if out_file.exists():
                                                        continue
                                                    if asset_name == "READ_ME_I_AM_VERY_IMPORTANT":
                                                        print(f"Downloading: {asset_name} (LOL what kind of file is this)")
                                                    else:
                                                        print(f"Downloading: {asset_name}")
                                                    try:
                                                        urllib.request.urlretrieve(url, out_file)
                                                        n += 1
                                                    except Exception as e:
                                                        input(f"Unable to download (asset) {asset_name}: {str(e)}")
                                                        go_libraries = False
                                                        break
                                                if go_libraries:
                                                    print("Done")
                                                    print("Checking & downloading libraries")
                                                    version_download_done = True
                                                    for library_data in json_data["libraries"]:
                                                        try:
                                                            library_path = Path(LIBRARIES_DIR / library_data["downloads"]["artifact"]["path"])
                                                        except Exception as e:
                                                            continue
                                                        if library_path.exists():
                                                            print(f"Library: {str(library_path)} already exists, skipping......")
                                                        else:
                                                            library_path.parent.mkdir(parents = True, exist_ok = True)
                                                            print(f"Downloading library: {str(library_path)}")
                                                            library_url = library_data["downloads"]["artifact"]["url"]
                                                            try:
                                                                urllib.request.urlretrieve(library_url, str(library_path))
                                                            except Exception as e:
                                                                input(f"Unable to download (library) {library_path}: {str(e)}")
                                                                version_download_done = False
                                                                break
                                                    if version_download_done:
                                                        input(f"Successfully downloaded version {version_id}!")
                elif c == "2":
                    folders = [f for f in VERSIONS_DIR.iterdir() if f.is_dir()]
                    print("Current version list (installed):")
                    c = 0
                    for i in folders:
                        print(f"{str(c)}: {i.name} ({str(i)})")
                        c += 1
                    if c == 0:
                        input("There are no versions downloaded yet")
                    else:
                        id = input("Select version to delete> ")
                        
                        if id == "b":
                            pass
                        elif not id.isdigit():
                            input("Unsupported input")
                        elif int(id) > c or int(id) < 0:
                            input("Unsupported input")
                        else:
                            version_name = Path(folders[int(id)]).name
                            version_path = (folders[int(id)])
                            try:
                                folder = version_path


                                for item in os.listdir(folder):
                                    path = os.path.join(folder, item)
                                    if os.path.isfile(path):
                                        os.remove(path)
                                    else:
                                        shutil.rmtree(path)
                                if folder.exists():
                                    shutil.rmtree(folder)
                                input(f"Seccessfully deleted {version_name}!")
                            except Exception as e:
                                input(f"Unable to delete version {version_name}! {str(e)}")


                elif c == "3":
                    folders = [f for f in VERSIONS_DIR.iterdir() if f.is_dir()]
                    print("Current version list (installed):")
                    c = 0
                    for i in folders:
                        print(f"{str(c)}: {i.name} ({str(i)})")
                        c += 1
                    if c == 0:
                        input("There are no versions downloaded yet")
                    else:
                        id = input("Select version> ")
                        
                        if id == "b":
                            pass
                        elif not id.isdigit():
                            input("Unsupported input")
                        elif int(id) > c or int(id) < 0:
                            input("Unsupported input")
                        else:
                            try:
                                version_name = Path(folders[int(id)]).name
                                version_path = (folders[int(id)])
                                json_path = Path(version_path / f"{version_name}.json")
                                configs["selected_version"]["path"] = str(version_path)
                                configs["selected_version"]["id"] = str(version_name)
                                configs["selected_version"]["json_path"] = str(json_path)
                                with open(LAUNCHER_CONFIG_PATH, "w") as f:
                                    json.dump(configs, f, indent = 4)
                                input("Success!")
                            except Exception as e:
                                print(f"Unable to save version: {str(e)}")
                elif c == "4":
                    folders = [f for f in VERSIONS_DIR.iterdir() if f.is_dir()]
                    print("Current version list (installed):")
                    c = 0
                    for i in folders:
                        print(f"{str(c)}: {i.name} ({str(i)})")
                        c += 1
                    if c == 0:
                        input("There are no versions downloaded yet")
                elif c == "b":
                    versions_running = False
                else:
                    input("Unrecognized input")
        elif c == "2":
            accounts_running = True
            while accounts_running:
                print("1: Add account")
                print("2: Delete account")
                print("3: Select account")
                print("4: List accounts")
                c = input("Main-Accounts > ")
                if c == "1":
                    account_name = input("Enter account name> ")
                    if not account_name == "b":
                        account = {"username": account_name, "online": False, "uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, account_name))}
                        for i in configs["accounts"]:
                            if i == account:
                                input("This account has already been added!")
                                break
                        else:
                            configs["accounts"].append(account)
                            with open(LAUNCHER_CONFIG_PATH, "w") as f:
                                json.dump(configs, f, indent = 4)
                            input("Success!")
                elif c == "2":
                    print("Current account list:")
                    c = 0
                    for i in configs["accounts"]:
                        if i["online"] == False:
                            online = "offline"
                        else:
                            online = "online"
                        print(f"{str(c)}: {i["username"]} ({online})")
                        c += 1
                    if c == 0:
                        input("There are no accounts yet")
                    else:
                        id = input("Select account to delete> ")
                        
                        if id == "b":
                            pass
                        elif not id.isdigit():
                            input("Unsupported input")
                        elif int(id) > c or int(id) < 0:
                            input("Unsupported input")
                        else:
                            c = 0
                            for i in configs["accounts"]:
                                if int(id) == c:
                                    username = i["username"]
                                    this_uuid = i["uuid"]
                                    online = i["online"]
                                c += 1
                            configs["accounts"].pop(int(id))
                            
                            if (not configs["selected_account"] == {}) and configs["selected_account"]["username"] == username and configs["selected_account"]["uuid"] == this_uuid and configs["selected_account"]["online"] == online:
                                configs["selected_account"] = {}
                            with open(LAUNCHER_CONFIG_PATH, "w") as f:
                                json.dump(configs, f, indent = 4)
                            input("Success!")
                elif c == "3":
                    print("Current account list:")
                    c = 0
                    for i in configs["accounts"]:
                        if i["online"] == False:
                            online = "offline"
                        else:
                            online = "online"
                        print(f"{str(c)}: {i["username"]} ({online})")
                        c += 1
                    if c == 0:
                        input("There are no accounts yet")
                    else:
                        id = input("Account id> ")
                        if id == "b":
                            pass
                        elif not id.isdigit():
                            input("Unsupported input")
                        elif int(id) > c:
                            input("Unsupported input")
                        else:
                            c = 0
                            for i in configs["accounts"]:
                                if int(id) == c:
                                    account = {"username": i["username"], "online": i["online"], "uuid": i["uuid"]}
                                c += 1
                            configs["selected_account"] = account
                            with open(LAUNCHER_CONFIG_PATH, "w") as f:
                                json.dump(configs, f, indent = 4)
                            input("Success!")
                elif c == "4":
                    print("Current account list:")
                    c = 0
                    for i in configs["accounts"]:
                        if i["online"] == False:
                            online = "offline"
                        else:
                            online = "online"
                        print(f"{str(c)}: {i["username"]} ({online})")
                        c += 1
                    if c == 0:
                        input("There are no accounts yet")
                    else:
                        input()
                    
                elif c == "b":
                    accounts_running = False
                else:
                    input("unrecognized input")
        elif c == "3":
            pass#settings
        elif c == "4":
            if (configs["selected_account"]["username"]) and (configs["selected_account"]["uuid"]) and (configs["selected_account"]["online"] != None) and (configs["selected_version"]["id"]) and (configs["selected_version"]["path"]) and (configs["selected_version"]["json_path"]):
                print(f"Launching version {configs["selected_version"]["id"]} with username {configs["selected_account"]["username"]}")
                version_path = configs["selected_version"]["path"]
                account = configs["selected_account"]
                json_path = configs["selected_version"]["json_path"]
                with open(json_path) as json_file:
                    json_data = json.load(json_file)
                    main_class = json_data["mainClass"]
                    min_java = json_data["javaVersion"]["majorVersion"]
                    current_version = get_java_major()
                    print(current_version)
                    if int(current_version) != int(min_java):
                        local_java = find_local_java(int(min_java), JAVA_BASE_DIR)
                        if local_java:
                            pass
                            #####run local_java
                        else:
                            go = False
                            if sys.platform.startswith("win"):
                                computer_platform = "windows"
                                go = True
                            elif sys.platform == "darwin":
                                computer_platform = "mac"
                                go = True
                            elif sys.platform.startswith("linux"):
                                computer_platform = "linux"
                                go = True
                            else:
                                computer_platform = "unknown"
                                input("Platform not supported")
                                go = False
                            if go:
                                print(f"Downloading Java version {min_java}")
                                download_dir = JAVA_BASE_DIR
                                archive_name = "java.zip" if computer_platform == "windows" else "java.tar.gz"
                                archive_path = download_dir / archive_name
                                target_dir = JAVA_BASE_DIR / "runtime"
                                try:
                                    urllib.request.urlretrieve(url, archive_path)
                                    print("Download complete")
                                    print(f"Extracting java in {archive_path}")
                                    try:
                                        target_dir.mkdir(parents=True, exist_ok=True)

                                        if archive_path.suffix == ".zip":
                                            with zipfile.ZipFile(archive_path, "r") as z:
                                                z.extractall(target_dir)
                                        else:
                                            with tarfile.open(archive_path, "r:*") as t:
                                                t.extractall(target_dir)
                                        input(f"Successfully installed java version {min_java} in {target_dir}")
                                        print(f"Launching Minecraft version {configs["selected_version"]["id"]} with local java version {min_java} in {target_dir}. YOU CAN CONFIGURE FEATURES IN SETTINGS!!")
                                        local_java_installed = find_local_java(int(min_java), JAVA_BASE_DIR)
                                        if not local_java_installed:
                                            input("Unable to find java")
                                        else:
                                            try:
                                                arguments = json_data["arguments"]
                                            except Exception:
                                                arguments = json_data["minecraftArguments"]["game"]
                                            main_class = json_data["mainClass"]
                                        
                                            variables = {
                                                "auth_player_name": configs["selected_account"]["username"],
                                                "auth_uuid": configs["selected_account"]["uuid"],
                                                "auth_access_token": 0, #
                                                "version_name": json_data["id"],
                                                "version_type": json_data["type"],
                                                "game_directory": BASE_DIR,
                                                "assets_root": ASSETS_DIR,
                                                "assets_index_name": json_data.get("assetIndex", {}).get("id", ""),
                                                "classpath": build_classpath(version_json), # we can auto-generate from libraries
                                                "launcher_name": "MyLauncher",
                                                "launcher_version": "1.0",
                                                # optional features
                                                "resolution_width": configs["features"]["resolution_width"],
                                                "resolution_height": configs["features"]["resolution_height"],
                                                "quickPlayPath": configs["features"]["quick_play_path"],
                                                "quickPlaySingleplayer": configs["features"]["quick_play_singleplayer"],
                                                "quickPlayMultiplayer": configs["features"]["quick_play_multiplayer"],
                                                "quickPlayRealms": configs["features"]["quick_play_realms"],
                                                }

                                    except Exception as e:
                                        input(f"Unable to extract java from {archive_path}: {str(e)}")
                                except Exception as e:
                                    input(f"Unable to download java version {min_java}: {str(e)}")
                    else:
                        pass#run java

            else:
                input("Unable to launch, either no account selected or no version selected.")
        else:
            input("unrecognized input")
