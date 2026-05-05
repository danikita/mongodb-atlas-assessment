
import os
import re
import shutil
import subprocess
import pexpect

# =====================================================
# CORES
# =====================================================

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

## =====================================================
## CONFIG
## =====================================================

default_base_export_dir = "/home/ec2-user/realm_exports"
user_input = input(
    f"Informe o caminho do BASE_EXPORT_DIR "
    f"[default: {default_base_export_dir}]: "
).strip()

BASE_EXPORT_DIR = user_input if user_input else default_base_export_dir

# =====================================================
# VALIDAR SESSÃO
# =====================================================

print(
    f"{YELLOW}Validando sessão realm-cli...{RESET}"
)

session_test = subprocess.run(
    ["realm-cli", "app", "list"],
    capture_output=True,
    text=True
)

# -----------------------------------------------------
# SESSÃO INVÁLIDA
# -----------------------------------------------------

if (
    session_test.returncode != 0
    or "invalid session" in session_test.stderr.lower()
):

    print(
        f"{YELLOW}Sessão inválida.{RESET}"
    )

    print(
        f"{YELLOW}Realizando login...{RESET}"
    )

    login = subprocess.run(
        ["realm-cli", "login"]
    )

    if login.returncode != 0:

        print(
            f"{RED}Falha no login{RESET}"
        )

        exit(1)

    # TESTA NOVAMENTE

    session_test = subprocess.run(
        ["realm-cli", "app", "list"],
        capture_output=True,
        text=True
    )

    if session_test.returncode != 0:

        print(
            f"{RED}Falha ao validar sessão após login{RESET}"
        )

        print(session_test.stderr)

        exit(1)

# -----------------------------------------------------
# SESSÃO OK
# -----------------------------------------------------

else:

    print(
        f"{GREEN}OK{RESET} - "
        f"Sessão autenticada"
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

if result.returncode != 0:

    print(
        f"{RED}Falha ao listar apps{RESET}"
    )

    print(result.stderr)

    exit(1)

# =====================================================
# EXTRAIR APPS
# =====================================================

#
# Exemplo:
#
# triggers-fljovwi (5c893a855538555c636b3621)
#

pattern = r"(.+?)\s+\(([a-f0-9]+)\)"

apps = re.findall(pattern, result.stdout)

if not apps:

    print(
        f"{RED}Nenhum app encontrado{RESET}"
    )

    exit(1)

print(
    f"{GREEN}OK{RESET} - "
    f"{len(apps)} app(s)"
)

# =====================================================
# CRIAR BASE
# =====================================================

os.makedirs(
    BASE_EXPORT_DIR,
    exist_ok=True
)

# =====================================================
# LOOP DOS APPS
# =====================================================

for index, (app_name, app_id) in enumerate(apps):

    app_name = app_name.strip()

    print(
        f"\n{YELLOW}Exportando:{RESET} "
        f"{app_name}"
    )

    print(f"App ID: {app_id}")

    # =================================================
    # PASTA DESTINO
    # =================================================

    export_path = os.path.join(
        BASE_EXPORT_DIR,
        app_id
    )

    # =================================================
    # REMOVE EXPORT ANTIGO
    # =================================================

    if os.path.exists(export_path):

        print(
            f"{YELLOW}Removendo export anterior..."
            f"{RESET}"
        )

        shutil.rmtree(export_path)

    # =================================================
    # RECRIAR PASTA
    # =================================================

    os.makedirs(export_path)

    print(f"Pasta: {export_path}")

    os.chdir(export_path)

    # =================================================
    # EXECUTAR EXPORT
    # =================================================

    try:

        child = pexpect.spawn(
            "realm-cli export",
            encoding="utf-8",
            timeout=300
        )

        # =================================================
        # LOG
        # =================================================

        log_path = os.path.join(
            export_path,
            "realm_export.log"
        )

        logfile = open(log_path, "w")

        child.logfile = logfile

        # =================================================
        # MENU PROJETO
        # =================================================

        child.expect("Atlas Project")

        print(
            f"{GREEN}OK{RESET} - "
            f"Tela de projeto detectada"
        )

        # ENTER NO PRIMEIRO PROJETO

        child.sendline("")

        # =================================================
        # MENU APPS
        # =================================================

        child.expect([
            "Use arrows to move",
            "client files",
            pexpect.TIMEOUT
        ])

        print(
            f"{GREEN}OK{RESET} - "
            f"Menu de apps detectado"
        )

        # =================================================
        # NAVEGAR NO APP
        # =================================================

        #
        # app 0 -> ENTER
        # app 1 -> ↓ ENTER
        # app 2 -> ↓ ↓ ENTER
        #

        for _ in range(index):

            child.send("\x1b[B")

        child.sendline("")

        # =================================================
        # AGUARDAR FINALIZAÇÃO
        # =================================================

        child.expect(pexpect.EOF)

        logfile.close()

        print(
            f"{GREEN}OK{RESET} - "
            f"Export concluído"
        )

    except Exception as e:

        print(
            f"{RED}ERRO{RESET} - "
            f"Falha no export"
        )

        print(e)

# =====================================================
# FINAL
# =====================================================

print(
    f"\n{GREEN}Processo finalizado{RESET}"
)

print(BASE_EXPORT_DIR)
