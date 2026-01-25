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
                        ###############






                        
                elif c == "2":
                    pass#delete
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
                        elif int(id) > c:
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
