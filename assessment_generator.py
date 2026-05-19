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

from datetime import datetime
from pymongo import MongoClient
from requests.auth import HTTPDigestAuth

# =====================================================
# ANSI COLORS
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

default_export = os.path.join(
    os.path.expanduser("~"),
    "mongodbatlas_assessment_outputs"
)

BASE_EXPORT_DIR = input(
    f"Inform the BASE_EXPORT_DIR "
    f"[default: {default_export}]: "
).strip()

if not BASE_EXPORT_DIR:
    BASE_EXPORT_DIR = default_export

os.makedirs(BASE_EXPORT_DIR, exist_ok=True)

OUTPUT_JSON = "atlas_exec_assessment.json"
OUTPUT_XLSX = "atlas_exec_assessment.xlsx"

LOG_FILE = os.path.join(
    BASE_EXPORT_DIR,
    "assessment.log"
)

# =====================================================
# LOG
# =====================================================

def log(msg):

    print(msg)

    with open(LOG_FILE, "a") as f:

        clean_msg = re.sub(
            r'\033\[[0-9;]*m',
            '',
            msg
        )

        f.write(clean_msg + "\n")

# =====================================================
# START
# =====================================================

log(f"\n{CYAN}=== REALM EXPORT PIPELINE ==={RESET}")

# =====================================================
# CHECK REALM-CLI
# =====================================================

log(
    f"\n{YELLOW}Checking realm-cli version...{RESET}"
)

try:

    version = subprocess.run(
        ["realm-cli", "--version"],
        capture_output=True,
        text=True
    )

    if version.returncode != 0:

        log(
            f"{RED}realm-cli not installed{RESET}"
        )

        sys.exit(1)

    log(
        f"{GREEN}OK{RESET} - "
        f"{version.stdout.strip()}"
    )

except Exception as e:

    log(
        f"{RED}realm-cli validation failed:{RESET} "
        f"{str(e)}"
    )

    sys.exit(1)

# =====================================================
# INPUT CREDS
# =====================================================

PUBLIC_KEY = input(
    "Public Key: "
).strip()

PRIVATE_KEY = getpass_with_asterisks(
    "Private Key: "
)

# =====================================================
# CLEAN SESSION
# =====================================================

log(
    f"\n{YELLOW}Cleaning previous realm-cli session...{RESET}"
)

try:

    subprocess.run(
        ["realm-cli", "logout"],
        capture_output=True,
        text=True
    )

except:
    pass

# =====================================================
# LOGIN
# =====================================================

log(
    f"\n{YELLOW}Authenticating realm-cli...{RESET}"
)

try:

    login_cmd = [
        "realm-cli",
        "login",
        f"--api-key={PUBLIC_KEY}",
        f"--private-api-key={PRIVATE_KEY}"
    ]

    login = subprocess.run(
        login_cmd,
        capture_output=True,
        text=True,
        timeout=120
    )

    if login.returncode != 0:

        log(
            f"{RED}realm-cli authentication failed{RESET}"
        )

        log(login.stderr)

        sys.exit(1)

    log(
        f"{GREEN}OK{RESET} - realm-cli authenticated"
    )

except subprocess.TimeoutExpired:

    log(
        f"{RED}Timeout during realm-cli login{RESET}"
    )

    sys.exit(1)

# =====================================================
# VALIDATE SESSION
# =====================================================

log(
    f"\n{YELLOW}Validating realm-cli session...{RESET}"
)

whoami = subprocess.run(
    ["realm-cli", "whoami"],
    capture_output=True,
    text=True
)

if whoami.returncode != 0:

    log(
        f"{RED}Invalid realm-cli session{RESET}"
    )

    sys.exit(1)

log(
    f"{GREEN}OK{RESET} - Valid session"
)

# =====================================================
# ATLAS URLS
# =====================================================

ATLAS_BASE_URL_V1 = (
    "https://cloud.mongodb.com/api/atlas/v1.0"
)

ATLAS_BASE_URL_V2 = (
    "https://cloud.mongodb.com/api/atlas/v2"
)

# =====================================================
# AUTH
# =====================================================

ATLAS_AUTH = HTTPDigestAuth(
    PUBLIC_KEY,
    PRIVATE_KEY
)

# =====================================================
# REQUEST AUX
# =====================================================

def atlas_get(url):

    try:

        response = requests.get(
            url,
            auth=ATLAS_AUTH,
            timeout=30
        )

        return response

    except Exception as e:

        log(
            f"{RED}Request failed:{RESET} "
            f"{url}"
        )

        log(str(e))

        return None

# =====================================================
# VALIDATE API
# =====================================================

log(
    f"\n{YELLOW}Validating Atlas API...{RESET}"
)

validate = atlas_get(
    f"{ATLAS_BASE_URL_V1}/groups"
)

if not validate:

    log(
        f"{RED}Atlas API validation failed{RESET}"
    )

    sys.exit(1)

if validate.status_code != 200:

    log(
        f"{RED}Atlas API authentication failed{RESET}"
    )

    log(validate.text)

    sys.exit(1)

log(
    f"{GREEN}OK{RESET} - Atlas API authenticated"
)

# =====================================================
# LIST APPS
# =====================================================

log(
    f"\n{YELLOW}Listing realm-cli apps...{RESET}"
)

result = subprocess.run(
    ["realm-cli", "app", "list"],
    capture_output=True,
    text=True
)

pattern = r"(.+?)\s+\(([a-f0-9]+)\)"

apps_cli = re.findall(
    pattern,
    result.stdout
)

apps = []

log(
    f"{GREEN}OK{RESET} - "
    f"{len(apps_cli)} app(s)"
)

# =====================================================
# MAP APPS
# =====================================================

log(
    f"\n{YELLOW}Mapping apps to projects...{RESET}"
)

APP_PROJECT_MAP = {}

projects_for_map_resp = atlas_get(
    f"{ATLAS_BASE_URL_V1}/groups"
)

projects_for_map = projects_for_map_resp.json().get(
    "results",
    []
)

for _proj in projects_for_map:

    _proj_id = _proj.get("id")
    _proj_name = _proj.get("name")

    _result = subprocess.run(
        [
            "realm-cli",
            "app",
            "list",
            "--project",
            _proj_id
        ],
        capture_output=True,
        text=True
    )

    _proj_apps = re.findall(
        pattern,
        _result.stdout
    )

    for _app_name, _app_id in _proj_apps:

        _app_name = _app_name.strip()

        APP_PROJECT_MAP[_app_name] = _proj_name

        apps.append(
            (_app_name, _app_id)
        )

log(
    f"{GREEN}OK{RESET} - "
    f"{len(APP_PROJECT_MAP)} app(s) mapped"
)

# =====================================================
# EXPORT APPS
# =====================================================

trigger_rows = []

if apps:

    log(
        f"\n{CYAN}=== EXPORTING APPS ==={RESET}"
    )

    for app_name, app_id in apps:

        app_name = app_name.strip()

        log(
            f"\n{YELLOW}App:{RESET} "
            f"{app_name}"
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

            child.expect("Atlas Project")

            project_name = APP_PROJECT_MAP.get(
                app_name
            )

            child.send(project_name)
            child.sendline("")

            child.expect("Use arrows to move")

            child.send(app_name)
            child.sendline("")

            child.expect(pexpect.EOF)

            log(
                f"{GREEN}OK{RESET} - Export completed"
            )

        except Exception as e:

            log(
                f"{RED}Export ERROR{RESET}"
            )

            log(str(e))

# =====================================================
# RESET DIR
# =====================================================

os.chdir(
    os.path.expanduser("~")
)

# =====================================================
# LIST PROJECTS
# =====================================================

log(
    f"\n{YELLOW}Listing Atlas Projects...{RESET}"
)

projects_resp = atlas_get(
    f"{ATLAS_BASE_URL_V1}/groups"
)

projects = projects_resp.json().get(
    "results",
    []
)

log(
    f"{GREEN}OK{RESET} - "
    f"{len(projects)} project(s)"
)

# =====================================================
# OUTPUT STRUCTURES
# =====================================================

final_output = {
    "generated_at": str(datetime.utcnow()),
    "projects": []
}

summary_rows = []
cluster_rows = []

# =====================================================
# PROJECT LOOP
# =====================================================

for project in projects:

    PROJECT_ID = project.get("id")
    PROJECT_NAME = project.get("name")

    log(
        f"\n{CYAN}Project:{RESET} "
        f"{PROJECT_NAME}"
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

    log(
        f"{YELLOW}Collecting clusters...{RESET}"
    )

    cluster_resp = atlas_get(
        f"{ATLAS_BASE_URL_V1}/groups/"
        f"{PROJECT_ID}/clusters"
    )

    clusters = []

    if cluster_resp and cluster_resp.status_code == 200:

        clusters = cluster_resp.json().get(
            "results",
            []
        )

    log(
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
                f"{ATLAS_BASE_URL_V1}/groups/"
                f"{PROJECT_ID}/clusters/"
                f"{cluster_name}/onlineArchives"
            )

            if archive_resp:

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
        # SEARCH / VECTOR
        # =============================================

        has_atlas_search = False
        has_vector_search = False
        vector_indexes = 0

        try:

            mongo_uri = input(
                f"\nMongo URI for cluster "
                f"{cluster_name} "
                f"(ENTER to skip): "
            ).strip()

            if mongo_uri:

                client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=5000
                )

                dbs = client.list_database_names()

                for db_name in dbs:

                    if db_name in [
                        "admin",
                        "local",
                        "config"
                    ]:
                        continue

                    db = client[db_name]

                    collections = db.list_collection_names()

                    for coll_name in collections:

                        try:

                            idx_list = list(
                                db[coll_name].aggregate([
                                    {
                                        "$listSearchIndexes": {}
                                    }
                                ])
                            )

                            if len(idx_list) > 0:

                                has_atlas_search = True

                            for idx in idx_list:

                                idx_type = str(
                                    idx.get("type", "")
                                ).lower()

                                if idx_type in [
                                    "search",
                                    "lucene"
                                ]:

                                    has_atlas_search = True

                                if idx_type in [
                                    "vectorsearch",
                                    "vector"
                                ]:

                                    has_vector_search = True
                                    vector_indexes += 1

                        except:
                            pass

        except Exception as e:

            log(
                f"{RED}Mongo inspection ERROR:{RESET}"
            )

            log(str(e))

        disk_size_gb = c.get(
            "diskSizeGB",
            0
        )

        log(
            f"   Cluster: {cluster_name}"
        )

        log(
            f"   Online Archive: "
            f"{has_online_archive}"
        )

        log(
            f"   Atlas Search: "
            f"{has_atlas_search}"
        )

        log(
            f"   Vector Search: "
            f"{has_vector_search}"
        )

        log(
            f"   Vector Indexes: "
            f"{vector_indexes}"
        )

        log(
            f"   Disk Size GB: "
            f"{disk_size_gb}"
        )

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
                str(
                    c.get("clusterType")
                    == "SERVERLESS"
                ).upper(),

            "backup":
                str(
                    c.get(
                        "cloudBackup",
                        False
                    )
                ).upper(),

            "disk_size_gb":
                disk_size_gb,

            "online_archive":
                str(
                    has_online_archive
                ).upper(),

            "atlas_search":
                str(
                    has_atlas_search
                ).upper(),

            "vector_search":
                str(
                    has_vector_search
                ).upper(),

            "vector_indexes":
                vector_indexes
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

    # =================================================
    # TRIGGERS
    # =================================================

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
            continue

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

                config_data = data.get(
                    "config",
                    {}
                )

                event_processors = data.get(
                    "event_processors",
                    {}
                )

                trigger_obj = {

                    "project_name":
                        PROJECT_NAME,

                    "project_id":
                        PROJECT_ID,

                    "app_name":
                        app_name,

                    "app_id":
                        app_id,

                    "trigger_name":
                        data.get("name"),

                    "type":
                        data.get("type"),

                    "function_name":
                        (
                            event_processors
                            .get("FUNCTION", {})
                            .get("config", {})
                            .get("function_name")
                        ),

                    "service_name":
                        config_data.get(
                            "service_name"
                        ),

                    "database":
                        config_data.get(
                            "database"
                        ),

                    "collection":
                        config_data.get(
                            "collection"
                        ),

                    "operation_types":
                        ",".join(
                            config_data.get(
                                "operation_types",
                                []
                            )
                        ),

                    "disabled":
                        str(
                            data.get(
                                "disabled",
                                False
                            )
                        ).upper()
                }

                app_obj["triggers"].append(
                    trigger_obj
                )

                trigger_rows.append(
                    trigger_obj
                )

                total_triggers += 1

            except Exception as e:

                log(
                    f"{RED}Trigger parsing error:{RESET}"
                )

                log(str(e))

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

        "total_online_archive":
            sum(
                1 for c in assessment["infrastructure"]["clusters"]
                if c.get("online_archive") == "TRUE"
            ),

        "total_atlas_search":
            sum(
                1 for c in assessment["infrastructure"]["clusters"]
                if c.get("atlas_search") == "TRUE"
            ),

        "total_vector_search":
            sum(
                1 for c in assessment["infrastructure"]["clusters"]
                if c.get("vector_search") == "TRUE"
            )
    })

    final_output["projects"].append(
        assessment
    )

# =====================================================
# SAVE JSON
# =====================================================

log(
    f"\n{YELLOW}Generating JSON...{RESET}"
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

log(
    f"{GREEN}OK{RESET} - JSON generated:"
)

log(json_path)

# =====================================================
# SAVE EXCEL
# =====================================================

log(
    f"\n{YELLOW}Generating Excel...{RESET}"
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

log(
    f"{GREEN}OK{RESET} - Excel generated:"
)

log(excel_path)

log(
    f"\n{GREEN}Pipeline completed{RESET}"
)
