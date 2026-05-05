import json
import pandas as pd

INPUT_FILE = "atlas_auto_assessment.json"
OUTPUT_FILE = "atlas_auto_assessment.xlsx"

with open(INPUT_FILE) as f:
    data = json.load(f)

# =====================================================
# TRIGGERS (FLATTEN)
# =====================================================

triggers_rows = []

for project in data["projects"]:

    project_name = project.get("project_name")
    project_id = project.get("project_id")

    for app in project.get("app_services", {}).get("apps", []):

        app_name = app.get("app_name")
        app_id = app.get("app_id")

        for t in app.get("triggers", []):

            triggers_rows.append({
                "project_name": project_name,
                "project_id": project_id,
                "app_name": app_name,
                "app_id": app_id,
                "trigger_name": t.get("trigger_name"),
                "type": t.get("type"),
                "database": t.get("database"),
                "collection": t.get("collection"),
                "operations": ",".join(t.get("operations", [])),
                "disabled": t.get("disabled"),
                "function": t.get("function"),
                "uses_http": t.get("function_analysis", {}).get("uses_http"),
                "uses_context_services": t.get("function_analysis", {}).get("uses_context_services"),
                "uses_collection": t.get("function_analysis", {}).get("uses_collection"),
                "code_size": t.get("function_analysis", {}).get("code_size")
            })

df_triggers = pd.DataFrame(triggers_rows)

# =====================================================
# CLUSTERS
# =====================================================

clusters_rows = []

for project in data["projects"]:

    project_name = project.get("project_name")
    project_id = project.get("project_id")

    for c in project.get("infrastructure", {}).get("clusters", []):

        clusters_rows.append({
            "project_name": project_name,
            "project_id": project_id,
            "cluster_name": c.get("cluster_name"),
            "provider": c.get("provider"),
            "cluster_type": c.get("cluster_type"),
            "instance_size": c.get("instance_size"),
            "mongo_version": c.get("mongo_version"),
            "serverless": c.get("serverless"),
            "backup_continuous": c.get("backup_continuous"),
            "encryption_at_rest": c.get("encryption_at_rest"),
            "customer_managed_keys": c.get("customer_managed_keys"),
            "online_archive": c.get("online_archive"),
            "atlas_search": c.get("atlas_search")
        })

df_clusters = pd.DataFrame(clusters_rows)

# =====================================================
# SUMMARY POR PROJETO
# =====================================================

summary_rows = []

for project in data["projects"]:

    project_name = project.get("project_name")
    project_id = project.get("project_id")

    total_clusters = len(project.get("infrastructure", {}).get("clusters", []))

    total_triggers = sum(
        len(app.get("triggers", []))
        for app in project.get("app_services", {}).get("apps", [])
    )

    uses_http = any(
        t.get("function_analysis", {}).get("uses_http")
        for app in project.get("app_services", {}).get("apps", [])
        for t in app.get("triggers", [])
    )

    uses_collection = any(
        t.get("function_analysis", {}).get("uses_collection")
        for app in project.get("app_services", {}).get("apps", [])
        for t in app.get("triggers", [])
    )

    summary_rows.append({
        "project_name": project_name,
        "project_id": project_id,
        "total_clusters": total_clusters,
        "total_triggers": total_triggers,
        "uses_http": uses_http,
        "uses_collection": uses_collection,
        "data_federation_enabled": project.get("infrastructure", {}).get("data_federation_enabled"),
        "private_endpoints_enabled": project.get("infrastructure", {}).get("private_endpoints_enabled")
    })

df_summary = pd.DataFrame(summary_rows)

# =====================================================
# EXPORT EXCEL
# =====================================================

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:

    df_triggers.to_excel(writer, sheet_name="Triggers", index=False)
    df_clusters.to_excel(writer, sheet_name="Clusters", index=False)
    df_summary.to_excel(writer, sheet_name="Summary", index=False)

print(f"Arquivo gerado: {OUTPUT_FILE}")
