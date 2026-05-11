import os
import re
import json
import shutil
import subprocess
import requests
import pandas as pd
import sys
import tty
import termios
import pexpect

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
# PASSWORD MASK
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

        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings
        )

    return password

# =====================================================
# INPUTS
# =====================================================

default_export = "/home/ec2-user/realm_exports"

BASE_EXPORT_DIR = input(
    f"Informe o BASE_EXPORT_DIR "
    f"[default: {default_export}]: "
).strip()

if not BASE_EXPORT_DIR:

    BASE_EXPORT_DIR = default_export

print(f"\n{CYAN}=== REALM EXPORT PIPELINE ==={RESET}")

PUBLIC_KEY = input("Public Key: ").strip()

PRIVATE_KEY = getpass_with_asterisks(
    "Private Key: "
)

# =====================================================
# URLS
# =====================================================

ATLAS_BASE_URL = (
    "https://cloud.mongodb.com/api/atlas/v1.0"
)

OUTPUT_JSON = "atlas_exec_assessment.json"

OUTPUT_XLSX = "atlas_exec_assessment.xlsx"

# =====================================================
# AUTH
# =====================================================

ATLAS_AUTH = HTTPDigestAuth(
    PUBLIC_KEY,
    PRIVATE_KEY
)

# =====================================================
# AUX
# =====================================================

def atlas_get(url):

    return requests.get(
        url,
        auth=ATLAS_AUTH
    )

# =====================================================
# VALIDAR SESSION
# =====================================================

print(
    f"\n{YELLOW}Validando sessão realm-cli...{RESET}"
)

session = subprocess.run(
    ["realm-cli", "app", "list"],
    capture_output=True,
    text=True
)

if session.returncode != 0:

    print(
        f"{RED}Sessão inválida{RESET}"
    )

    print(
        f"{YELLOW}Execute realm-cli login{RESET}"
    )

    exit(1)

print(
    f"{GREEN}OK{RESET} - Sessão válida"
)

# =====================================================
# LISTAR APPS
# =====================================================

print(
    f"\n{YELLOW}Listando apps...{RESET}"
)

result = subprocess.run(
    ["realm-cli", "app", "list"],
    capture_output=True,
    text=True
)

pattern = r"(.+?)\s+\(([a-f0-9]+)\)"

apps = re.findall(
    pattern,
    result.stdout
)

print(
    f"{GREEN}OK{RESET} - "
    f"{len(apps)} app(s)"
)

if not apps:

    print(
        f"{RED}Nenhum app encontrado{RESET}"
    )

    exit(1)

# =====================================================
# APP -> PROJECT MAP
# =====================================================

APP_PROJECT_MAP = {

    "triggers-hbudeor":
        "Project Data",

    "triggers-fljovwi":
        "Conversion Project",

    "triggers-iffrsrt":
        "Project Teste"
}


# =====================================================
# CREATE EXPORT BASE
# =====================================================

os.makedirs(
    BASE_EXPORT_DIR,
    exist_ok=True
)

# =====================================================
# EXPORT APPS
# =====================================================

print(
    f"\n{CYAN}=== EXPORTANDO APPS ==={RESET}"
)

for app_name, app_id in apps:

    app_name = app_name.strip()

    print(
        f"\n{YELLOW}App:{RESET} "
        f"{app_name}"
    )

    print(
        f"{CYAN}App ID:{RESET} "
        f"{app_id}"
    )

    export_dir = os.path.join(
        BASE_EXPORT_DIR,
        app_id
    )

    if os.path.exists(export_dir):

        shutil.rmtree(export_dir)

    os.makedirs(export_dir)

    try:

        os.chdir(export_dir)

        child = pexpect.spawn(
            "realm-cli pull",
            encoding="utf-8",
            timeout=300
        )

        child.logfile = sys.stdout

        child.expect("Atlas Project")

        project_name = APP_PROJECT_MAP.get(
            app_name
        )

        if not project_name:

            print(
                f"{RED}Projeto não mapeado{RESET}"
            )

            continue

        child.send(project_name)
        child.sendline("")

        child.expect("Scaning Project")

        child.send(app_name)
        child.sendline("")

        child.expect(pexpect.EOF)

        print(
            f"{GREEN}✔ Export concluído{RESET}"
        )

    except Exception as e:

        print(
            f"{RED}ERRO export{RESET}"
        )

        print(str(e))

# =====================================================
# RESET DIR
# =====================================================

os.chdir(
    os.path.expanduser("~")
)

# =====================================================
# LISTAR PROJETOS
# =====================================================

print(
    f"\n{YELLOW}Listando projetos Atlas...{RESET}"
)

projects_resp = atlas_get(
    f"{ATLAS_BASE_URL}/groups"
)

projects = projects_resp.json().get(
    "results",
    []
)

print(
    f"{GREEN}OK{RESET} - "
    f"{len(projects)} projeto(s)"
)

# =====================================================
# OUTPUT
# =====================================================

final_output = {
    "projects": []
}

summary_rows = []
cluster_rows = []
trigger_rows = []

# =====================================================
# LOOP PROJETOS
# =====================================================

for project in projects:

    PROJECT_ID = project.get("id")

    PROJECT_NAME = project.get("name")

    print(
        f"\n{CYAN}Projeto:{RESET} "
        f"{PROJECT_NAME}"
    )

    print(
        f"{CYAN}Project ID:{RESET} "
        f"{PROJECT_ID}"
    )

    assessment = {

        "project_name":
            PROJECT_NAME,

        "project_id":
            PROJECT_ID,

        "infrastructure": {
            "clusters": []
        },

        "app_services": {
            "apps": []
        }
    }

    # =================================================
    # CLUSTERS
    # =================================================

    print(
        f"{YELLOW}Coletando clusters...{RESET}"
    )

    cluster_resp = atlas_get(
        f"{ATLAS_BASE_URL}/groups/"
        f"{PROJECT_ID}/clusters"
    )

    clusters = []

    if cluster_resp.status_code == 200:

        clusters = cluster_resp.json().get(
            "results",
            []
        )

    print(
        f"{GREEN}OK{RESET} - "
        f"{len(clusters)} cluster(s)"
    )

    for c in clusters:

        cluster_name = c.get("name")

        # =============================================
        # ONLINE ARCHIVE
        # =============================================

        has_online_archive = False

        try:

            archive_resp = atlas_get(
                f"{ATLAS_BASE_URL}/groups/"
                f"{PROJECT_ID}/clusters/"
                f"{cluster_name}/onlineArchives"
            )

            if archive_resp.status_code == 200:

                archive_results = archive_resp.json().get(
                    "results",
                    []
                )

                if len(archive_results) > 0:

                    has_online_archive = True

        except:
            pass

        # =============================================
        # ATLAS SEARCH
        # =============================================

        has_atlas_search = False

        try:

            search_resp = atlas_get(
                f"{ATLAS_BASE_URL}/groups/"
                f"{PROJECT_ID}/clusters/"
                f"{cluster_name}/fts/indexes/*/*"
            )

            if search_resp.status_code == 200:

                try:

                    search_results = search_resp.json()

                    if isinstance(search_results, list):

                        if len(search_results) > 0:

                            has_atlas_search = True

                    elif isinstance(search_results, dict):

                        if len(search_results.keys()) > 0:

                            has_atlas_search = True

                except:
                    pass

        except:
            pass

        cluster_obj = {

            "cluster_name":
                cluster_name,

            "provider":
                c.get(
                    "providerSettings",
                    {}
                ).get(
                    "providerName"
                ),

            "cluster_type":
                c.get("clusterType"),

            "instance_size":
                c.get(
                    "providerSettings",
                    {}
                ).get(
                    "instanceSizeName"
                ),

            "mongo_version":
                c.get("mongoDBVersion"),

            "serverless":
                (
                    c.get("clusterType")
                    == "SERVERLESS"
                ),

            "backup":
                c.get(
                    "cloudBackup",
                    False
                ),

            "online_archive":
                has_online_archive,

            "atlas_search":
                has_atlas_search
        }

        assessment["infrastructure"][
            "clusters"
        ].append(cluster_obj)

        cluster_rows.append({

            "project_name":
                PROJECT_NAME,

            "project_id":
                PROJECT_ID,

            **cluster_obj
        })

        print(
            f"   Cluster: {cluster_name}"
        )

        print(
            f"   Online Archive: "
            f"{has_online_archive}"
        )

        print(
            f"   Atlas Search: "
            f"{has_atlas_search}"
        )

    # =================================================
    # APPS / TRIGGERS
    # =================================================

    print(
        f"{YELLOW}Lendo exports realm-cli...{RESET}"
    )

    total_triggers = 0

    for app_name, app_id in apps:

        app_name = app_name.strip()

        mapped_project_name = APP_PROJECT_MAP.get(
            app_name
        )

        if mapped_project_name != PROJECT_NAME:
            continue

        app_dir = os.path.join(
            BASE_EXPORT_DIR,
            app_id
        )

        if not os.path.exists(app_dir):
            continue

        print(
            f"{GREEN}OK{RESET} - "
            f"App encontrado: "
            f"{app_name}"
        )

        app_obj = {

            "app_name":
                app_name,

            "app_id":
                app_id,

            "triggers":
                []
        }

        real_trigger_dir = os.path.join(
            app_dir,
            "Triggers",
            "triggers"
        )

        if not os.path.exists(real_trigger_dir):

            real_trigger_dir = os.path.join(
                app_dir,
                "triggers"
            )

        if not os.path.exists(real_trigger_dir):

            print(
                f"{RED}Diretório real de triggers não encontrado{RESET}"
            )

            continue

        trigger_count = 0

        for file in os.listdir(real_trigger_dir):

            if not file.endswith(".json"):
                continue

            file_path = os.path.join(
                real_trigger_dir,
                file
            )

            try:

                with open(file_path) as f:

                    data = json.load(f)

                trigger_name = data.get(
                    "name"
                )

                trigger_type = data.get(
                    "type"
                )

                config_data = data.get(
                    "config",
                    {}
                )

                event_processors = data.get(
                    "event_processors",
                    {}
                )

                function_name = (
                    event_processors
                    .get("FUNCTION", {})
                    .get("config", {})
                    .get("function_name")
                )

                operation_types = config_data.get(
                    "operation_types",
                    []
                )

                database = config_data.get(
                    "database"
                )

                collection = config_data.get(
                    "collection"
                )

                service_name = config_data.get(
                    "service_name"
                )

                disabled = data.get(
                    "disabled"
                )

                print(
                    f"{CYAN}   → Trigger:{RESET} "
                    f"{trigger_name}"
                )

                print(
                    f"      Type: {trigger_type}"
                )

                print(
                    f"      Function: {function_name}"
                )

                print(
                    f"      Database: {database}"
                )

                print(
                    f"      Collection: {collection}"
                )

                print(
                    f"      Operations: "
                    f"{','.join(operation_types)}"
                )

                trigger_obj = {

                    "trigger_name":
                        trigger_name,

                    "type":
                        trigger_type,

                    "function_name":
                        function_name,

                    "service_name":
                        service_name,

                    "database":
                        database,

                    "collection":
                        collection,

                    "operation_types":
                        operation_types,

                    "disabled":
                        disabled
                }

                app_obj["triggers"].append(
                    trigger_obj
                )

                trigger_rows.append({

                    "project_name":
                        PROJECT_NAME,

                    "project_id":
                        PROJECT_ID,

                    "app_name":
                        app_name,

                    "app_id":
                        app_id,

                    **trigger_obj
                })

                trigger_count += 1
                total_triggers += 1

            except Exception as e:

                print(
                    f"{RED}Erro lendo trigger:{RESET} "
                    f"{file}"
                )

                print(str(e))

        print(
            f"{CYAN}   → Total Triggers:{RESET} "
            f"{trigger_count}"
        )

        assessment["app_services"][
            "apps"
        ].append(app_obj)

    summary_rows.append({

        "project_name":
            PROJECT_NAME,

        "project_id":
            PROJECT_ID,

        "total_clusters":
            len(clusters),

        "total_apps":
            len(
                assessment["app_services"]["apps"]
            ),

        "total_triggers":
            total_triggers,

        "total_archive":
            sum(
                1 for c in assessment["infrastructure"]["clusters"]
                if c.get("online_archive")
            ),

        "total_atlassearch":
            sum(
                1 for c in assessment["infrastructure"]["clusters"]
                if c.get("atlas_search")
            )
    })

    final_output["projects"].append(
        assessment
    )

# =====================================================
# SAVE JSON
# =====================================================

print(
    f"\n{YELLOW}Gerando output consolidado...{RESET}"
)

json_path = os.path.join(
    BASE_EXPORT_DIR,
    OUTPUT_JSON
)

with open(
    json_path,
    "w"
) as f:

    json.dump(
        final_output,
        f,
        indent=4
    )

print(
    f"{GREEN}OK{RESET} - JSON gerado:"
)

print(json_path)

# =====================================================
# SAVE EXCEL
# =====================================================

print(
    f"\n{YELLOW}Gerando Excel...{RESET}"
)

excel_path = os.path.join(
    BASE_EXPORT_DIR,
    OUTPUT_XLSX
)

with pd.ExcelWriter(
    excel_path,
    engine="openpyxl"
) as writer:

    pd.DataFrame(
        summary_rows
    ).to_excel(
        writer,
        sheet_name="Summary",
        index=False
    )

    pd.DataFrame(
        cluster_rows
    ).to_excel(
        writer,
        sheet_name="Clusters",
        index=False
    )

    pd.DataFrame(
        trigger_rows
    ).to_excel(
        writer,
        sheet_name="Triggers",
        index=False
    )

print(
    f"{GREEN}OK{RESET} - Excel gerado:"
)

print(excel_path)

print(
    f"\n{GREEN}Pipeline finalizado{RESET}"
)
