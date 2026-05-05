import os
import re
import json
import subprocess
import requests
import sys
import tty
import termios

from requests.auth import HTTPDigestAuth

# =====================================================
# CORES ANSI
# =====================================================

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

# =====================================================
# INPUT COM ASTERISCOS
# =====================================================

def getpass_with_asterisks(prompt="Password: "):
    print(prompt, end="", flush=True)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        password = ""

        while True:
            ch = sys.stdin.read(1)

            if ch in ("\n", "\r"):
                print()
                break

            elif ch == "\x7f":
                if len(password) > 0:
                    password = password[:-1]
                    print("\b \b", end="", flush=True)

            else:
                password += ch
                print("*", end="", flush=True)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return password

# =====================================================
# AUTH DINÂMICO
# =====================================================

print(f"\n{CYAN}=== AUTENTICAÇÃO ATLAS ==={RESET}")

PUBLIC_KEY = input("Public Key: ").strip()
PRIVATE_KEY = getpass_with_asterisks("Private Key: ")

BASE_URL = "https://cloud.mongodb.com/api/atlas/v1.0"

AUTH = HTTPDigestAuth(
    PUBLIC_KEY,
    PRIVATE_KEY
)

# =====================================================
# 🔥 NOVO: INPUT PATH DINÂMICO
# =====================================================

print(f"\n{CYAN}=== CONFIGURAÇÃO DE PATH ==={RESET}")

default_path = "/home/ec2-user/realm_exports"

user_path = input(
    f"Caminho dos exports realm-cli [Enter = {default_path}]: "
).strip()

REALM_EXPORT_BASE = user_path if user_path else default_path

if not os.path.exists(REALM_EXPORT_BASE):
    print(f"{RED}ERRO{RESET} - Caminho não encontrado:")
    print(REALM_EXPORT_BASE)
    exit(1)

print(f"{GREEN}OK{RESET} - Usando path:")
print(REALM_EXPORT_BASE)

# =====================================================
# CONFIG
# =====================================================

OUTPUT_FILE = "atlas_auto_assessment.json"

# =====================================================
# AUX
# =====================================================

def get(url):
    return requests.get(url, auth=AUTH)

# =====================================================
# MAP APP -> PROJECT (MANTIDO IGUAL)
# =====================================================

APP_PROJECT_MAP = {

    "5c893a855538555c636b3621":
        "5c893a855538555c636b3621",

    "69efbf887b99091ecf86face":
        "69efbf630bf262a89b8aa0c5"
}

# =====================================================
# LISTAR APPS REALM-CLI
# =====================================================

print(f"{YELLOW}Listando apps realm-cli...{RESET}")

apps_result = subprocess.run(
    ["realm-cli", "app", "list"],
    capture_output=True,
    text=True
)

if apps_result.returncode != 0:
    print(f"{RED}ERRO{RESET} ao listar apps")
    print(apps_result.stderr)
    exit(1)

pattern = r"(.+?)\s+\(([a-f0-9]+)\)"
apps = re.findall(pattern, apps_result.stdout)

print(f"{GREEN}OK{RESET} - {len(apps)} app(s)")

# =====================================================
# LISTAR PROJETOS
# =====================================================

print(f"\n{YELLOW}Listando projetos Atlas...{RESET}")

projects_resp = get(f"{BASE_URL}/groups")

if projects_resp.status_code != 200:
    print(f"{RED}ERRO{RESET} ao listar projetos")
    print(projects_resp.text)
    exit(1)

atlas_projects = projects_resp.json().get("results", [])

print(f"{GREEN}OK{RESET} - {len(atlas_projects)} projeto(s)")

# =====================================================
# PROCESSAMENTO
# =====================================================

final_output = {"projects": []}

for project in atlas_projects:

    PROJECT_ID = project.get("id")
    PROJECT_NAME = project.get("name")

    print(f"\n{CYAN}Projeto:{RESET} {PROJECT_NAME}")
    print(f"{CYAN}Project ID:{RESET} {PROJECT_ID}")

    assessment = {
        "project_name": PROJECT_NAME,
        "project_id": PROJECT_ID,
        "infrastructure": {
            "clusters": [],
            "data_federation_enabled": False,
            "private_endpoints_enabled": False
        },
        "app_services": {
            "apps": []
        }
    }

    # ================= CLUSTERS =================

    print(f"{YELLOW}Coletando clusters...{RESET}")

    resp = get(f"{BASE_URL}/groups/{PROJECT_ID}/clusters")

    if resp.status_code == 200:

        clusters = resp.json().get("results", [])

        print(f"{GREEN}OK{RESET} - {len(clusters)} cluster(s)")

        for c in clusters:

            assessment["infrastructure"]["clusters"].append({

                "cluster_name": c.get("name"),
                "provider": c.get("providerSettings", {}).get("providerName"),
                "cluster_type": c.get("clusterType"),
                "instance_size": c.get("providerSettings", {}).get("instanceSizeName"),
                "mongo_version": c.get("mongoDBVersion"),
                "serverless": c.get("clusterType") == "SERVERLESS",
                "backup_continuous": c.get("cloudBackup", False),
                "encryption_at_rest": c.get("encryptionAtRestProvider") is not None
            })

    # ================= APPS =================

    print(f"{YELLOW}Lendo exports realm-cli...{RESET}")

    for app_name, app_id in apps:

        if APP_PROJECT_MAP.get(app_id) != PROJECT_ID:
            continue

        export_path = os.path.join(
            REALM_EXPORT_BASE,
            app_id,
            "Triggers"
        )

        if not os.path.exists(export_path):
            continue

        print(f"{GREEN}OK{RESET} - App encontrado: {app_name}")

        app_info = {
            "app_name": app_name,
            "app_id": app_id,
            "triggers": [],
            "data_sources": []
        }

        # ================= FUNCTIONS =================

        functions_map = {}

        functions_path = os.path.join(export_path, "functions")

        if os.path.exists(functions_path):

            for file in os.listdir(functions_path):

                if not file.endswith(".js"):
                    continue

                content = open(os.path.join(functions_path, file)).read()

                name = file.replace(".js", "")

                functions_map[name] = {
                    "uses_http": "http" in content,
                    "uses_collection": ".collection(" in content,
                    "code_size": len(content)
                }

        # ================= TRIGGERS =================

        triggers_path = os.path.join(export_path, "triggers")

        if os.path.exists(triggers_path):

            for file in os.listdir(triggers_path):

                if not file.endswith(".json"):
                    continue

                data = json.load(open(os.path.join(triggers_path, file)))
                triggers = data if isinstance(data, list) else [data]

                for t in triggers:

                    func = (
                        t.get("event_processors", {})
                        .get("FUNCTION", {})
                        .get("config", {})
                        .get("function_name")
                    )

                    app_info["triggers"].append({

                        "trigger_name": t.get("name"),
                        "type": t.get("type"),
                        "database": t.get("config", {}).get("database"),
                        "collection": t.get("config", {}).get("collection"),
                        "operations": t.get("config", {}).get("operation_types", []),
                        "disabled": t.get("disabled"),
                        "function": func,
                        "function_analysis": functions_map.get(func, {})
                    })

        assessment["app_services"]["apps"].append(app_info)

    final_output["projects"].append(assessment)

# =====================================================
# SAVE
# =====================================================

print(f"\n{YELLOW}Gerando output consolidado...{RESET}")

with open(OUTPUT_FILE, "w") as f:
    json.dump(final_output, f, indent=4)

print(f"{GREEN}OK{RESET} - Arquivo gerado:")
print(os.path.abspath(OUTPUT_FILE))
