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


ssl._create_default_https_context = ssl._create_unverified_context

BASE_DIR = Path("mc")
VERSIONS_DIR = BASE_DIR / "versions"
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"

LAUNCHER_CONFIG_PATH = Path(BASE_DIR / "launcher_config.json")
DEFAULT_CONFIG = {
    "manifest_url": "https://piston-meta.mojang.com/mc/game/version_manifest.json",
    "java_cmd": "java",
    "max_ram": "4G",
    "accounts": [],
    "current_account": {"username": None, "online": None, "uuid": None},
    "version_display": {"old_alpha": True, "old_beta": True, "snapshot": True, "release": True}
}

MC_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
JAVA_CMD = "java"
MAX_RAM = "2G"

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
    print("Welcome to PML -- Python Minecraft Launcher by ItsMrEric")
    print("You can input stuff when you see \">\". The text behind it shows the current page")
    print("Input \"b\" to return (go back)")
    print("Ensuring dirs......")
    ensure_dirs()
    print("Reading configs......" )
    configs = load_or_fix_json(LAUNCHER_CONFIG_PATH, DEFAULT_CONFIG)
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
                                            with open(asset_index_path) as asset_index_file:
                                                print("Downloading assets (this is going to be slow though =D)")
                                                assets_index_data = json.load(asset_index_file)
                                                go_libraries = True
                                                for asset_name, asset_data in assets_index_data["objects"].items():
                                                    print("Total files: {}")
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
                                                        
                                                    except Exception as e:
                                                        input(f"Unable to download (asset) {asset_name}: {str(e)}")
                                                        go_libraries = False
                                                        break
                                                if go_libraries:
                                                    print("Done")
                                                    print("Checking & downloading libraries")
                                                    version_download_done = True
                                                    for library_data in json_data["libraries"]:
                                                        library_path = Path(library_data["downloads"]["artifact"]["path"])
                                                        if library_path.exists():
                                                            print(f"Library: {str(library_path)} already exists, skipping......")
                                                        else:
                                                            print(f"Downloading library: {str(library_path)}")
                                                            library_url = library_data["downloads"]["artifact"]["url"]
                                                            try:
                                                                urllib.request.urlretrieve(library_url, library_path)
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


                        #################################################################
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

                            ####################################################################

                elif c == "3":
                    pass#select
                elif c == "4":
                    pass#list
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
                            
                            if (not configs["current_account"] == {}) and configs["current_account"]["username"] == username and configs["current_account"]["uuid"] == this_uuid and configs["current_account"]["online"] == online:
                                configs["current_account"] = {}
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
                            configs["current_account"] = account
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
            pass#launch
        else:
            input("unrecognized input")
