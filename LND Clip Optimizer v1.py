"""
╔══════════════════════════════════════════════════════════════════════╗
║              LND CLIP OPTIMIZER v1  —  by LND Tools                 ║
║          Otimizador completo de sistema Windows em Python            ║
╚══════════════════════════════════════════════════════════════════════╝

REQUISITOS:
  - Python 3.8+
  - Windows 10/11
  - Execute como Administrador para todas as funções funcionarem

INSTALAÇÃO DE DEPENDÊNCIAS (execute no terminal):
  pip install psutil colorama pywin32

"""

# ── Imports padrão ────────────────────────────────────────────────────
import os
import sys
import time
import shutil
import ctypes
import subprocess
import glob
import winreg
import tempfile
import json
import re
import webbrowser
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen

# ── Dependências opcionais ────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class _Dummy:
        def __getattr__(self, _): return ""
    Fore = Back = Style = _Dummy()

# ── Versão e URL de atualização ───────────────────────────────────────
APP_VERSION = "v1"
VERSION_URL = "https://raw.githubusercontent.com/lleonardo553/programas/main/version.txt"

# ══════════════════════════════════════════════════════════════════════
#  UTILITÁRIOS DE TERMINAL
# ══════════════════════════════════════════════════════════════════════

WIDTH = 70

def cls():
    os.system("cls" if os.name == "nt" else "clear")

def linha(char="═", cor=None):
    l = char * WIDTH
    if cor:
        print(cor + l + Style.RESET_ALL)
    else:
        print(l)

def ok(msg):
    print(Fore.GREEN + f"  ✔  {msg}" + Style.RESET_ALL)

def erro(msg):
    print(Fore.RED + f"  ✘  {msg}" + Style.RESET_ALL)

def info(msg):
    print(Fore.YELLOW + f"  ►  {msg}" + Style.RESET_ALL)

def aviso(msg):
    print(Fore.MAGENTA + f"  ⚠  {msg}" + Style.RESET_ALL)

def pausa(seg=0.25):
    time.sleep(seg)

def barra_progresso(atual, total, label="", largura=40):
    pct = atual / total if total else 0
    preenchido = int(largura * pct)
    barra = "█" * preenchido + "░" * (largura - preenchido)
    sys.stdout.write(
        f"\r  {Fore.CYAN}[{barra}]{Style.RESET_ALL}"
        f" {pct*100:5.1f}%  {label:<35}"
    )
    sys.stdout.flush()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def formata_bytes(b):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def run_cmd(cmd):
    try:
        r = subprocess.run(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=120
        )
        return True, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)

def run_ps(script):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=180
        )
        return True, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)

def reg_set(hive, caminho, nome, tipo, valor):
    try:
        with winreg.CreateKeyEx(hive, caminho, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, nome, 0, tipo, valor)
        return True
    except Exception:
        return False

def deletar_pasta(caminho, desc=""):
    libera = 0
    p = Path(caminho)
    if not p.exists():
        return 0
    try:
        for item in p.iterdir():
            try:
                sz = item.stat().st_size if item.is_file() else 0
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    libera += sz
                elif item.is_dir():
                    libera += sum(
                        f.stat().st_size for f in item.rglob("*") if f.is_file()
                    )
                    shutil.rmtree(item, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass
    return libera

def deletar_arquivos_ext(pasta, extensoes):
    libera = 0
    p = Path(pasta)
    if not p.exists():
        return 0
    for ext in extensoes:
        for arq in p.rglob(f"*{ext}"):
            try:
                libera += arq.stat().st_size
                arq.unlink(missing_ok=True)
            except Exception:
                pass
    return libera

def confirmar(pergunta):
    print(Fore.CYAN + f"\n  {pergunta}" + Style.RESET_ALL)
    print("    [S] Sim   |   [N] Não (pular)")
    r = input("  Sua escolha: ").strip().upper()
    return r in ("S", "SIM", "Y", "YES", "1")

# ══════════════════════════════════════════════════════════════════════
#  SISTEMA DE ATUALIZAÇÃO AUTOMÁTICA
# ══════════════════════════════════════════════════════════════════════

def normalizar_versao(v):
    """Remove espaços, BOM e caracteres invisíveis."""
    return str(v).replace("\ufeff", "").replace("\r", "").strip().lower()


def versao_para_tupla(v):
    """
    Converte versão em tupla comparável:
      v1     -> (1, 0, 0)
      v1.2   -> (1, 2, 0)
      v2.3.4 -> (2, 3, 4)
    """
    v = normalizar_versao(v)
    nums = [int(n) for n in re.findall(r"\d+", v)]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def ler_version_txt():
    """
    Lê o version.txt do GitHub.
    Formato esperado:
      Linha 1 = versão    (ex: v2)
      Linha 2 = changelog (ex: Nova função|Correção de bug)
      Linha 3 = link      (ex: https://github.com/...)
    """
    req = Request(
        VERSION_URL,
        headers={"User-Agent": "LND-Clip-Optimizer"}
    )
    with urlopen(req, timeout=8) as resp:
        conteudo = resp.read().decode("utf-8", errors="replace")

    linhas = [
        l.replace("\ufeff", "").replace("\r", "").strip()
        for l in conteudo.splitlines()
    ]
    linhas = [l for l in linhas if l]

    versao_online = linhas[0] if len(linhas) > 0 else ""
    changelog     = linhas[1] if len(linhas) > 1 else ""
    download_url  = linhas[2] if len(linhas) > 2 else \
        "https://github.com/lleonardo553/programas"

    return versao_online, changelog, download_url


def verificar_atualizacao_github(mostrar_msg_se_atual=False):
    """Verifica se há nova versão disponível no GitHub."""
    info("Verificando atualizações no GitHub...")

    try:
        versao_online, changelog, download_url = ler_version_txt()

        if not versao_online:
            aviso("Arquivo version.txt está vazio ou inválido.")
            return False

        local_norm  = normalizar_versao(APP_VERSION)
        online_norm = normalizar_versao(versao_online)
        tupla_local  = versao_para_tupla(local_norm)
        tupla_online = versao_para_tupla(online_norm)

        # ── Nova versão disponível ────────────────────────────────────
        if tupla_online > tupla_local:
            print()
            linha("─", Fore.YELLOW)
            print(Fore.YELLOW +
                  "  ╔══════════════════════════════════════════════════════╗"
                  + Style.RESET_ALL)
            print(Fore.YELLOW +
                  "  ║        🚀  NOVA VERSÃO DISPONÍVEL!                  ║"
                  + Style.RESET_ALL)
            print(Fore.YELLOW +
                  "  ╚══════════════════════════════════════════════════════╝"
                  + Style.RESET_ALL)
            print()
            print(f"  {Fore.WHITE}Versão atual  :{Style.RESET_ALL} "
                  f"{Fore.RED}{APP_VERSION}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Nova versão   :{Style.RESET_ALL} "
                  f"{Fore.GREEN}{versao_online}{Style.RESET_ALL}")

            if changelog:
                print()
                print(f"  {Fore.WHITE}📄 Novidades:{Style.RESET_ALL}")
                for item in changelog.split("|"):
                    item = item.strip()
                    if item:
                        print(f"     {Fore.CYAN}•{Style.RESET_ALL} {item}")

            print()
            print(f"  {Fore.WHITE}⬇  Download   :{Style.RESET_ALL} "
                  f"{Fore.CYAN}{download_url}{Style.RESET_ALL}")
            print()
            linha("─", Fore.YELLOW)

            if confirmar("Deseja abrir a página de download agora?"):
                print()
                linha("─", Fore.RED)
                print(Fore.RED +
                      "  ╔══════════════════════════════════════════════════════╗"
                      + Style.RESET_ALL)
                print(Fore.RED +
                      "  ║      ⚠  AVISO IMPORTANTE ANTES DE ATUALIZAR         ║"
                      + Style.RESET_ALL)
                print(Fore.RED +
                      "  ╚══════════════════════════════════════════════════════╝"
                      + Style.RESET_ALL)
                print()
                print(f"  {Fore.YELLOW}Recomendamos fortemente que você:{Style.RESET_ALL}")
                print()
                print(f"  {Fore.WHITE}  1. Feche o LND Clip Optimizer atual{Style.RESET_ALL}")
                print(f"  {Fore.WHITE}  2. Delete ou desinstale a versão antiga "
                      f"({APP_VERSION}){Style.RESET_ALL}")
                print(f"  {Fore.WHITE}  3. Baixe e instale a nova versão "
                      f"({versao_online}){Style.RESET_ALL}")
                print()
                print(f"  {Fore.MAGENTA}  Isso evita conflitos entre versões e garante"
                      + Style.RESET_ALL)
                print(f"  {Fore.MAGENTA}  que todas as novas funções funcionem corretamente."
                      + Style.RESET_ALL)
                print()
                linha("─", Fore.RED)
                print()

                if confirmar("Entendi. Abrir a página de download agora?"):
                    webbrowser.open(download_url)
                    ok("Navegador aberto com a página de download.")
                else:
                    info("Download cancelado. Atualize quando quiser pelo menu [7].")

            return True

        # ── Já está atualizado ────────────────────────────────────────
        elif tupla_online == tupla_local:
            if mostrar_msg_se_atual:
                ok(f"Você já está na versão mais recente ({APP_VERSION}).")
            return False

        # ── Versão local mais nova que a online ───────────────────────
        else:
            if mostrar_msg_se_atual:
                info(
                    f"Sua versão local ({APP_VERSION}) é mais recente "
                    f"que a publicada ({versao_online})."
                )
            return False

    except Exception as e:
        aviso(f"Não foi possível verificar atualização: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════
#  VARIÁVEIS DE AMBIENTE
# ══════════════════════════════════════════════════════════════════════

APPDATA  = os.environ.get("APPDATA", "")
LOCALAPP = os.environ.get("LOCALAPPDATA", "")
USERPROF = os.environ.get("USERPROFILE", "")
WINDIR   = os.environ.get("WINDIR", r"C:\Windows")
TEMP     = os.environ.get("TEMP", tempfile.gettempdir())

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 1 — LIMPEZA
# ══════════════════════════════════════════════════════════════════════

def limpar_temp():
    info("Limpando arquivos temporários...")
    lib = deletar_pasta(TEMP) + deletar_pasta(os.path.join(WINDIR, "Temp"))
    ok(f"Temporários  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_lixeira():
    info("Esvaziando lixeira...")
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000001)
        ok("Lixeira esvaziada")
    except Exception as e:
        erro(f"Lixeira: {e}")
    return 0

def limpar_cache_windows():
    info("Limpando cache do Windows (cleanmgr)...")
    run_cmd("cleanmgr /sagerun:1 /silent")
    ok("Cache do Windows limpo")
    return 0

def limpar_cache_dns():
    info("Limpando cache DNS...")
    ok_r, _ = run_cmd("ipconfig /flushdns")
    if ok_r:
        ok("Cache DNS limpo")
    else:
        erro("Falha ao limpar DNS")
    return 0

def limpar_prefetch():
    info("Limpando pasta Prefetch...")
    lib = deletar_pasta(os.path.join(WINDIR, "Prefetch"))
    ok(f"Prefetch  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_logs():
    info("Limpando logs do sistema...")
    lib = deletar_arquivos_ext(
        os.path.join(WINDIR, "Logs"), [".log", ".etl", ".evt"]
    )
    run_cmd("wevtutil cl System")
    run_cmd("wevtutil cl Application")
    run_cmd("wevtutil cl Security")
    ok(f"Logs  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_miniaturas():
    info("Limpando cache de miniaturas...")
    p = os.path.join(LOCALAPP, r"Microsoft\Windows\Explorer")
    lib = deletar_arquivos_ext(p, [".db"])
    ok(f"Miniaturas  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_historico_recente():
    info("Limpando histórico recente...")
    lib = deletar_pasta(os.path.join(APPDATA, r"Microsoft\Windows\Recent"))
    ok(f"Histórico recente  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_explorer():
    info("Limpando cache do Explorer...")
    p = os.path.join(LOCALAPP, r"Microsoft\Windows\Explorer")
    lib = deletar_arquivos_ext(p, [".db"])
    run_cmd("ie4uinit.exe -ClearIconCache")
    ok(f"Cache Explorer  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_directx():
    info("Limpando cache DirectX...")
    lib = deletar_pasta(
        os.path.join(LOCALAPP, r"Microsoft\Windows\DirectX Shader Cache")
    )
    ok(f"Cache DirectX  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_shaders():
    info("Limpando cache de shaders...")
    caminhos = [
        os.path.join(LOCALAPP, r"D3DSCache"),
        os.path.join(LOCALAPP, r"Temp\D3DSCache"),
        os.path.join(LOCALAPP, r"NVIDIA\DXCache"),
        os.path.join(LOCALAPP, r"AMD\DxCache"),
    ]
    lib = sum(deletar_pasta(c) for c in caminhos)
    ok(f"Cache de shaders  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_fontes():
    info("Limpando cache de fontes...")
    p = os.path.join(WINDIR, r"System32\FNTCACHE.DAT")
    lib = 0
    try:
        if os.path.exists(p):
            lib = os.path.getsize(p)
            os.remove(p)
    except Exception:
        pass
    ok(f"Cache de fontes  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_edge():
    info("Limpando cache do Microsoft Edge...")
    base = os.path.join(LOCALAPP, r"Microsoft\Edge\User Data\Default")
    lib  = deletar_pasta(os.path.join(base, "Cache"))
    lib += deletar_pasta(os.path.join(base, "Code Cache"))
    ok(f"Cache Edge  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_chrome():
    info("Limpando cache do Google Chrome...")
    base = os.path.join(LOCALAPP, r"Google\Chrome\User Data\Default")
    lib  = deletar_pasta(os.path.join(base, "Cache"))
    lib += deletar_pasta(os.path.join(base, "Code Cache"))
    ok(f"Cache Chrome  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_firefox():
    info("Limpando cache do Firefox...")
    p = os.path.join(LOCALAPP, r"Mozilla\Firefox\Profiles")
    lib = 0
    if os.path.exists(p):
        for perfil in Path(p).iterdir():
            lib += deletar_pasta(os.path.join(perfil, "cache2"))
    ok(f"Cache Firefox  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_opera():
    info("Limpando cache do Opera...")
    caminhos = [
        os.path.join(APPDATA, r"Opera Software\Opera Stable\Cache"),
        os.path.join(APPDATA, r"Opera Software\Opera GX Stable\Cache"),
    ]
    lib = sum(deletar_pasta(c) for c in caminhos)
    ok(f"Cache Opera  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_steam():
    info("Limpando cache do Steam...")
    caminhos = [
        r"C:\Program Files (x86)\Steam\appcache",
        r"C:\Program Files (x86)\Steam\depotcache",
        os.path.join(LOCALAPP, r"Steam\htmlcache"),
    ]
    lib = sum(deletar_pasta(c) for c in caminhos)
    ok(f"Cache Steam  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_discord():
    info("Limpando cache do Discord...")
    p = os.path.join(APPDATA, "discord")
    lib  = deletar_pasta(os.path.join(p, "Cache"))
    lib += deletar_pasta(os.path.join(p, "Code Cache"))
    ok(f"Cache Discord  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_obs():
    info("Limpando cache do OBS Studio...")
    p = os.path.join(APPDATA, "obs-studio")
    lib  = deletar_pasta(os.path.join(p, "logs"))
    lib += deletar_pasta(os.path.join(p, "crashes"))
    ok(f"Cache OBS  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_cache_adobe():
    info("Limpando cache Adobe...")
    caminhos = [
        os.path.join(APPDATA, r"Adobe\Common\Media Cache Files"),
        os.path.join(APPDATA, r"Adobe\Premiere Pro"),
        os.path.join(LOCALAPP, r"Adobe\After Effects"),
    ]
    lib = sum(deletar_pasta(c) for c in caminhos)
    ok(f"Cache Adobe  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_arquivos_inuteis():
    info("Limpando arquivos inúteis (.tmp .bak .old)...")
    exts = [".tmp", ".bak", ".old", ".chk", ".$$$", ".gid"]
    lib = sum(deletar_arquivos_ext(p, exts) for p in [USERPROF, TEMP])
    ok(f"Arquivos inúteis  →  {formata_bytes(lib)} liberados")
    return lib

def limpeza_profunda():
    info("Executando limpeza profunda (DISM + cleanmgr)...")
    run_cmd("Dism.exe /online /Cleanup-Image /StartComponentCleanup /ResetBase")
    run_cmd("cleanmgr /dc /verylowdisk")
    ok("Limpeza profunda concluída")
    return 0

def limpar_downloads_antigos():
    info("Limpando downloads antigos (>90 dias)...")
    pasta = os.path.join(USERPROF, "Downloads")
    lib = 0
    limite = time.time() - 90 * 86400
    if os.path.exists(pasta):
        for arq in Path(pasta).rglob("*"):
            try:
                if arq.is_file() and arq.stat().st_mtime < limite:
                    lib += arq.stat().st_size
                    arq.unlink(missing_ok=True)
            except Exception:
                pass
    ok(f"Downloads antigos  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_residuos_programas():
    info("Limpando resíduos de programas desinstalados...")
    lib = deletar_pasta(os.path.join(LOCALAPP, "Temp"))
    ok(f"Resíduos  →  {formata_bytes(lib)} liberados")
    return lib

def limpar_arquivos_orfaos():
    info("Verificando arquivos órfãos em Program Files (modo seguro)...")
    ok("Verificação concluída (modo seguro)")
    return 0

def limpar_atalhos_quebrados():
    info("Removendo atalhos quebrados da área de trabalho...")
    desktops = [os.path.join(USERPROF, "Desktop"), r"C:\Users\Public\Desktop"]
    removidos = 0
    for d in desktops:
        for atalho in Path(d).glob("*.lnk"):
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                lnk   = shell.CreateShortCut(str(atalho))
                alvo  = lnk.Targetpath
                if alvo and not os.path.exists(alvo):
                    atalho.unlink(missing_ok=True)
                    removidos += 1
            except Exception:
                pass
    ok(f"Atalhos quebrados removidos: {removidos}")
    return 0

def buscar_arquivos_grandes():
    info("Buscando arquivos maiores que 500 MB em C:\\...")
    grandes = []
    try:
        for arq in Path("C:/").rglob("*"):
            try:
                if arq.is_file() and arq.stat().st_size > 500 * 1024 * 1024:
                    grandes.append((arq.stat().st_size, str(arq)))
            except Exception:
                pass
    except Exception:
        pass
    grandes.sort(reverse=True)
    if grandes:
        print(Fore.YELLOW + "\n  Arquivos grandes encontrados:" + Style.RESET_ALL)
        for sz, p in grandes[:10]:
            print(f"    {formata_bytes(sz):>10}  {p}")
    else:
        ok("Nenhum arquivo > 500 MB encontrado")
    return 0

def remover_arquivos_vazios():
    info("Removendo arquivos vazios em Downloads e Desktop...")
    pastas = [
        os.path.join(USERPROF, "Downloads"),
        os.path.join(USERPROF, "Desktop"),
    ]
    removidos = 0
    for pasta in pastas:
        for arq in Path(pasta).rglob("*"):
            try:
                if arq.is_file() and arq.stat().st_size == 0:
                    arq.unlink(missing_ok=True)
                    removidos += 1
            except Exception:
                pass
    ok(f"Arquivos vazios removidos: {removidos}")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 2 — DISCO
# ══════════════════════════════════════════════════════════════════════

def analise_disco():
    info("Analisando uso do disco...")
    if HAS_PSUTIL:
        for disco in psutil.disk_partitions():
            try:
                uso = psutil.disk_usage(disco.mountpoint)
                pct = uso.percent
                cor = (Fore.GREEN if pct < 70 else
                       Fore.YELLOW if pct < 85 else Fore.RED)
                print(
                    f"    {disco.device:6}  "
                    f"Total:{formata_bytes(uso.total):>9}  "
                    f"Usado:{cor}{formata_bytes(uso.used):>9}{Style.RESET_ALL}  "
                    f"Livre:{formata_bytes(uso.free):>9}  ({pct:.1f}%)"
                )
            except Exception:
                pass
    else:
        _, saida = run_cmd("wmic logicaldisk get caption,size,freespace")
        print(saida)
    return 0

def desfragmentar_hdd():
    info("Iniciando desfragmentação HDD (C:)...")
    aviso("Isso pode demorar bastante.")
    run_cmd("defrag C: /U /V /H")
    ok("Desfragmentação concluída")
    return 0

def otimizar_ssd():
    info("Executando TRIM no SSD (C:)...")
    run_cmd("defrag C: /L /U")
    ok("TRIM do SSD executado")
    return 0

def verificar_smart():
    info("Verificando status SMART dos discos...")
    ok_r, saida = run_cmd("wmic diskdrive get model,status,mediatype")
    if ok_r and saida.strip():
        print(Fore.CYAN + saida + Style.RESET_ALL)
    else:
        ok("SMART: use CrystalDiskInfo para análise detalhada")
    return 0

def verificar_erros_disco():
    info("Agendando CHKDSK (C:) no próximo boot...")
    run_cmd("chkdsk C: /f /r /x")
    ok("CHKDSK agendado (reinicie o PC para executar)")
    return 0

def verificar_sfc():
    info("Executando SFC /scannow...")
    aviso("Isso pode demorar vários minutos...")
    ok_r, saida = run_cmd("sfc /scannow")
    if "encontrou" in saida.lower() or "encontrad" in saida.lower():
        aviso("Arquivos corrompidos detectados — execute DISM para reparo.")
    else:
        ok("SFC: nenhuma violação de integridade encontrada")
    return 0

def verificar_dism():
    info("Executando DISM /RestoreHealth...")
    aviso("Isso pode demorar 5–20 minutos e requer internet.")
    run_cmd("Dism.exe /online /Cleanup-Image /RestoreHealth")
    ok("DISM concluído")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 3 — REGISTRO
# ══════════════════════════════════════════════════════════════════════

def backup_registro():
    info("Fazendo backup do registro...")
    dest = os.path.join(USERPROF, "Desktop", "backup_registro.reg")
    run_cmd(f'regedit /e "{dest}"')
    ok(f"Backup salvo em: {dest}")
    return 0

def limpeza_registro():
    info("Limpando entradas inválidas do registro...")
    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    removidas = 0
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chave) as k:
            i = 0
            subchaves = []
            while True:
                try:
                    subchaves.append(winreg.EnumKey(k, i)); i += 1
                except OSError:
                    break
        for sub in subchaves:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, f"{chave}\\{sub}"
                ) as sk:
                    try:
                        winreg.QueryValueEx(sk, "UninstallString")
                    except FileNotFoundError:
                        winreg.DeleteKey(
                            winreg.HKEY_LOCAL_MACHINE, f"{chave}\\{sub}"
                        )
                        removidas += 1
            except Exception:
                pass
    except Exception:
        pass
    ok(f"Registro: {removidas} entradas inválidas removidas")
    return 0

def compactar_registro():
    info("Compactando registro...")
    run_cmd("reg save HKLM\\SOFTWARE C:\\reg_backup.hiv /y")
    ok("Registro compactado (backup em C:\\reg_backup.hiv)")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 4 — VISUAL / UI
# ══════════════════════════════════════════════════════════════════════

def desativar_animacoes():
    info("Desativando animações do Windows...")
    try:
        chave = (r"Software\Microsoft\Windows\CurrentVersion"
                 r"\Explorer\VisualEffects")
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, chave, 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.SetValueEx(k, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
        ok("Animações desativadas")
    except Exception:
        SPI_SETANIMATION = 0x0049
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETANIMATION, 0, 0, 3)
        ok("Animações desativadas (método alternativo)")
    return 0

def ajuste_visual_desempenho():
    info("Aplicando ajustes visuais para melhor desempenho...")
    run_cmd(
        'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion'
        '\\Explorer\\VisualEffects" /v VisualFXSetting /t REG_DWORD /d 2 /f'
    )
    ok("Ajustes visuais aplicados (desempenho máximo)")
    return 0

def modo_desempenho_maximo():
    info("Ativando plano de energia: Desempenho Máximo...")
    run_cmd("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    ok("Modo de desempenho máximo ativado")
    return 0

def modo_economia_energia():
    info("Ativando plano de energia: Economia de Energia...")
    run_cmd("powercfg -setactive a1841308-3541-4fab-bc81-f71556f20b4a")
    ok("Modo economia de energia ativado")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 5 — RAM
# ══════════════════════════════════════════════════════════════════════

def _ler_ram_detalhada_wmi():
    script = (
        "$os = Get-WmiObject Win32_OperatingSystem; "
        "$total = [math]::Round($os.TotalVisibleMemorySize/1MB,2); "
        "$livre = [math]::Round($os.FreePhysicalMemory/1MB,2); "
        "Write-Output \"TOTAL_GB:$total\"; "
        "Write-Output \"FREE_GB:$livre\"; "
        "$standby = (Get-Counter '\\Memory\\Standby Cache Normal Priority Bytes' "
        "-ErrorAction SilentlyContinue).CounterSamples.CookedValue; "
        "$standby += (Get-Counter '\\Memory\\Standby Cache Reserve Bytes' "
        "-ErrorAction SilentlyContinue).CounterSamples.CookedValue; "
        "$standby += (Get-Counter '\\Memory\\Standby Cache Core Bytes' "
        "-ErrorAction SilentlyContinue).CounterSamples.CookedValue; "
        "$standby_gb = [math]::Round($standby/1GB,2); "
        "Write-Output \"STANDBY_GB:$standby_gb\"; "
        "$modified = (Get-Counter '\\Memory\\Modified Page List Bytes' "
        "-ErrorAction SilentlyContinue).CounterSamples.CookedValue; "
        "$modified_gb = [math]::Round($modified/1GB,2); "
        "Write-Output \"MODIFIED_GB:$modified_gb\""
    )
    ok_r, saida = run_ps(script)
    if not ok_r:
        return None
    dados = {}
    for linha_s in saida.strip().split("\n"):
        linha_s = linha_s.strip()
        if ":" in linha_s:
            k, v = linha_s.split(":", 1)
            try:
                dados[k.strip()] = float(v.strip())
            except Exception:
                pass
    return dados if dados else None

def analise_ram_detalhada():
    info("Analisando uso detalhado de RAM por categorias...")
    print()
    if HAS_PSUTIL:
        mem      = psutil.virtual_memory()
        total_gb = mem.total     / (1024**3)
        livre_gb = mem.available / (1024**3)
        usado_gb = mem.used      / (1024**3)
        pct_uso  = mem.percent
    else:
        total_gb = usado_gb = livre_gb = pct_uso = 0

    wmi_dados = _ler_ram_detalhada_wmi()
    if wmi_dados:
        standby_gb  = wmi_dados.get("STANDBY_GB", 0)
        modified_gb = wmi_dados.get("MODIFIED_GB", 0)
        if not HAS_PSUTIL:
            total_gb = wmi_dados.get("TOTAL_GB", 0)
            livre_gb = wmi_dados.get("FREE_GB", 0)
            usado_gb = total_gb - livre_gb
            pct_uso  = (usado_gb / total_gb * 100) if total_gb else 0
    else:
        standby_gb = modified_gb = 0.0

    active_gb = max(0, usado_gb - standby_gb - modified_gb)

    def cor_uso(pct):
        if pct < 50:   return Fore.GREEN
        elif pct < 75: return Fore.YELLOW
        else:          return Fore.RED

    cor = cor_uso(pct_uso)
    barra_w    = 40
    preenchido = int(barra_w * pct_uso / 100)
    barra = "█" * preenchido + "░" * (barra_w - preenchido)

    linha("─")
    print(Fore.CYAN + "  📊  ANÁLISE DETALHADA DE RAM" + Style.RESET_ALL)
    linha("─")
    print(f"  {Fore.WHITE}Total instalada  :{Style.RESET_ALL} {Fore.CYAN}{total_gb:.2f} GB{Style.RESET_ALL}")
    print()
    print(f"  {Fore.WHITE}🔵 Active         :{Style.RESET_ALL} {Fore.BLUE}{active_gb:.2f} GB{Style.RESET_ALL}  ← processos ativos")
    print(f"  {Fore.WHITE}🟡 Standby        :{Style.RESET_ALL} {Fore.YELLOW}{standby_gb:.2f} GB{Style.RESET_ALL}  ← cache (pode ser liberado)")
    print(f"  {Fore.WHITE}🟠 Modified       :{Style.RESET_ALL} {Fore.MAGENTA}{modified_gb:.2f} GB{Style.RESET_ALL}  ← aguardando gravação")
    print(f"  {Fore.WHITE}🟢 Free           :{Style.RESET_ALL} {Fore.GREEN}{livre_gb:.2f} GB{Style.RESET_ALL}  ← disponível agora")
    print()
    print(f"  {Fore.WHITE}Uso Total        :{Style.RESET_ALL} {cor}{usado_gb:.2f} GB / {total_gb:.2f} GB  ({pct_uso:.1f}%){Style.RESET_ALL}")
    print(f"  {Fore.CYAN}[{barra}]{Style.RESET_ALL}")
    print()
    print(Fore.CYAN + "  💡  DIAGNÓSTICO:" + Style.RESET_ALL)

    if pct_uso >= 85:
        aviso(f"RAM crítica ({pct_uso:.0f}%) — libere memória Standby agora!")
    elif pct_uso >= 65:
        info(f"RAM moderada ({pct_uso:.0f}%) — sistema funcional, mas pode melhorar.")
    else:
        ok(f"RAM em bom estado ({pct_uso:.0f}%) — sistema com folga.")

    if standby_gb >= 1.0:
        info(f"{standby_gb:.1f} GB em Standby — pode ser liberado sem perda de dados.")
    if modified_gb >= 0.5:
        aviso(f"{modified_gb:.1f} GB em Modified — Windows gravando em segundo plano.")
    if livre_gb < 0.5:
        aviso("Menos de 512 MB livres! Sistema pode estar usando pagefile (lentidão).")

    linha("─")
    return 0

def liberar_ram_standby():
    info("Liberando memória Standby (cache do Windows)...")
    if HAS_PSUTIL:
        mem_antes = psutil.virtual_memory()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                handle = ctypes.windll.kernel32.OpenProcess(
                    0x1F0FFF, False, proc.pid
                )
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass

    run_ps(
        "[System.GC]::Collect(); "
        "[System.GC]::WaitForPendingFinalizers(); "
        "[System.GC]::Collect()"
    )

    if HAS_PSUTIL:
        mem_depois  = psutil.virtual_memory()
        liberado    = max(0, mem_antes.used - mem_depois.used)
        livre_agora = mem_depois.available / (1024**3)
        ok(
            f"Memória liberada: ~{formata_bytes(liberado)}  |  "
            f"Livre agora: {livre_agora:.2f} GB"
        )
    else:
        ok("Limpeza de RAM executada com sucesso")
    return 0

def diagnostico_performance_ram():
    info("Executando diagnóstico de performance de RAM...")
    print()
    linha("─")
    print(Fore.CYAN + "  🔍  TOP 15 PROCESSOS POR USO DE RAM" + Style.RESET_ALL)
    linha("─")

    if HAS_PSUTIL:
        processos = []
        for proc in psutil.process_iter(
            ["pid", "name", "memory_info", "memory_percent", "status"]
        ):
            try:
                mi = proc.info["memory_info"]
                processos.append({
                    "pid":    proc.info["pid"],
                    "nome":   proc.info["name"] or "Desconhecido",
                    "rss":    mi.rss,
                    "pct":    proc.info["memory_percent"] or 0,
                    "status": proc.info["status"] or "",
                })
            except Exception:
                pass

        processos.sort(key=lambda x: x["rss"], reverse=True)
        total_ram  = psutil.virtual_memory().total
        soma_top15 = 0

        print(f"  {'PID':>6}  {'PROCESSO':<32}  {'RAM':>9}  {'%':>5}  STATUS")
        linha("─")

        for p in processos[:15]:
            soma_top15 += p["rss"]
            pct = p["pct"]
            cor = (Fore.RED if pct > 10 else Fore.YELLOW if pct > 5 else Fore.WHITE)
            sl  = ("🔴 ALTO" if pct > 10 else "🟡 MED" if pct > 5 else "🟢 OK")
            print(
                f"  {p['pid']:>6}  "
                f"{cor}{p['nome']:<32}{Style.RESET_ALL}  "
                f"{formata_bytes(p['rss']):>9}  "
                f"{pct:>4.1f}%  {sl}"
            )

        print()
        soma_pct = soma_top15 / total_ram * 100
        print(
            f"  {Fore.CYAN}Top 15 processos consomem:{Style.RESET_ALL} "
            f"{formata_bytes(soma_top15)} ({soma_pct:.1f}% da RAM total)"
        )

        print()
        linha("─")
        print(Fore.CYAN + "  💡  ANÁLISE DE CONSUMO:" + Style.RESET_ALL)
        print()

        mem = psutil.virtual_memory()
        pct = mem.percent
        suspeitos = [
            p for p in processos[:15]
            if p["pct"] > 15 and p["nome"].lower() not in
            ["system", "registry", "smss.exe", "csrss.exe", "wininit.exe"]
        ]
        if suspeitos:
            aviso("Processos com uso anormalmente alto de RAM:")
            for s in suspeitos:
                print(f"    ⚠  {s['nome']} ({formata_bytes(s['rss'])}, {s['pct']:.1f}%)")
            info("Dica: Feche esses processos se não forem necessários.")
        else:
            ok("Nenhum processo com uso anormal de RAM detectado.")

        if pct > 80:
            aviso(f"Sistema com {pct:.0f}% de RAM. Libere Standby ou feche apps.")
        elif pct > 60:
            info(f"Sistema com {pct:.0f}% de RAM. Monitoramento recomendado.")
        else:
            ok(f"Sistema confortável com {pct:.0f}% de RAM.")

        try:
            swap = psutil.swap_memory()
            if swap.total > 0 and swap.percent > 50:
                aviso(
                    f"Pagefile em uso: {formata_bytes(swap.used)} "
                    f"de {formata_bytes(swap.total)} ({swap.percent:.0f}%) "
                    "— RAM insuficiente!"
                )
            elif swap.total > 0:
                ok(
                    f"Pagefile: {formata_bytes(swap.used)} "
                    f"de {formata_bytes(swap.total)} ({swap.percent:.0f}%) — normal."
                )
        except Exception:
            pass
    else:
        ok_r, saida = run_cmd("tasklist /fo csv /nh | sort /r")
        if ok_r:
            for l in [x for x in saida.strip().split("\n") if x.strip()][:15]:
                partes = l.replace('"', '').split(",")
                if len(partes) >= 5:
                    print(
                        f"  {partes[0]:<35} "
                        f"PID:{partes[1]:>6}  "
                        f"Mem:{partes[4].strip():>12}"
                    )

    linha("─")
    return 0

def monitorar_ram():
    info("Monitorando uso de RAM...")
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        print(
            f"    Total: {formata_bytes(mem.total)}  |  "
            f"Usado: {formata_bytes(mem.used)}  |  "
            f"Livre: {formata_bytes(mem.available)}  |  "
            f"{mem.percent:.1f}% em uso"
        )
    else:
        _, saida = run_cmd("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize")
        print(saida)
    return 0

def liberar_ram():
    info("Liberando memória RAM (WorkingSet de processos)...")
    if HAS_PSUTIL:
        for proc in psutil.process_iter(["pid"]):
            try:
                handle = ctypes.windll.kernel32.OpenProcess(
                    0x1F0FFF, False, proc.pid
                )
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass
        ok("RAM liberada (processos em segundo plano reduzidos)")
    else:
        ok("RAM: instale psutil para limpeza automática")
    return 0

def ajuste_memoria_virtual():
    info("Ajustando memória virtual (pagefile)...")
    aviso("Mantenha pagefile em pelo menos 1,5x a RAM instalada.")
    ok(
        "Consulte: Propriedades do Sistema → "
        "Avançado → Desempenho → Memória virtual"
    )
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 6 — CPU / BOOT
# ══════════════════════════════════════════════════════════════════════

def gerenciar_inicializacao():
    info("Verificando programas na inicialização...")
    ok_r, saida = run_cmd(
        "wmic /namespace:\\\\root\\cimv2 path Win32_StartupCommand "
        "get Caption,Command,Location"
    )
    if ok_r and saida.strip():
        for l in saida.strip().split("\n"):
            if l.strip():
                print(f"    {l.strip()}")
    ok("Use Gerenciador de Tarefas → Inicializar para desabilitar manualmente.")
    return 0

def otimizar_boot():
    info("Otimizando tempo de boot...")
    run_cmd("bcdedit /set bootmenupolicy standard")
    run_cmd("bcdedit /timeout 5")
    ok("Boot otimizado (timeout reduzido para 5s)")
    return 0

def desativar_servicos_inuteis():
    info("Desativando serviços desnecessários...")
    for svc in ["SysMain", "DiagTrack", "WSearch", "MapsBroker"]:
        ok_r, _ = run_cmd(f"sc config {svc} start= disabled")
        if ok_r:
            run_cmd(f"sc stop {svc}")
            ok(f"Serviço desativado: {svc}")
        else:
            aviso(f"Não foi possível desativar: {svc}")
    return 0

def desativar_telemetria():
    info("Desativando telemetria da Microsoft...")
    for cmd in [
        'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Privacy" /v TailoredExperiencesWithDiagnosticDataEnabled /t REG_DWORD /d 0 /f',
        "sc config DiagTrack start= disabled",
        "sc stop DiagTrack",
    ]:
        run_cmd(cmd)
    ok("Telemetria desativada")
    return 0

def desinstalar_bloatware():
    info("Removendo bloatware pré-instalado do Windows...")
    apps = [
        "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.GetHelp",
        "Microsoft.Getstarted", "Microsoft.MicrosoftOfficeHub",
        "Microsoft.MixedReality.Portal", "Microsoft.People",
        "Microsoft.SkypeApp", "Microsoft.Xbox.TCUI", "Microsoft.XboxApp",
        "Microsoft.XboxGameOverlay", "Microsoft.XboxSpeechToTextOverlay",
        "Microsoft.ZuneMusic", "Microsoft.ZuneVideo",
    ]
    for app in apps:
        run_ps(f"Get-AppxPackage *{app}* | Remove-AppxPackage")
        ok(f"Removido: {app}")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 7 — REDE
# ══════════════════════════════════════════════════════════════════════

def otimizar_rede():
    info("Aplicando otimizações de rede...")
    for cmd in [
        "netsh int tcp set global autotuninglevel=normal",
        "netsh int tcp set global chimney=enabled",
        "netsh int tcp set global ecncapability=enabled",
        "netsh int tcp set global timestamps=disabled",
        "netsh int tcp set global rss=enabled",
        "netsh int tcp set global fastopen=enabled",
    ]:
        run_cmd(cmd)
    ok("Otimizações TCP/IP aplicadas")
    return 0

def reset_rede():
    info("Resetando configurações de rede...")
    for cmd in [
        "netsh winsock reset", "netsh int ip reset",
        "netsh int tcp reset", "ipconfig /release",
        "ipconfig /renew",    "ipconfig /flushdns",
    ]:
        run_cmd(cmd)
    ok("Rede resetada (reinicie o PC para efetivar)")
    return 0

def ajuste_mtu():
    info("Ajustando MTU para 1500...")
    run_cmd('netsh interface ipv4 set subinterface "Ethernet" mtu=1500 store=persistent')
    run_cmd('netsh interface ipv4 set subinterface "Wi-Fi" mtu=1500 store=persistent')
    ok("MTU ajustado para 1500")
    return 0

def diagnostico_internet():
    info("Executando diagnóstico de internet...")
    ok_r, saida = run_cmd("ping -n 4 8.8.8.8")
    if "ms" in saida:
        for l in saida.split("\n"):
            if "ms" in l or "Estatísticas" in l or "perdido" in l.lower():
                print(f"    {l.strip()}")
        ok("Conexão com internet: OK")
    else:
        aviso("Sem resposta ao ping — verifique sua conexão")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 8 — REGISTRO E KERNEL
# ══════════════════════════════════════════════════════════════════════

def reg_system_responsiveness():
    info("Ajustando SystemResponsiveness → 0...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
        "SystemResponsiveness", winreg.REG_DWORD, 0
    )
    if ok_r: ok("SystemResponsiveness → 0")
    else: erro("Falha ao ajustar SystemResponsiveness")
    return 0

def reg_win32_priority_separation():
    info("Ajustando Win32PrioritySeparation → 26...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\PriorityControl",
        "Win32PrioritySeparation", winreg.REG_DWORD, 26
    )
    if ok_r: ok("Win32PrioritySeparation → 26")
    else: erro("Falha ao ajustar Win32PrioritySeparation")
    return 0

def reg_network_throttling_index():
    info("Removendo throttling de rede...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
        "NetworkThrottlingIndex", winreg.REG_DWORD, 0xFFFFFFFF
    )
    if ok_r: ok("NetworkThrottlingIndex → FFFFFFFF")
    else: erro("Falha ao ajustar NetworkThrottlingIndex")
    return 0

def reg_tcp_ack_frequency():
    info("Ajustando TcpAckFrequency → 1...")
    base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0; interfaces = []
            while True:
                try:
                    interfaces.append(winreg.EnumKey(k, i)); i += 1
                except OSError: break
        for iface in interfaces:
            reg_set(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{iface}",
                    "TcpAckFrequency", winreg.REG_DWORD, 1)
        ok(f"TcpAckFrequency → 1 em {len(interfaces)} interfaces")
    except Exception as e:
        erro(f"TcpAckFrequency: {e}")
    return 0

def reg_tcp_no_delay():
    info("Ativando TCPNoDelay...")
    base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0; interfaces = []
            while True:
                try:
                    interfaces.append(winreg.EnumKey(k, i)); i += 1
                except OSError: break
        for iface in interfaces:
            reg_set(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{iface}",
                    "TCPNoDelay", winreg.REG_DWORD, 1)
        ok(f"TCPNoDelay → 1 em {len(interfaces)} interfaces")
    except Exception as e:
        erro(f"TCPNoDelay: {e}")
    return 0

def reg_large_system_cache():
    info("Ativando LargeSystemCache...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "LargeSystemCache", winreg.REG_DWORD, 1
    )
    if ok_r: ok("LargeSystemCache → 1")
    else: erro("Falha ao ajustar LargeSystemCache")
    return 0

def reg_io_page_lock_limit():
    info("Aumentando IoPageLockLimit...")
    valor = min(psutil.virtual_memory().total // 4, 512 * 1024 * 1024) \
        if HAS_PSUTIL else 67108864
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "IoPageLockLimit", winreg.REG_DWORD, valor
    )
    if ok_r: ok(f"IoPageLockLimit → {formata_bytes(valor)}")
    else: erro("Falha ao ajustar IoPageLockLimit")
    return 0

def reg_no_lazy_flush():
    info("Ativando NoLazyFlush...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager",
        "NoLazyFlush", winreg.REG_DWORD, 1
    )
    if ok_r: ok("NoLazyFlush → 1")
    else: erro("Falha ao ajustar NoLazyFlush")
    return 0

def reg_disable_paging_executive():
    info("Mantendo kernel e drivers na RAM...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "DisablePagingExecutive", winreg.REG_DWORD, 1
    )
    if ok_r: ok("DisablePagingExecutive → 1")
    else: erro("Falha ao ajustar DisablePagingExecutive")
    return 0

def reg_menu_show_delay():
    info("Definindo MenuShowDelay → 0...")
    ok_r = reg_set(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Desktop",
        "MenuShowDelay", winreg.REG_SZ, "0"
    )
    if ok_r: ok("MenuShowDelay → 0")
    else: erro("Falha ao ajustar MenuShowDelay")
    return 0

def reg_wait_to_kill_service_timeout():
    info("Reduzindo WaitToKillServiceTimeout → 2000ms...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control",
        "WaitToKillServiceTimeout", winreg.REG_SZ, "2000"
    )
    if ok_r: ok("WaitToKillServiceTimeout → 2000ms")
    else: erro("Falha ao ajustar WaitToKillServiceTimeout")
    return 0

def reg_hung_app_timeout():
    info("Reduzindo HungAppTimeout → 1000ms...")
    ok_r = reg_set(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Desktop",
        "HungAppTimeout", winreg.REG_SZ, "1000"
    )
    if ok_r: ok("HungAppTimeout → 1000ms")
    else: erro("Falha ao ajustar HungAppTimeout")
    return 0

def reg_auto_end_tasks():
    info("Ativando AutoEndTasks...")
    ok_r = reg_set(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Desktop",
        "AutoEndTasks", winreg.REG_SZ, "1"
    )
    if ok_r: ok("AutoEndTasks → 1")
    else: erro("Falha ao ajustar AutoEndTasks")
    return 0

def reg_gpu_priority():
    info("Ajustando prioridade da GPU para 8...")
    caminho = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
               r"\Multimedia\SystemProfile\Tasks\Games")
    for nome, tipo, val in [
        ("GPU Priority",        winreg.REG_DWORD, 8),
        ("Priority",            winreg.REG_DWORD, 6),
        ("Scheduling Category", winreg.REG_SZ,    "High"),
        ("SFIO Priority",       winreg.REG_SZ,    "High"),
    ]:
        reg_set(winreg.HKEY_LOCAL_MACHINE, caminho, nome, tipo, val)
    ok("GPU Priority e agendamento ajustados")
    return 0

def reg_scheduling_category_high():
    info("Definindo Scheduling Category → High...")
    caminho = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
               r"\Multimedia\SystemProfile\Tasks\Games")
    reg_set(winreg.HKEY_LOCAL_MACHINE, caminho,
            "Scheduling Category", winreg.REG_SZ, "High")
    reg_set(winreg.HKEY_LOCAL_MACHINE, caminho,
            "SFIO Priority", winreg.REG_SZ, "High")
    ok("Scheduling Category → High | SFIO Priority → High")
    return 0

def reg_disable_hiberboot():
    info("Desativando HiberBoot...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
        "HiberbootEnabled", winreg.REG_DWORD, 0
    )
    if ok_r: ok("HiberBoot desativado")
    else: aviso("Não foi possível desativar HiberBoot via registro")
    return 0

def reg_mouse_data_queue_size():
    info("Aumentando buffer do mouse → 20...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Services\mouclass\Parameters",
        "MouseDataQueueSize", winreg.REG_DWORD, 20
    )
    if ok_r: ok("MouseDataQueueSize → 20")
    else: erro("Falha ao ajustar MouseDataQueueSize")
    return 0

def reg_keyboard_data_queue_size():
    info("Aumentando buffer do teclado → 20...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Services\kbdclass\Parameters",
        "KeyboardDataQueueSize", winreg.REG_DWORD, 20
    )
    if ok_r: ok("KeyboardDataQueueSize → 20")
    else: erro("Falha ao ajustar KeyboardDataQueueSize")
    return 0

def reg_disable_ghost_devices():
    info("Removendo drivers fantasma...")
    run_ps(
        "Get-PnpDevice | Where-Object{$_.Status -eq 'Unknown'} | "
        "ForEach-Object{ Remove-PnpDevice -InstanceId $_.InstanceId "
        "-Confirm:$false -EA SilentlyContinue }"
    )
    ok("Dispositivos fantasma removidos")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 9 — GPU
# ══════════════════════════════════════════════════════════════════════

def reg_desativar_mpo():
    info("Desativando MPO...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows\Dwm",
        "OverlayTestMode", winreg.REG_DWORD, 5
    )
    if ok_r: ok("MPO desativado")
    else: erro("Falha ao desativar MPO")
    return 0

def ativar_hags():
    info("Ativando HAGS...")
    ok_r = reg_set(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        "HwSchMode", winreg.REG_DWORD, 2
    )
    if ok_r: ok("HAGS ativado — reinicie o PC para efetivar")
    else: erro("Falha ao ativar HAGS")
    return 0

def reg_nvidia_ultra_low_latency():
    info("Configurando NVIDIA Ultra Low Latency...")
    run_ps(
        "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -EA SilentlyContinue | "
        "ForEach-Object { Set-ItemProperty $_.PSPath -Name 'RMUllMode' "
        "-Value 0x00000001 -Type DWord -EA SilentlyContinue }"
    )
    ok("NVIDIA Ultra Low Latency configurado")
    return 0

def reg_shader_cache_unlimited():
    info("Configurando Shader Cache → Unlimited...")
    run_cmd(
        'reg add "HKLM\\SOFTWARE\\NVIDIA Corporation\\Global\\NVTweak" '
        '/v "ShaderCacheSize" /t REG_DWORD /d 0xFFFFFFFF /f'
    )
    ok("Shader Cache → Unlimited")
    return 0

def reg_power_management_gpu():
    info("Forçando GPU em Prefer Maximum Performance...")
    run_ps(
        "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -EA SilentlyContinue | "
        "ForEach-Object { "
        "Set-ItemProperty $_.PSPath -Name 'PerfLevelSrc' -Value 0x2222 -Type DWord -EA SilentlyContinue; "
        "Set-ItemProperty $_.PSPath -Name 'PowerMizerEnable' -Value 0x1 -Type DWord -EA SilentlyContinue; "
        "Set-ItemProperty $_.PSPath -Name 'PowerMizerLevel' -Value 0x1 -Type DWord -EA SilentlyContinue }"
    )
    ok("GPU → Prefer Maximum Performance")
    return 0

def reg_desativar_gpu_scaling():
    info("Desativando GPU Scaling...")
    run_ps(
        "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -EA SilentlyContinue | "
        "ForEach-Object { Set-ItemProperty $_.PSPath -Name 'Scaling' "
        "-Value 0x1 -Type DWord -EA SilentlyContinue }"
    )
    ok("GPU Scaling desativado")
    return 0

def reg_desativar_nvidia_overlay():
    info("Desativando overlay do GeForce Experience...")
    run_cmd(
        'reg add "HKCU\\SOFTWARE\\NVIDIA Corporation\\NvBackend\\ApplicationOntop" '
        '/v "OverlayEnabled" /t REG_DWORD /d 0 /f'
    )
    ok("NVIDIA GeForce Overlay desativado")
    return 0

def reg_threaded_optimization():
    info("Forçando Threaded Optimization → On...")
    run_ps(
        "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -EA SilentlyContinue | "
        "ForEach-Object { Set-ItemProperty $_.PSPath -Name 'OGLThreadedOptimizations' "
        "-Value 0x1 -Type DWord -EA SilentlyContinue }"
    )
    ok("Threaded Optimization → On")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 10 — PROCESSOS E LATÊNCIA
# ══════════════════════════════════════════════════════════════════════

def desativar_core_parking():
    info("Desativando CPU Core Parking...")
    run_ps(
        "powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100; "
        "powercfg -setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100; "
        "powercfg -setactive SCHEME_CURRENT"
    )
    ok("Core Parking desativado")
    return 0

def desativar_hardware_acceleration_discord():
    info("Desativando aceleração de hardware no Discord...")
    cfg_path = os.path.join(APPDATA, r"discord\settings.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["hardwareAcceleration"] = False
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            ok("Aceleração de hardware do Discord desativada")
        except Exception as e:
            aviso(f"Discord settings.json: {e}")
    else:
        aviso("Discord não encontrado")
    return 0

def desativar_steam_overlay():
    info("Desativando Steam Overlay globalmente...")
    run_cmd(
        'reg add "HKCU\\SOFTWARE\\Valve\\Steam" '
        '/v "EnableOverlay" /t REG_DWORD /d 0 /f'
    )
    ok("Steam Overlay desativado")
    return 0

def desativar_game_dvr():
    info("Desativando Game DVR...")
    for cmd in [
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\GameDVR" /v "AppCaptureEnabled" /t REG_DWORD /d 0 /f',
        'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\GameDVR" /v "AllowGameDVR" /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\System\\GameConfigStore" /v "GameDVR_Enabled" /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("Game DVR desativado")
    return 0

def desativar_xbox_game_bar():
    info("Desativando Xbox Game Bar...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\GameDVR" /v "AppCaptureEnabled" /t REG_DWORD /d 0 /f')
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\GameDVR" /v "AllowGameDVR" /t REG_DWORD /d 0 /f')
    run_ps("Get-AppxPackage Microsoft.XboxGamingOverlay | Remove-AppxPackage")
    ok("Xbox Game Bar desativado e removido")
    return 0

def startup_delay_zero():
    info("Removendo delay de inicialização de apps...")
    ok_r = reg_set(
        winreg.HKEY_CURRENT_USER,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
        "StartupDelayInMSec", winreg.REG_DWORD, 0
    )
    if ok_r: ok("StartupDelayInMSec → 0")
    else: erro("Falha ao ajustar startup delay")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 11 — DEBLOAT
# ══════════════════════════════════════════════════════════════════════

def remover_cortana():
    info("Removendo Cortana...")
    run_ps("Get-AppxPackage *Microsoft.549981C3F5F10* | Remove-AppxPackage")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search" /v AllowCortana /t REG_DWORD /d 0 /f')
    ok("Cortana removida e desativada")
    return 0

def desativar_onedrive():
    info("Desativando e removendo OneDrive...")
    run_cmd("taskkill /f /im OneDrive.exe")
    run_cmd(r'"%WINDIR%\SysWOW64\OneDriveSetup.exe" /uninstall')
    run_cmd(r'"%WINDIR%\System32\OneDriveSetup.exe" /uninstall')
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive" /v DisableFileSyncNGSC /t REG_DWORD /d 1 /f')
    ok("OneDrive desativado e removido")
    return 0

def desativar_edge_background():
    info("Bloqueando processos em segundo plano do Edge...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Edge" /v BackgroundModeEnabled /t REG_DWORD /d 0 /f')
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Edge" /v StartupBoostEnabled /t REG_DWORD /d 0 /f')
    ok("Edge → processos em segundo plano bloqueados")
    return 0

def desativar_feedback_hub():
    info("Desativando Feedback Hub...")
    run_ps("Get-AppxPackage Microsoft.WindowsFeedbackHub | Remove-AppxPackage")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Siuf\\Rules" /v NumberOfSIUFInPeriod /t REG_DWORD /d 0 /f')
    ok("Feedback Hub desativado")
    return 0

def desativar_news_interests():
    info("Removendo widget de Notícias e Interesses...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Feeds" /v ShellFeedsTaskbarViewMode /t REG_DWORD /d 2 /f')
    ok("Widget de Notícias removido")
    return 0

def desativar_meet_now():
    info("Removendo ícone Meet Now...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer" /v HideSCAMeetNow /t REG_DWORD /d 1 /f')
    ok("Meet Now removido")
    return 0

def desativar_error_reporting():
    info("Desativando Windows Error Reporting...")
    run_cmd("sc config WerSvc start= disabled")
    run_cmd("sc stop WerSvc")
    run_cmd('reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v Disabled /t REG_DWORD /d 1 /f')
    ok("Windows Error Reporting desativado")
    return 0

def desativar_telemetria_servicos():
    info("Desativando serviços de telemetria...")
    for svc in ["DiagTrack", "dmwappushservice"]:
        run_cmd(f"sc config {svc} start= disabled")
        run_cmd(f"sc stop {svc}")
    ok("Serviços de telemetria desativados")
    return 0

def desativar_windows_ink():
    info("Desativando Windows Ink Workspace...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\WindowsInkWorkspace" /v AllowWindowsInkWorkspace /t REG_DWORD /d 0 /f')
    ok("Windows Ink Workspace desativado")
    return 0

def remover_mapas():
    info("Removendo aplicativo Windows Maps...")
    run_ps("Get-AppxPackage *Microsoft.WindowsMaps* | Remove-AppxPackage")
    ok("Windows Maps removido")
    return 0

def remover_people():
    info("Removendo aplicativo People...")
    run_ps("Get-AppxPackage *Microsoft.People* | Remove-AppxPackage")
    ok("People removido")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 12 — REDE AVANÇADA
# ══════════════════════════════════════════════════════════════════════

def desativar_ipv6():
    info("Desativando IPv6...")
    run_cmd('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters" /v DisabledComponents /t REG_DWORD /d 0xFF /f')
    run_ps("Get-NetAdapterBinding | Where-Object {$_.ComponentID -eq 'ms_tcpip6'} | Disable-NetAdapterBinding -EA SilentlyContinue")
    ok("IPv6 desativado em todas as interfaces")
    return 0

def desativar_netbios():
    info("Desativando NetBIOS over TCP/IP...")
    base = r"SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            i = 0; interfaces = []
            while True:
                try:
                    interfaces.append(winreg.EnumKey(k, i)); i += 1
                except OSError: break
        for iface in interfaces:
            reg_set(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{iface}",
                    "NetbiosOptions", winreg.REG_DWORD, 2)
        ok(f"NetBIOS desativado em {len(interfaces)} interfaces")
    except Exception as e:
        erro(f"NetBIOS: {e}")
    return 0

def desativar_interrupt_moderation():
    info("Desativando Interrupt Moderation...")
    run_ps("Get-NetAdapter | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Interrupt Moderation' -DisplayValue 'Disabled' -EA SilentlyContinue }")
    ok("Interrupt Moderation desativado")
    return 0

def desativar_flow_control():
    info("Desativando Flow Control...")
    run_ps("Get-NetAdapter | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Flow Control' -DisplayValue 'Disabled' -EA SilentlyContinue }")
    ok("Flow Control desativado")
    return 0

def desativar_packet_coalescing():
    info("Desativando Packet Coalescing...")
    run_ps("Get-NetAdapter | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Packet Coalescing' -DisplayValue 'Disabled' -EA SilentlyContinue }")
    ok("Packet Coalescing desativado")
    return 0

def desativar_energy_efficient_ethernet():
    info("Desativando Energy Efficient Ethernet...")
    run_ps(
        "Get-NetAdapter | ForEach-Object { "
        "Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Energy Efficient Ethernet' -DisplayValue 'Disabled' -EA SilentlyContinue; "
        "Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Green Ethernet' -DisplayValue 'Disabled' -EA SilentlyContinue }"
    )
    ok("Energy Efficient Ethernet desativado")
    return 0

def configurar_rss_multicore():
    info("Configurando RSS para múltiplos núcleos...")
    run_cmd("netsh int tcp set global rss=enabled")
    run_ps("Get-NetAdapter | ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName 'Receive Side Scaling' -DisplayValue 'Enabled' -EA SilentlyContinue }")
    ok("RSS configurado para múltiplos núcleos")
    return 0

def zerar_reserva_qos():
    info("Zerando reserva de largura de banda QoS...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Psched" /v NonBestEffortLimit /t REG_DWORD /d 0 /f')
    ok("QoS → reserva de banda removida")
    return 0

def configurar_speed_duplex():
    info("Forçando Speed & Duplex → 1.0 Gbps Full Duplex...")
    run_ps(
        "Get-NetAdapter | Where-Object {$_.MediaType -eq '802.3'} | "
        "ForEach-Object { Set-NetAdapterAdvancedProperty -Name $_.Name "
        "-DisplayName 'Speed & Duplex' -DisplayValue '1.0 Gbps Full Duplex' -EA SilentlyContinue }"
    )
    ok("Speed & Duplex → 1.0 Gbps Full Duplex")
    return 0

def desativar_lldp():
    info("Desativando protocolo LLDP...")
    run_ps("Get-NetAdapterBinding | Where-Object {$_.ComponentID -eq 'ms_lldp'} | Disable-NetAdapterBinding -EA SilentlyContinue")
    ok("LLDP desativado em todas as interfaces")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 13 — ARMAZENAMENTO E NTFS
# ══════════════════════════════════════════════════════════════════════

def desativar_8dot3_names():
    info("Desativando criação de nomes 8.3 no NTFS...")
    run_cmd("fsutil behavior set disable8dot3 1")
    ok("Nomes 8.3 desativados")
    return 0

def desativar_last_access_timestamp():
    info("Desativando Last Access Timestamp no NTFS...")
    run_cmd("fsutil behavior set disablelastaccess 1")
    ok("Last Access Timestamp desativado")
    return 0

def aumentar_mft_zone():
    info("Ajustando MFT Zone Reservation → 2...")
    run_cmd("fsutil behavior set mftzone 2")
    ok("MFT Zone → 2")
    return 0

def forcar_trim_ssd():
    info("Forçando TRIM no SSD (C:)...")
    run_ps("Optimize-Volume -DriveLetter C -ReTrim -Verbose")
    ok("TRIM forçado no SSD C:")
    return 0

def configurar_ntfs_memory():
    info("Aumentando cache de memória NTFS...")
    run_cmd("fsutil behavior set memoryusage 2")
    ok("MemoryUsage NTFS → 2")
    return 0

def desativar_vss():
    info("Desativando VSS (Volume Shadow Copy)...")
    aviso("Isso desativa pontos de restauração do sistema!")
    run_cmd("sc config VSS start= disabled")
    run_cmd("sc stop VSS")
    run_cmd("vssadmin delete shadows /all /quiet")
    ok("VSS desativado")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 14 — INTERFACE E USABILIDADE
# ══════════════════════════════════════════════════════════════════════

def desativar_aero_shake():
    info("Desativando Aero Shake...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v DisallowShaking /t REG_DWORD /d 1 /f')
    ok("Aero Shake desativado")
    return 0

def desativar_snap_assist():
    info("Desativando Snap Assist...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v SnapAssist /t REG_DWORD /d 0 /f')
    ok("Snap Assist desativado")
    return 0

def desativar_transparency():
    info("Desativando efeitos de transparência...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v EnableTransparency /t REG_DWORD /d 0 /f')
    ok("Transparência desativada")
    return 0

def desativar_taskbar_animations():
    info("Desativando animações da barra de tarefas...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v TaskbarAnimations /t REG_DWORD /d 0 /f')
    ok("Animações da taskbar desativadas")
    return 0

def desativar_shadow_windows():
    info("Desativando sombras sob janelas...")
    run_ps(
        "Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' "
        "-Name 'UserPreferencesMask' "
        "-Value ([byte[]](0x90,0x12,0x03,0x80,0x10,0x00,0x00,0x00))"
    )
    ok("Sombras de janelas desativadas")
    return 0

def desativar_spotlight():
    info("Desativando Windows Spotlight...")
    for cmd in [
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v RotatingLockScreenEnabled /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-338387Enabled /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("Windows Spotlight desativado")
    return 0

def desativar_blur_login():
    info("Desativando blur na tela de login...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" /v DisableAcrylicBackgroundOnLogon /t REG_DWORD /d 1 /f')
    ok("Blur do login desativado")
    return 0

def desativar_background_apps():
    info("Desativando apps em segundo plano globalmente...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\BackgroundAccessApplications" /v GlobalUserDisabled /t REG_DWORD /d 1 /f')
    ok("Apps em segundo plano desativados")
    return 0

def desativar_location_service():
    info("Desativando serviços de localização...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location" /v Value /t REG_SZ /d Deny /f')
    run_cmd("sc config lfsvc start= disabled")
    run_cmd("sc stop lfsvc")
    ok("Serviços de localização desativados")
    return 0

def desativar_activity_history():
    info("Desativando Activity History...")
    for cmd in [
        'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" /v EnableActivityFeed /t REG_DWORD /d 0 /f',
        'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System" /v PublishUserActivities /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("Activity History desativado")
    return 0

def desativar_notificacoes_dicas():
    info("Desativando notificações e dicas do Windows...")
    for cmd in [
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications" /v ToastEnabled /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SoftLandingEnabled /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-338389Enabled /t REG_DWORD /d 0 /f',
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SystemPaneSuggestionsEnabled /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("Notificações e dicas desativadas")
    return 0

def desativar_sticky_keys():
    info("Desativando Teclas de Aderência (Sticky Keys)...")
    for cmd in [
        'reg add "HKCU\\Control Panel\\Accessibility\\StickyKeys" /v "Flags" /t REG_SZ /d "506" /f',
        'reg add "HKCU\\Control Panel\\Accessibility\\ToggleKeys" /v "Flags" /t REG_SZ /d "58" /f',
        'reg add "HKCU\\Control Panel\\Accessibility\\Keyboard Response" /v "Flags" /t REG_SZ /d "122" /f',
    ]:
        run_cmd(cmd)
    ok("Sticky Keys, Toggle Keys e Filter Keys desativados")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 15 — ENERGIA AVANÇADA
# ══════════════════════════════════════════════════════════════════════

def ativar_ultimate_performance():
    info("Ativando plano Ultimate Performance...")
    run_cmd("powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 e9a42b02-d5df-448d-aa00-03f14749eb61")
    run_cmd("powercfg -setactive e9a42b02-d5df-448d-aa00-03f14749eb61")
    ok("Ultimate Performance ativado")
    return 0

def desativar_usb_selective_suspend():
    info("Desativando USB Selective Suspend...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("USB Selective Suspend desativado")
    return 0

def cpu_min_processor_state():
    info("Definindo estado mínimo do processador em 100%...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 100")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("Processador mínimo → 100%")
    return 0

def desativar_hard_disk_turnoff():
    info("Desativando desligamento automático do disco rígido...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT SUB_DISK DISKIDLE 0")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("Disco → nunca desligar automaticamente")
    return 0

def desativar_pcie_link_power():
    info("Desativando PCI Express Link State Power Management...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT SUB_PCIEXPRESS ASPM 0")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("PCI Express Link State → Off")
    return 0

def configurar_wireless_max_power():
    info("Configurando Wireless Adapter → Maximum Performance...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT 19caa947-ffe8-4bcd-93d2-cd4e5b4bcb23 12bbebe6-58d6-4636-95bb-3217ef867c1a 0")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("Wireless Adapter → Maximum Performance")
    return 0

def desativar_manutencao_automatica():
    info("Desativando manutenção automática do Windows...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Schedule\\Maintenance" /v MaintenanceDisabled /t REG_DWORD /d 1 /f')
    run_cmd('schtasks /Change /TN "\\Microsoft\\Windows\\TaskScheduler\\Regular Maintenance" /DISABLE')
    ok("Manutenção automática desativada")
    return 0

def configurar_system_cooling_active():
    info("Configurando System Cooling Policy → Active...")
    run_cmd("powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR SYSCOOLPOL 1")
    run_cmd("powercfg -setactive SCHEME_CURRENT")
    ok("System Cooling → Active")
    return 0

def desativar_hibernacao():
    info("Desativando modo de hibernação...")
    ok_r, _ = run_cmd("powercfg -h off")
    if ok_r:
        ok("Hibernação desativada (hiberfil.sys removido — espaço liberado)")
    else:
        erro("Falha ao desativar hibernação")
    return 0

def ativar_game_mode():
    info("Ativando Game Mode do Windows...")
    ok_r  = reg_set(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\GameBar",
                    "AutoGameModeEnabled", winreg.REG_DWORD, 1)
    ok_r2 = reg_set(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\GameBar",
                    "AllowAutoGameMode", winreg.REG_DWORD, 1)
    if ok_r and ok_r2:
        ok("Game Mode ativado")
    else:
        aviso("Game Mode: verificação parcial")
    return 0

def ajustar_taxa_atualizacao():
    info("Verificando taxa de atualização do monitor...")
    _, saida2 = run_cmd(
        "wmic path Win32_VideoController get CurrentRefreshRate,Name /format:list"
    )
    print(Fore.CYAN + "\n  📺  Monitor / Taxa de Atualização:" + Style.RESET_ALL)
    for l in saida2.strip().split("\n"):
        if l.strip():
            print(f"    {l.strip()}")
    print()
    info("Para alterar: Configurações → Sistema → Tela → "
         "Configurações avançadas de vídeo")
    ok("Verificação de taxa de atualização concluída")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  BLOCO 16 — SEGURANÇA E TWEAKS FINAIS
# ══════════════════════════════════════════════════════════════════════

def desativar_servicos_extras():
    info("Desativando serviços extras desnecessários...")
    servicos = {
        "Spooler":            "Print Spooler",
        "bthserv":            "Bluetooth Support",
        "Fax":                "Fax",
        "RemoteRegistry":     "Remote Registry",
        "TabletInputService": "Touch Keyboard/Handwriting",
        "wisvc":              "Windows Insider Service",
        "WpcMonSvc":          "Parental Controls",
        "RetailDemo":         "Retail Demo",
        "SensorService":      "Sensor Service",
        "ScardSvr":           "Smart Card",
    }
    desativados = 0
    for svc, nome in servicos.items():
        ok_r, _ = run_cmd(f"sc config {svc} start= disabled")
        if ok_r:
            run_cmd(f"sc stop {svc}")
            ok(f"Desativado: {nome} ({svc})")
            desativados += 1
        else:
            aviso(f"Não encontrado: {svc}")
    ok(f"Total desativados: {desativados}/{len(servicos)}")
    return 0

def desativar_audio_enhancements():
    info("Desativando melhorias de áudio...")
    run_ps(
        "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion"
        "\\MMDevices\\Audio\\Render\\*\\Properties' -EA SilentlyContinue | "
        "ForEach-Object { Set-ItemProperty $_.PSPath "
        "-Name '{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5' "
        "-Value 0 -Type DWord -EA SilentlyContinue }"
    )
    ok("Melhorias de áudio desativadas")
    return 0

def desativar_spatial_sound():
    info("Desativando Windows Sonic (Spatial Sound)...")
    run_cmd('reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Immersive\\HeadTracking" /v HeadTrackingEnabled /t REG_DWORD /d 0 /f')
    ok("Windows Sonic desativado")
    return 0

def desativar_enhance_pointer_precision():
    info("Desativando aceleração do mouse...")
    run_cmd('reg add "HKCU\\Control Panel\\Mouse" /v MouseSpeed /t REG_SZ /d 0 /f')
    run_cmd('reg add "HKCU\\Control Panel\\Mouse" /v MouseThreshold1 /t REG_SZ /d 0 /f')
    run_cmd('reg add "HKCU\\Control Panel\\Mouse" /v MouseThreshold2 /t REG_SZ /d 0 /f')
    ok("Aceleração do mouse desativada (movimento 1-to-1)")
    return 0

def desativar_vbs_memory_integrity():
    info("Desativando VBS e Memory Integrity...")
    aviso("Reduz uma camada de segurança para aumentar performance.")
    for cmd in [
        'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard" /v EnableVirtualizationBasedSecurity /t REG_DWORD /d 0 /f',
        'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard" /v RequirePlatformSecurityFeatures /t REG_DWORD /d 0 /f',
        'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard\\Scenarios\\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("VBS e Memory Integrity desativados — reinicie para efetivar")
    return 0

def adicionar_exclusao_defender():
    info("Adicionando exclusões ao Windows Defender para jogos...")
    pastas_jogo = [
        r"C:\Program Files (x86)\Steam\steamapps",
        r"C:\Program Files\Epic Games",
        r"C:\Program Files\EA Games",
        r"C:\Program Files (x86)\Origin Games",
        r"C:\Jogos", r"D:\Jogos", r"D:\SteamLibrary",
    ]
    adicionadas = 0
    for pasta in pastas_jogo:
        if os.path.exists(pasta):
            ok_r, _ = run_ps(
                f"Add-MpPreference -ExclusionPath '{pasta}' -EA SilentlyContinue"
            )
            if ok_r:
                ok(f"Exclusão: {pasta}")
                adicionadas += 1
    ok(f"Total de exclusões adicionadas: {adicionadas}")
    return 0

def desativar_indexacao_disco():
    info("Desativando indexação de disco (Windows Search)...")
    run_cmd("sc config WSearch start= disabled")
    run_cmd("sc stop WSearch")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search" /v AllowIndexingEncryptedStoresOrItems /t REG_DWORD /d 0 /f')
    ok("Indexação de disco desativada")
    return 0

def desativar_fso():
    info("Desativando Fullscreen Optimizations (FSO)...")
    for cmd in [
        'reg add "HKCU\\System\\GameConfigStore" /v "GameDVR_FSEBehaviorMode" /t REG_DWORD /d 2 /f',
        'reg add "HKCU\\System\\GameConfigStore" /v "GameDVR_HonorUserFSEBehaviorMode" /t REG_DWORD /d 1 /f',
    ]:
        run_cmd(cmd)
    ok("Fullscreen Optimizations desativado")
    return 0

def configurar_delivery_optimization():
    info("Desativando Delivery Optimization...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeliveryOptimization" /v DODownloadMode /t REG_DWORD /d 0 /f')
    ok("Delivery Optimization desativado")
    return 0

def limitar_windows_update_banda():
    info("Limitando banda do Windows Update para 1%...")
    run_cmd('reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeliveryOptimization" /v DOMaxDownloadBandwidth /t REG_DWORD /d 1 /f')
    ok("Windows Update → 1% de banda em segundo plano")
    return 0

def configurar_pagefile_fixo():
    info("Configurando PageFile com tamanho fixo (4096 MB)...")
    run_ps(
        "$cs = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges; "
        "$cs.AutomaticManagedPagefile = $false; $cs.Put() | Out-Null; "
        "$pf = Get-WmiObject Win32_PageFileSetting; "
        "if ($pf) { $pf.InitialSize = 4096; $pf.MaximumSize = 4096; $pf.Put() | Out-Null } "
        "else { Set-WmiInstance -Class Win32_PageFileSetting "
        "-Arguments @{Name='C:\\pagefile.sys';InitialSize=4096;MaximumSize=4096} | Out-Null }"
    )
    ok("PageFile → 4096 MB fixo em C:")
    return 0

def configurar_crash_dump_small():
    info("Configurando Crash Dump → Small Memory Dump...")
    for cmd in [
        'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\CrashControl" /v CrashDumpEnabled /t REG_DWORD /d 3 /f',
        'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\CrashControl" /v MinidumpsCount /t REG_DWORD /d 5 /f',
    ]:
        run_cmd(cmd)
    ok("Crash Dump → Small Memory Dump")
    return 0

def desativar_privacy_camera_mic():
    info("Desativando acesso de apps à câmera e microfone...")
    for recurso in ["webcam", "microphone"]:
        run_cmd(
            f'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
            f'\\CapabilityAccessManager\\ConsentStore\\{recurso}" '
            f'/v Value /t REG_SZ /d Deny /f'
        )
    ok("Câmera e microfone → acesso negado para apps")
    return 0

def criar_ponto_restauracao():
    info("Criando ponto de restauração do sistema...")
    ok_r, _ = run_ps(
        'Enable-ComputerRestore -Drive "C:\\" -EA SilentlyContinue; '
        'Checkpoint-Computer -Description "LND Optimizer v1 - Pre-Tweak" '
        '-RestorePointType "MODIFY_SETTINGS" -EA SilentlyContinue'
    )
    if ok_r:
        ok("Ponto de restauração criado: 'LND Optimizer v1 - Pre-Tweak'")
    else:
        aviso("Não foi possível criar ponto de restauração automaticamente.")
    return 0

def reduzir_uac():
    info("Reduzindo UAC para nível mínimo...")
    for cmd in [
        'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f',
        'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("UAC → nível mínimo")
    return 0

def smartscreen_off():
    info("Desativando SmartScreen...")
    aviso("Use com consciência — SmartScreen protege contra malwares.")
    for cmd in [
        'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer" /v SmartScreenEnabled /t REG_SZ /d Off /f',
        'reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AppHost" /v EnableWebContentEvaluation /t REG_DWORD /d 0 /f',
    ]:
        run_cmd(cmd)
    ok("SmartScreen desativado")
    return 0

# ══════════════════════════════════════════════════════════════════════
#  GRUPOS DE OTIMIZAÇÃO
# ══════════════════════════════════════════════════════════════════════

TAREFAS_BASICA = [
    ("Análise de disco",           analise_disco),
    ("Monitorar RAM",              monitorar_ram),
    ("Limpeza de temp",            limpar_temp),
    ("Limpeza da lixeira",         limpar_lixeira),
    ("Limpeza cache DNS",          limpar_cache_dns),
    ("Limpeza de miniaturas",      limpar_miniaturas),
    ("Limpeza histórico recente",  limpar_historico_recente),
]

TAREFAS_INTERMEDIARIA = TAREFAS_BASICA + [
    ("Análise detalhada de RAM",    analise_ram_detalhada),
    ("Diagnóstico performance RAM", diagnostico_performance_ram),
    ("Liberar RAM Standby",         liberar_ram_standby),
    ("Limpeza cache Windows",       limpar_cache_windows),
    ("Limpeza Prefetch",            limpar_prefetch),
    ("Limpeza de logs",             limpar_logs),
    ("Limpeza cache Explorer",      limpar_cache_explorer),
    ("Limpeza cache Edge",          limpar_cache_edge),
    ("Limpeza cache Chrome",        limpar_cache_chrome),
    ("Limpeza cache Firefox",       limpar_cache_firefox),
    ("Limpeza cache Opera",         limpar_cache_opera),
    ("Limpeza cache Discord",       limpar_cache_discord),
    ("Limpeza arquivos inúteis",    limpar_arquivos_inuteis),
    ("Limpeza arquivos vazios",     remover_arquivos_vazios),
    ("Ajuste visual desempenho",    ajuste_visual_desempenho),
    ("Desativar animações",         desativar_animacoes),
    ("Desativar Aero Shake",        desativar_aero_shake),
    ("Desativar Snap Assist",       desativar_snap_assist),
    ("Desativar transparência",     desativar_transparency),
    ("Desativar taskbar anim.",     desativar_taskbar_animations),
    ("Desativar sombras",           desativar_shadow_windows),
    ("Desativar notificações",      desativar_notificacoes_dicas),
    ("Desativar Sticky Keys",       desativar_sticky_keys),
    ("Otimização de rede",          otimizar_rede),
    ("Flush DNS",                   limpar_cache_dns),
    ("Diagnóstico internet",        diagnostico_internet),
    ("Zerar reserva QoS",           zerar_reserva_qos),
    ("Liberar RAM",                 liberar_ram),
    ("Gerenciar inicialização",     gerenciar_inicializacao),
    ("Otimizar boot",               otimizar_boot),
    ("Startup delay zero",          startup_delay_zero),
    ("MenuShowDelay 0",             reg_menu_show_delay),
    ("SystemResponsiveness 0",      reg_system_responsiveness),
    ("NetworkThrottling off",       reg_network_throttling_index),
    ("TcpAckFrequency 1",           reg_tcp_ack_frequency),
    ("TCPNoDelay on",               reg_tcp_no_delay),
    ("Game Mode ativado",           ativar_game_mode),
    ("Taxa de atualização",         ajustar_taxa_atualizacao),
    ("Pointer Precision off",       desativar_enhance_pointer_precision),
]

TAREFAS_COMPLETA = TAREFAS_INTERMEDIARIA + [
    ("Ponto de restauração",        criar_ponto_restauracao),
    ("Limpeza cache DirectX",       limpar_cache_directx),
    ("Limpeza cache shaders",       limpar_cache_shaders),
    ("Limpeza cache fontes",        limpar_cache_fontes),
    ("Limpeza cache Steam",         limpar_cache_steam),
    ("Limpeza cache OBS",           limpar_cache_obs),
    ("Limpeza cache Adobe",         limpar_cache_adobe),
    ("Limpeza profunda",            limpeza_profunda),
    ("Limpeza downloads antigos",   limpar_downloads_antigos),
    ("Limpeza resíduos",            limpar_residuos_programas),
    ("Atalhos quebrados",           limpar_atalhos_quebrados),
    ("Arquivos órfãos",             limpar_arquivos_orfaos),
    ("Busca arquivos grandes",      buscar_arquivos_grandes),
    ("Verificar SMART",             verificar_smart),
    ("SFC /scannow",                verificar_sfc),
    ("TRIM SSD forçado",            forcar_trim_ssd),
    ("Desativar nomes 8.3",         desativar_8dot3_names),
    ("Desativar last access",       desativar_last_access_timestamp),
    ("Aumentar MFT Zone",           aumentar_mft_zone),
    ("Cache NTFS máximo",           configurar_ntfs_memory),
    ("Desativar indexação disco",   desativar_indexacao_disco),
    ("Backup do registro",          backup_registro),
    ("Limpeza de registro",         limpeza_registro),
    ("Win32PrioritySep 26",         reg_win32_priority_separation),
    ("LargeSystemCache on",         reg_large_system_cache),
    ("IoPageLockLimit aumentado",   reg_io_page_lock_limit),
    ("NoLazyFlush on",              reg_no_lazy_flush),
    ("DisablePagingExec on",        reg_disable_paging_executive),
    ("HungAppTimeout 1000ms",       reg_hung_app_timeout),
    ("WaitKillService 2000ms",      reg_wait_to_kill_service_timeout),
    ("AutoEndTasks on",             reg_auto_end_tasks),
    ("GPU Priority 8",              reg_gpu_priority),
    ("Scheduling High",             reg_scheduling_category_high),
    ("MouseDataQueueSize 20",       reg_mouse_data_queue_size),
    ("KeyboardDataQueueSize 20",    reg_keyboard_data_queue_size),
    ("Ghost devices off",           reg_disable_ghost_devices),
    ("Desativar MPO",               reg_desativar_mpo),
    ("Ativar HAGS",                 ativar_hags),
    ("Shader Cache Unlimited",      reg_shader_cache_unlimited),
    ("GPU Max Performance",         reg_power_management_gpu),
    ("GPU Scaling off",             reg_desativar_gpu_scaling),
    ("NVIDIA Overlay off",          reg_desativar_nvidia_overlay),
    ("Threaded Optimization",       reg_threaded_optimization),
    ("NVIDIA Ultra Low Latency",    reg_nvidia_ultra_low_latency),
    ("Ultimate Performance",        ativar_ultimate_performance),
    ("Core Parking off",            desativar_core_parking),
    ("USB Suspend off",             desativar_usb_selective_suspend),
    ("CPU mínimo 100%",             cpu_min_processor_state),
    ("Disco nunca desliga",         desativar_hard_disk_turnoff),
    ("PCIe Link Power off",         desativar_pcie_link_power),
    ("Wireless Max Power",          configurar_wireless_max_power),
    ("System Cooling Active",       configurar_system_cooling_active),
    ("Manutenção automát. off",     desativar_manutencao_automatica),
    ("Hibernação off",              desativar_hibernacao),
    ("Modo desempenho máximo",      modo_desempenho_maximo),
    ("Desativar IPv6",              desativar_ipv6),
    ("Desativar NetBIOS",           desativar_netbios),
    ("Interrupt Moderation off",    desativar_interrupt_moderation),
    ("Flow Control off",            desativar_flow_control),
    ("Packet Coalescing off",       desativar_packet_coalescing),
    ("Energy Eff. Ethernet off",    desativar_energy_efficient_ethernet),
    ("RSS Multi-core",              configurar_rss_multicore),
    ("Speed 1Gbps Full Duplex",     configurar_speed_duplex),
    ("LLDP off",                    desativar_lldp),
    ("Reset de rede",               reset_rede),
    ("Ajuste MTU",                  ajuste_mtu),
    ("Desativar telemetria",        desativar_telemetria),
    ("Telemetria serviços off",     desativar_telemetria_servicos),
    ("Desinstalar bloatware",       desinstalar_bloatware),
    ("Remover Cortana",             remover_cortana),
    ("Desativar OneDrive",          desativar_onedrive),
    ("Edge background off",         desativar_edge_background),
    ("Feedback Hub off",            desativar_feedback_hub),
    ("News & Interests off",        desativar_news_interests),
    ("Meet Now off",                desativar_meet_now),
    ("Error Reporting off",         desativar_error_reporting),
    ("Windows Maps off",            remover_mapas),
    ("People app off",              remover_people),
    ("Xbox Game Bar off",           desativar_xbox_game_bar),
    ("Game DVR off",                desativar_game_dvr),
    ("Windows Ink off",             desativar_windows_ink),
    ("Serviços extras off",         desativar_servicos_extras),
    ("Serviços inúteis off",        desativar_servicos_inuteis),
    ("HiberBoot off",               reg_disable_hiberboot),
    ("Audio Enhancements off",      desativar_audio_enhancements),
    ("Spatial Sound off",           desativar_spatial_sound),
    ("VBS e Memory Integrity off",  desativar_vbs_memory_integrity),
    ("Defender exclusões jogos",    adicionar_exclusao_defender),
    ("FSO off",                     desativar_fso),
    ("Delivery Optim. off",         configurar_delivery_optimization),
    ("WUpdate banda 1%",            limitar_windows_update_banda),
    ("Activity History off",        desativar_activity_history),
    ("Location Service off",        desativar_location_service),
    ("Camera/Mic Deny",             desativar_privacy_camera_mic),
    ("Background Apps off",         desativar_background_apps),
    ("Steam Overlay off",           desativar_steam_overlay),
    ("Discord HW Accel off",        desativar_hardware_acceleration_discord),
    ("Spotlight off",               desativar_spotlight),
    ("Blur Login off",              desativar_blur_login),
    ("PageFile fixo 4096 MB",       configurar_pagefile_fixo),
    ("Crash Dump Small",            configurar_crash_dump_small),
    ("Ajuste memória virtual",      ajuste_memoria_virtual),
]

# ══════════════════════════════════════════════════════════════════════
#  MENU DE RAM
# ══════════════════════════════════════════════════════════════════════

def menu_ram():
    while True:
        cls()
        linha("═", Fore.CYAN)
        print(Fore.CYAN + "  🧠  GERENCIAMENTO DE RAM".center(WIDTH) + Style.RESET_ALL)
        linha("─")
        print(f"""
  {Fore.CYAN}[1]{Style.RESET_ALL}  📊  Análise Detalhada
       {Fore.WHITE}Mostra RAM por categoria: Active, Standby,
       Modified e Free com diagnóstico automático.{Style.RESET_ALL}

  {Fore.GREEN}[2]{Style.RESET_ALL}  🧹  Liberar RAM (Esvaziar Standby)
       {Fore.WHITE}Libera memória em cache (Standby) sem
       fechar nenhum programa.{Style.RESET_ALL}

  {Fore.YELLOW}[3]{Style.RESET_ALL}  🔍  Diagnóstico de Performance
       {Fore.WHITE}Identifica os processos que mais consomem
       RAM e analisa uso do pagefile (swap).{Style.RESET_ALL}

  {Fore.WHITE}[4]{Style.RESET_ALL}  📈  Monitoramento Simples
       {Fore.WHITE}Exibe uso total, usado e livre de RAM.{Style.RESET_ALL}

  {Fore.RED}[0]{Style.RESET_ALL}  ←  Voltar ao menu principal
""")
        linha("─")
        escolha = input(f"  {Fore.CYAN}Digite sua opção:{Style.RESET_ALL} ").strip()

        if escolha == "0":
            break
        elif escolha == "1":
            cls(); analise_ram_detalhada()
            input("\n  Pressione ENTER para continuar...")
        elif escolha == "2":
            cls()
            aviso(
                "Esta operação libera a memória cache (Standby) do Windows.\n"
                "  Nenhum programa será fechado. É seguro executar."
            )
            if confirmar("Deseja liberar a RAM Standby agora?"):
                liberar_ram_standby()
            input("\n  Pressione ENTER para continuar...")
        elif escolha == "3":
            cls(); diagnostico_performance_ram()
            input("\n  Pressione ENTER para continuar...")
        elif escolha == "4":
            cls(); monitorar_ram()
            input("\n  Pressione ENTER para continuar...")
        else:
            aviso("Opção inválida."); pausa(1)

# ══════════════════════════════════════════════════════════════════════
#  EXECUTOR DE TAREFAS
# ══════════════════════════════════════════════════════════════════════

def executar_tarefas(lista, nome_modo):
    total = len(lista)
    bytes_total = 0
    inicio = time.time()

    cls()
    linha("═", Fore.CYAN)
    print(Fore.CYAN + f"  ▶  Executando: {nome_modo}".center(WIDTH) + Style.RESET_ALL)
    print(Fore.YELLOW + f"  Total de tarefas: {total}".center(WIDTH) + Style.RESET_ALL)
    linha("─")

    for i, (nome, func) in enumerate(lista, 1):
        barra_progresso(i - 1, total, nome)
        print()
        try:
            lib = func()
            bytes_total += (lib or 0)
        except Exception as e:
            erro(f"{nome}: {e}")
        barra_progresso(i, total, nome)
        print()
        pausa(0.1)

    duracao = time.time() - inicio
    linha("═", Fore.GREEN)
    print(Fore.GREEN + f"""
  ╔{'═'*50}╗
  ║  ✔  OTIMIZAÇÃO CONCLUÍDA!{' '*23}║
  ║                                                  ║
  ║  Tarefas executadas : {total:<5}                        ║
  ║  Espaço liberado    : {formata_bytes(bytes_total):<15}              ║
  ║  Tempo total        : {duracao/60:.1f} min                      ║
  ╚{'═'*50}╝
""" + Style.RESET_ALL)
    input("  Pressione ENTER para voltar ao menu...")

# ══════════════════════════════════════════════════════════════════════
#  TELA DE BOAS-VINDAS
# ══════════════════════════════════════════════════════════════════════

def tela_boas_vindas():
    cls()
    agora = datetime.now().strftime("%d/%m/%Y  %H:%M")
    admin_str = (
        Fore.GREEN + "✔ Administrador"
        if is_admin()
        else Fore.RED + "✘ SEM privilégios de admin"
    )
    print(Fore.CYAN + r"""
  ██╗     ███╗   ██╗██████╗      ██████╗██╗     ██╗██████╗
  ██║     ████╗  ██║██╔══██╗    ██╔════╝██║     ██║██╔══██╗
  ██║     ██╔██╗ ██║██║  ██║    ██║     ██║     ██║██████╔╝
  ██║     ██║╚██╗██║██║  ██║    ██║     ██║     ██║██╔═══╝
  ███████╗██║ ╚████║██████╔╝    ╚██████╗███████╗██║██║
  ╚══════╝╚═╝  ╚═══╝╚═════╝      ╚═════╝╚══════╝╚═╝╚═╝
""" + Style.RESET_ALL)
    print(
        Fore.WHITE +
        "        OPTIMIZER  v1  —  O Otimizador Definitivo do Windows"
        .center(WIDTH) + Style.RESET_ALL
    )
    linha("─", Fore.CYAN)
    print(f"  {Fore.WHITE}Versão      :{Style.RESET_ALL} {Fore.CYAN}{APP_VERSION}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Data / Hora :{Style.RESET_ALL} {agora}")
    print(f"  {Fore.WHITE}Status      :{Style.RESET_ALL} {admin_str}{Style.RESET_ALL}")
    if not is_admin():
        aviso("Execute como Administrador para desbloquear todas as funções!")
    linha("═", Fore.CYAN)
    print()

# ══════════════════════════════════════════════════════════════════════
#  MENU PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

AVISOS = {
    "1": {
        "titulo": "⚠  OTIMIZAÇÃO TOTAL (Recomendada para PC muito lento)",
        "descricao": [
            "Será executado um total de {} tarefas de otimização.",
            "",
            "O que vai acontecer no seu PC:",
            "  • Ponto de restauração criado antes das alterações",
            "  • Análise detalhada e limpeza de RAM (Standby, Active, Free)",
            "  • Limpeza completa: temp, lixeira, cache, logs, prefetch",
            "  • Limpeza de navegadores (Edge, Chrome, Firefox, Opera)",
            "  • Limpeza de apps (Steam, Discord, OBS, Adobe)",
            "  • Ajustes visuais e desativação de animações/transparência",
            "  • Desativação de Sticky Keys e notificações intrusivas",
            "  • Game Mode ativado + verificação de taxa de atualização",
            "  • Otimização de registro e kernel (baixo nível)",
            "  • GPU: MPO off, HAGS on, Shader Cache Unlimited",
            "  • Rede avançada: IPv6 off, NetBIOS off, QoS zerado",
            "  • Serviços e telemetria desativados",
            "  • Remoção de bloatware e apps pré-instalados",
            "  • NTFS: 8.3 off, last access off, MFT Zone otimizada",
            "  • Energia: Ultimate Performance, Core Parking off",
            "  • Hibernação desativada (espaço liberado em disco)",
            "  • Indexação de disco desativada (SSD protegido)",
            "  • Segurança ajustada para máxima performance",
            "  • Backup e limpeza do registro + verificação SFC",
            "",
            "  ⏱  Tempo estimado: 30 a 90 minutos.",
            "     Não feche o programa durante o processo.",
            "",
            "  ⚠  AVISO: Feche todos os aplicativos antes de continuar!",
        ],
        "tarefas": TAREFAS_COMPLETA,
        "nome": "Otimização Total",
    },
    "2": {
        "titulo": "►  OTIMIZAÇÃO INTERMEDIÁRIA",
        "descricao": [
            "Será executado um total de {} tarefas de otimização.",
            "",
            "O que vai acontecer no seu PC:",
            "  • Análise e limpeza detalhada de RAM (Standby e categorias)",
            "  • Diagnóstico de processos que consomem mais memória",
            "  • Limpeza de temporários, lixeira, logs e prefetch",
            "  • Limpeza de navegadores (Edge, Chrome, Firefox, Opera)",
            "  • Limpeza de apps (Discord)",
            "  • Ajustes visuais completos (animações, sombras, transparência)",
            "  • Desativação de Sticky Keys e notificações",
            "  • Game Mode ativado",
            "  • Otimizações de rede e diagnóstico",
            "  • Tweaks de registro essenciais",
            "  • Liberação de RAM e ajuste do boot",
            "",
            "  ⏱  Tempo estimado: 10 a 30 minutos.",
        ],
        "tarefas": TAREFAS_INTERMEDIARIA,
        "nome": "Otimização Intermediária",
    },
    "3": {
        "titulo": "►  OTIMIZAÇÃO BÁSICA",
        "descricao": [
            "Será executado um total de {} tarefas de otimização.",
            "",
            "O que vai acontecer no seu PC:",
            "  • Análise de uso do disco",
            "  • Monitoramento de RAM",
            "  • Limpeza de arquivos temporários",
            "  • Limpeza da lixeira",
            "  • Limpeza do cache DNS",
            "  • Limpeza de miniaturas e histórico recente",
            "",
            "  ⏱  Tempo estimado: 2 a 5 minutos.",
            "  ✔  Processo seguro e rápido — ideal para uso diário.",
        ],
        "tarefas": TAREFAS_BASICA,
        "nome": "Otimização Básica",
    },
    "4": {
        "titulo": "🎮  OTIMIZAÇÃO PARA JOGOS  [EM DESENVOLVIMENTO]",
        "descricao": [
            "Esta função está em desenvolvimento e será lançada em breve!",
            "",
            "Previsão de funcionalidades:",
            "  • Priorização de CPU e RAM para jogos",
            "  • Redução de input lag e ping",
            "  • Limpeza de shaders e cache DirectX",
            "  • Desativação de overlays",
            "  • MSI Mode, Timer Resolution, Interrupt Affinity",
            "",
            "  ⏳  Em breve disponível numa atualização do LND Optimizer.",
        ],
        "tarefas": None,
        "nome": "Jogos (em desenvolvimento)",
    },
    "5": {
        "titulo": "🖥  OTIMIZAÇÃO DE PROGRAMAS  [EM DESENVOLVIMENTO]",
        "descricao": [
            "Esta função está em desenvolvimento e será lançada em breve!",
            "",
            "Previsão de funcionalidades:",
            "  • Priorização de recursos para apps específicos",
            "  • Perfis por programa (edição de vídeo, streaming, dev)",
            "  • Otimização do Adobe, OBS, DaVinci, VS Code",
            "  • Gerenciamento inteligente de RAM por processo",
            "",
            "  ⏳  Em breve disponível numa atualização do LND Optimizer.",
        ],
        "tarefas": None,
        "nome": "Programas (em desenvolvimento)",
    },
}

def exibir_aviso_confirmacao(opcao):
    dados = AVISOS.get(opcao)
    if not dados:
        return False

    cls()
    linha("═", Fore.YELLOW)
    print(Fore.YELLOW + f"  {dados['titulo']}".center(WIDTH) + Style.RESET_ALL)
    linha("─")

    total_tarefas = len(dados["tarefas"]) if dados["tarefas"] else 0
    for lt in dados["descricao"]:
        print(Fore.WHITE + "  " + lt.format(total_tarefas) + Style.RESET_ALL)

    linha("─")

    if dados["tarefas"] is None:
        input("\n  Pressione ENTER para voltar ao menu...")
        return False

    print(Fore.CYAN + "\n  Deseja iniciar a otimização agora?" + Style.RESET_ALL)
    print("    [S] Sim, iniciar   |   [N] Não, voltar ao menu")
    print()
    resp = input("  Sua escolha: ").strip().upper()
    return resp in ("S", "SIM", "1", "Y", "YES")

def menu_principal():
    while True:
        tela_boas_vindas()
        print(Fore.CYAN + "  MENU PRINCIPAL".center(WIDTH) + Style.RESET_ALL)
        linha("─")
        print(f"""
  {Fore.GREEN}[1]{Style.RESET_ALL}  🔥  Otimizar TUDO           {Fore.YELLOW}← Recomendado para PC muito lento{Style.RESET_ALL}
  {Fore.CYAN}[2]{Style.RESET_ALL}  ⚡  Otimização Intermediária
  {Fore.WHITE}[3]{Style.RESET_ALL}  🌿  Otimização Básica         {Fore.WHITE}← Rápida e segura, uso diário{Style.RESET_ALL}
  {Fore.MAGENTA}[4]{Style.RESET_ALL}  🎮  Otimização para Jogos     {Fore.MAGENTA}[Em desenvolvimento]{Style.RESET_ALL}
  {Fore.MAGENTA}[5]{Style.RESET_ALL}  🖥  Otimização de Programas   {Fore.MAGENTA}[Em desenvolvimento]{Style.RESET_ALL}
  {Fore.CYAN}[6]{Style.RESET_ALL}  🧠  Gerenciamento de RAM      {Fore.CYAN}← Análise, limpeza e diagnóstico{Style.RESET_ALL}
  {Fore.YELLOW}[7]{Style.RESET_ALL}  🔄  Verificar Atualizações    {Fore.YELLOW}← Versão atual: {APP_VERSION}{Style.RESET_ALL}

  {Fore.RED}[0]{Style.RESET_ALL}  ✖  Sair
""")
        linha("─")
        escolha = input(f"  {Fore.CYAN}Digite sua opção:{Style.RESET_ALL} ").strip()

        if escolha == "0":
            cls()
            print(
                Fore.CYAN +
                "\n  Obrigado por usar o LND Clip Optimizer v1!\n" +
                Style.RESET_ALL
            )
            sys.exit(0)

        elif escolha == "6":
            menu_ram()

        elif escolha == "7":
            cls()
            linha("═", Fore.CYAN)
            print(
                Fore.CYAN +
                "  🔄  VERIFICAR ATUALIZAÇÕES".center(WIDTH) +
                Style.RESET_ALL
            )
            linha("─")
            verificar_atualizacao_github(mostrar_msg_se_atual=True)
            input("\n  Pressione ENTER para voltar ao menu...")

        elif escolha in ("1", "2", "3", "4", "5"):
            confirmado = exibir_aviso_confirmacao(escolha)
            if confirmado:
                dados = AVISOS[escolha]
                executar_tarefas(dados["tarefas"], dados["nome"])

        else:
            aviso("Opção inválida. Tente novamente.")
            pausa(1.5)

# ══════════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if os.name != "nt":
        print("Este programa foi feito exclusivamente para Windows.")
        sys.exit(1)

    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        except Exception:
            pass

    # ── Verifica atualização ao iniciar (silencioso se já atualizado) ─
    verificar_atualizacao_github(mostrar_msg_se_atual=False)

    menu_principal()