"""Moteur : synchronisation Google Drive, construction du portail web et sauvegarde."""
import json
import re
import shutil
import socket
import zipfile
import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

# Prioriser IPv4 pour éviter les blocages WinError 10060 (fréquents sur VPN ou réseaux sans routage IPv6)
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_first_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in res if r[0] == socket.AF_INET]
    ipv6 = [r for r in res if r[0] == socket.AF_INET6]
    return (ipv4 + ipv6) if ipv4 else res
socket.getaddrinfo = _ipv4_first_getaddrinfo

BASE = Path(__file__).parent
RENDUS = BASE / "rendus"
SITE = BASE / "site"
CONFIG = BASE / "config.json"
CREDS = BASE / "credentials.json"
TOKEN = BASE / "token.json"

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Extensions web, médias, polices et données autorisées
ALLOWED = {
    # Web standard
    ".html", ".htm", ".css", ".js", ".mjs", ".json",
    # Images & icônes
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif",
    # Polices typographiques
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # Audio / Vidéo légitimes pour projets étudiants
    ".mp3", ".wav", ".ogg", ".mp4", ".webm",
    # Données et documentation
    ".txt", ".md", ".pdf", ".csv", ".xml"
}

# Limites de sécurité contre les Zip-bombs et abus
MAX_FILE_SIZE = 25 * 1024 * 1024          # 25 Mo max par fichier
MAX_ARCHIVE_SIZE = 150 * 1024 * 1024       # 150 Mo max décompressé au total par projet
MAX_FILES_PER_ZIP = 1500                   # 1500 fichiers max par zip

DEFAULT_CONFIG = {
    "titre": "Travaux des étudiants",
    "sous_titre": "Portail des projets et réalisations web",
    "anonymiser": False,
    "rendus_folder_id": "",
    "sauvegarde_folder_id": ""
}


def clean_folder_id(val: str) -> str:
    """Extrait l'identifiant brut d'un dossier Google Drive, même si l'utilisateur colle l'URL complète."""
    if not val:
        return ""
    val = val.strip()
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", val)
    if match:
        return match.group(1)
    match_d = re.search(r"/d/([a-zA-Z0-9_-]+)", val)
    if match_d:
        return match_d.group(1)
    return val.split("?")[0].split("&")[0].strip("/")


def load_config():
    """Charge la configuration ou génère le fichier par défaut s'il n'existe pas."""
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        cfg = {**DEFAULT_CONFIG, **data}
        cfg["rendus_folder_id"] = clean_folder_id(cfg.get("rendus_folder_id", ""))
        cfg["sauvegarde_folder_id"] = clean_folder_id(cfg.get("sauvegarde_folder_id", ""))
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    """Enregistre la configuration dans config.json en nettoyant les IDs Drive."""
    cfg = dict(cfg)
    cfg["rendus_folder_id"] = clean_folder_id(cfg.get("rendus_folder_id", ""))
    cfg["sauvegarde_folder_id"] = clean_folder_id(cfg.get("sauvegarde_folder_id", ""))
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- Google Drive ----------
def drive():
    """Initialise et retourne le client API Google Drive."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CREDS.exists():
        raise RuntimeError(
            "Fichier credentials.json introuvable.\n"
            "Téléchargez vos identifiants OAuth Google Cloud et placez-les sous le nom 'credentials.json' "
            "dans le dossier de l'application."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


def sync(cfg, log):
    """Télécharge les nouveaux zip (ou zip modifiés) du dossier Drive « rendus »."""
    from googleapiclient.http import MediaIoBaseDownload

    folder_id = (cfg.get("rendus_folder_id") or "").strip()
    if not folder_id or "COLLEZ_ICI" in folder_id:
        raise RuntimeError("Veuillez renseigner un 'rendus_folder_id' valide dans la configuration.")

    RENDUS.mkdir(exist_ok=True)
    log("[INFO] Connexion au Google Drive du club...")
    svc = drive()

    state_file = RENDUS / ".sync.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

    q = f"'{folder_id}' in parents and trashed=false and name contains '.zip'"
    files, page_token = [], None

    log("[INFO] Recherche des archives .zip dans le dossier distant...")
    while True:
        r = svc.files().list(
            q=q,
            fields="nextPageToken, files(id, name, modifiedTime, size)",
            pageSize=200,
            pageToken=page_token
        ).execute()
        files.extend(r.get("files", []))
        page_token = r.get("nextPageToken")
        if not page_token:
            break

    new_count = 0
    for f in files:
        name = Path(f["name"]).name
        dest_file = RENDUS / name
        
        # Vérification si le fichier a déjà été téléchargé avec la même date de modification
        if state.get(f["id"]) == f.get("modifiedTime") and dest_file.exists():
            continue

        log(f"[INFO] Téléchargement de {name}...")
        with open(dest_file, "wb") as out:
            dl = MediaIoBaseDownload(out, svc.files().get_media(fileId=f["id"]))
            done = False
            while not done:
                _, done = dl.next_chunk()

        state[f["id"]] = f.get("modifiedTime")
        new_count += 1
        log(f"[SUCCES] Téléchargé avec succès : {name}")

    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    log(f"[SUCCES] Synchronisation terminée : {new_count} archive(s) récupérée(s), {len(files)} au total sur le Drive.")


def backup(cfg, log):
    """Crée une archive locale datée des rendus et du site, puis la téléverse sur Drive."""
    from googleapiclient.http import MediaFileUpload

    folder_id = (cfg.get("sauvegarde_folder_id") or "").strip()
    if not folder_id or "COLLEZ_ICI" in folder_id:
        raise RuntimeError("Veuillez renseigner un 'sauvegarde_folder_id' valide dans la configuration.")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
    archive_base = BASE / f"sauvegarde-{stamp}"
    log(f"[INFO] Création de l'archive de sauvegarde : {archive_base.name}.zip...")

    RENDUS.mkdir(exist_ok=True)
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", BASE, "rendus"))

    # Inclure le dossier du site web dans la sauvegarde s'il existe
    if SITE.exists():
        with zipfile.ZipFile(archive_path, "a", zipfile.ZIP_DEFLATED) as z:
            for p in SITE.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(BASE))

    log(f"[INFO] Envoi vers Google Drive (dossier {folder_id})...")
    meta = {"name": archive_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(archive_path), mimetype="application/zip", resumable=True)
    drive().files().create(body=meta, media_body=media, fields="id").execute()

    # Nettoyage de l'archive locale temporaire
    try:
        archive_path.unlink()
    except Exception:
        pass

    log(f"[SUCCES] Sauvegarde transmise avec succès sur Google Drive : {meta['name']}")


# ---------- Construction du site et sécurité ----------
def extract(zpath, dest):
    """
    Extrait une archive de manière sécurisée (protection Zip-Slip, types de fichiers,
    limites de taille unitaire et globale).
    Retourne (skipped_files, total_size, file_count).
    """
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    skipped = []
    total_uncompressed = 0
    extracted_count = 0

    with zipfile.ZipFile(zpath) as zf:
        members = zf.infolist()
        if len(members) > MAX_FILES_PER_ZIP:
            raise ValueError(f"Archive trop volumineuse ({len(members)} fichiers, max {MAX_FILES_PER_ZIP}).")

        for m in members:
            # Ignorer les répertoires et métadonnées macOS
            if m.is_dir() or m.filename.startswith("__MACOSX") or "/.DS_Store" in m.filename:
                continue

            target = (dest / m.filename).resolve()

            # Sécurité 1 : Protection stricte contre le Zip-Slip
            try:
                target.relative_to(root)
            except ValueError:
                skipped.append((m.filename, "Chemin hors dossier racine (Zip-Slip bloqué)"))
                continue

            # Sécurité 2 : Filtrage strict par liste d'extensions autorisées
            if target.suffix.lower() not in ALLOWED:
                skipped.append((m.filename, f"Type de fichier non autorisé ({target.suffix})"))
                continue

            # Sécurité 3 : Limite par taille de fichier
            if m.file_size > MAX_FILE_SIZE:
                skipped.append((m.filename, f"Fichier trop gros ({m.file_size // (1024*1024)} Mo)"))
                continue

            # Sécurité 4 : Limite globale décompressée
            total_uncompressed += m.file_size
            if total_uncompressed > MAX_ARCHIVE_SIZE:
                raise ValueError(f"Dépassement du quota total extrait ({total_uncompressed // (1024*1024)} Mo).")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(m))
            extracted_count += 1

    return skipped, total_uncompressed, extracted_count


def scan_external_calls(project_dir):
    """
    Analyse statique des fichiers du projet pour détecter les dépendances externes
    (scripts CDN, styles distants, polices Google Fonts, appels fetch/axios).
    """
    findings = []
    pattern = re.compile(
        r"""(?:(?:src|href)\s*=\s*["']https?://|"""
        r"""@import\s+(?:url\()?["']https?://|"""
        r"""url\(\s*["']?https?://|"""
        r"""(?:fetch|axios|open)\s*\(\s*["']https?://|"""
        r"""new\s+WebSocket\s*\(\s*["']wss?://)""",
        re.IGNORECASE
    )

    for f in project_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".html", ".htm", ".js", ".css"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                matches = pattern.findall(content)
                if matches:
                    findings.append(f"{f.name} ({len(matches)} appel(s) externe(s))")
            except Exception:
                pass
    return findings


def build(cfg, log):
    """Génère le site statique complet dans le dossier site/."""
    RENDUS.mkdir(exist_ok=True)
    SITE.mkdir(exist_ok=True)

    travaux_dir = SITE / "travaux"
    shutil.rmtree(travaux_dir, ignore_errors=True)
    travaux_dir.mkdir(parents=True, exist_ok=True)

    zip_files = sorted(RENDUS.glob("*.zip"))
    if not zip_files:
        log("[INFO] Aucun fichier zip trouvé dans le dossier 'rendus/'.")

    entries = []
    problems = 0

    for i, z in enumerate(zip_files, 1):
        # Slug propre pour le dossier web
        raw_slug = re.sub(r"[^a-zA-Z0-9]+", "-", z.stem).strip("-").lower()
        slug = raw_slug if raw_slug else f"projet-{i}"
        dest = travaux_dir / slug

        try:
            skipped, total_size, file_count = extract(z, dest)
        except (zipfile.BadZipFile, ValueError) as err:
            log(f"[ERREUR] Archive illisible ou non conforme {z.name} : {err}")
            problems += 1
            continue

        # Recherche de la page d'entrée (insensible à la casse)
        html_files = [p for p in dest.rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm")]
        index_candidates = [p for p in html_files if p.name.lower() in ("index.html", "index.htm")]

        # Préférer le index.html le plus proche de la racine du projet
        if index_candidates:
            index_candidates.sort(key=lambda p: len(p.parts))
            entry_page = index_candidates[0]
        elif html_files:
            # Fallback : premier fichier HTML trouvé
            html_files.sort(key=lambda p: len(p.parts))
            entry_page = html_files[0]
            log(f"[ATTENTION] Pas de 'index.html' exact dans {z.name}. Utilisation de '{entry_page.name}'.")
        else:
            log(f"[ERREUR] Aucun fichier HTML trouvé dans {z.name}. Projet ignoré.")
            problems += 1
            shutil.rmtree(dest, ignore_errors=True)
            continue

        # Signalement des fichiers ignorés
        if skipped:
            skip_summary = ", ".join(f"{name} ({reason})" for name, reason in skipped[:3])
            if len(skipped) > 3:
                skip_summary += f" et {len(skipped)-3} autre(s)..."
            log(f"[ATTENTION] Éléments filtrés dans {z.name} : {skip_summary}")

        # Signalement des appels distants (CDNs, polices, requêtes réseau)
        external_calls = scan_external_calls(dest)
        if external_calls:
            log(f"[A VERIFIER] {z.name} : ressources externes dans {', '.join(external_calls[:3])}")

        # Détermination du libellé selon l'option d'anonymisation
        if cfg.get("anonymiser", False):
            label = f"Projet {i:02d}"
            author_desc = "Étudiant anonyme"
        else:
            clean_name = z.stem.replace("-", " ").replace("_", " ").strip()
            label = clean_name.title() if clean_name else f"Projet {i:02d}"
            author_desc = label

        entry_rel = entry_page.relative_to(SITE).as_posix()
        size_kb = round(total_size / 1024, 1)

        entries.append({
            "id": f"p{i}",
            "label": label,
            "author": author_desc,
            "url": entry_rel,
            "slug": slug,
            "file_count": file_count,
            "size_kb": size_kb,
            "has_warnings": bool(external_calls or skipped),
            "warnings_text": ", ".join(external_calls) if external_calls else ""
        })

    # Génération du HTML ultra-moderne et responsive
    render_portal(cfg, entries)
    log(f"[SUCCES] Portail web compilé : {len(entries)} projet(s) publié(s), {problems} problème(s).")
    log(f"[INFO] Répertoire du site : {SITE.resolve()}")


def render_portal(cfg, projects):
    """Produit un portail web moderne avec thème clair/sombre, recherche en direct et prévisualisation."""
    titre = cfg.get("titre", "Travaux des étudiants")
    sous_titre = cfg.get("sous_titre", "Portail des projets et réalisations web")
    generated_at = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")

    projects_json = json.dumps(projects, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(titre)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --surface: rgba(23, 32, 54, 0.75);
      --surface-border: rgba(255, 255, 255, 0.1);
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --accent: #6366f1;
      --badge-warn-bg: rgba(245, 158, 11, 0.15);
      --badge-warn-text: #fbbf24;
      --badge-ok-bg: rgba(16, 185, 129, 0.15);
      --badge-ok-text: #34d399;
      --card-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
      --radius: 14px;
      --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }}

    [data-theme="light"] {{
      --bg: #f8fafc;
      --surface: rgba(255, 255, 255, 0.85);
      --surface-border: rgba(0, 0, 0, 0.08);
      --text: #0f172a;
      --text-muted: #64748b;
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --accent: #4f46e5;
      --badge-warn-bg: #fef3c7;
      --badge-warn-text: #b45309;
      --badge-ok-bg: #d1fae5;
      --badge-ok-text: #047857;
      --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.07);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      line-height: 1.5;
      transition: background-color 0.3s ease, color 0.3s ease;
    }}

    header {{
      background: var(--surface);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--surface-border);
      position: sticky;
      top: 0;
      z-index: 40;
    }}

    .header-container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 1.25rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }}

    .brand-icon {{
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      font-size: 1.2rem;
      box-shadow: 0 4px 15px rgba(56, 189, 248, 0.3);
    }}

    .brand-text h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}

    .brand-text p {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    .actions {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .theme-toggle {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      color: var(--text);
      cursor: pointer;
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: var(--transition);
    }}

    .theme-toggle:hover {{
      border-color: var(--primary);
      transform: scale(1.05);
    }}

    main {{
      max-width: 1200px;
      width: 100%;
      margin: 0 auto;
      padding: 2.5rem 1.5rem;
      flex: 1;
    }}

    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 2rem;
      flex-wrap: wrap;
    }}

    .search-box {{
      position: relative;
      flex: 1;
      min-width: 260px;
      max-width: 480px;
    }}

    .search-box input {{
      width: 100%;
      padding: 0.75rem 1rem 0.75rem 2.6rem;
      border-radius: 12px;
      border: 1px solid var(--surface-border);
      background: var(--surface);
      color: var(--text);
      font-size: 0.95rem;
      transition: var(--transition);
    }}

    .search-box input:focus {{
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }}

    .search-box svg {{
      position: absolute;
      left: 0.9rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      pointer-events: none;
    }}

    .stats {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.9rem;
      color: var(--text-muted);
    }}

    .count-pill {{
      background: var(--surface);
      padding: 0.35rem 0.85rem;
      border-radius: 20px;
      border: 1px solid var(--surface-border);
      font-weight: 600;
      color: var(--primary);
    }}

    .projects-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem;
    }}

    .project-card {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius);
      padding: 1.4rem;
      box-shadow: var(--card-shadow);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      transition: var(--transition);
      overflow: hidden;
    }}

    .project-card:hover {{
      transform: translateY(-4px);
      border-color: rgba(56, 189, 248, 0.4);
      box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.2);
    }}

    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 0.85rem;
    }}

    .project-title {{
      font-family: 'Outfit', sans-serif;
      font-size: 1.15rem;
      font-weight: 600;
      color: var(--text);
      word-break: break-word;
    }}

    .badge {{
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .badge-ok {{
      background: var(--badge-ok-bg);
      color: var(--badge-ok-text);
    }}

    .badge-warn {{
      background: var(--badge-warn-bg);
      color: var(--badge-warn-text);
    }}

    .card-meta {{
      display: flex;
      gap: 1rem;
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 1.25rem;
    }}

    .card-actions {{
      display: flex;
      gap: 0.75rem;
      margin-top: auto;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      padding: 0.65rem 1rem;
      border-radius: 10px;
      font-size: 0.875rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: var(--transition);
      border: 1px solid transparent;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, var(--primary), var(--accent));
      color: #ffffff;
      flex: 1;
    }}

    .btn-primary:hover {{
      opacity: 0.92;
      box-shadow: 0 4px 15px rgba(56, 189, 248, 0.35);
    }}

    .btn-secondary {{
      background: var(--surface);
      border-color: var(--surface-border);
      color: var(--text);
    }}

    .btn-secondary:hover {{
      border-color: var(--primary);
      background: rgba(56, 189, 248, 0.08);
    }}

    /* Modal de prévisualisation */
    .modal-overlay {{
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(6px);
      z-index: 100;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }}

    .modal-overlay.active {{
      display: flex;
    }}

    .modal-window {{
      background: var(--bg);
      width: 95%;
      max-width: 1280px;
      height: 90vh;
      border-radius: 16px;
      border: 1px solid var(--surface-border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
    }}

    .modal-header {{
      background: var(--surface);
      padding: 0.85rem 1.25rem;
      border-bottom: 1px solid var(--surface-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .modal-header h3 {{
      font-size: 1.05rem;
      font-family: 'Outfit', sans-serif;
    }}

    .modal-tools {{
      display: flex;
      gap: 0.6rem;
    }}

    .modal-body {{
      flex: 1;
      background: #ffffff;
    }}

    .modal-body iframe {{
      width: 100%;
      height: 100%;
      border: none;
    }}

    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 4rem 1rem;
      color: var(--text-muted);
    }}

    footer {{
      border-top: 1px solid var(--surface-border);
      padding: 1.5rem;
      text-align: center;
      font-size: 0.82rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-container">
      <div class="brand">
        <div class="brand-icon">L1</div>
        <div class="brand-text">
          <h1>{escape(titre)}</h1>
          <p>{escape(sous_titre)}</p>
        </div>
      </div>
      <div class="actions">
        <button id="themeToggle" class="theme-toggle" title="Changer de thème" aria-label="Changer de thème">
          <svg id="themeIcon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
          </svg>
        </button>
      </div>
    </div>
  </header>

  <main>
    <div class="toolbar">
      <div class="search-box">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input type="text" id="searchInput" placeholder="Rechercher un projet, étudiant..." autocomplete="off">
      </div>
      <div class="stats">
        <span>Projets publiés :</span>
        <span class="count-pill" id="projectCount">{len(projects)}</span>
      </div>
    </div>

    <div class="projects-grid" id="projectsGrid">
      <!-- Rempli dynamiquement via JS -->
    </div>
  </main>

  <div class="modal-overlay" id="previewModal">
    <div class="modal-window">
      <div class="modal-header">
        <h3 id="modalTitle">Aperçu du projet</h3>
        <div class="modal-tools">
          <a id="modalExternal" href="#" target="_blank" class="btn btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">
            Plein écran ↗
          </a>
          <button id="modalClose" class="btn btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">
            Fermer ✕
          </button>
        </div>
      </div>
      <div class="modal-body">
        <iframe id="previewIframe" src="about:blank" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>
      </div>
    </div>
  </div>

  <footer>
    Généré automatiquement par le gestionnaire de projets • {generated_at}
  </footer>

  <script>
    const projectsData = {projects_json};

    const grid = document.getElementById('projectsGrid');
    const searchInput = document.getElementById('searchInput');
    const projectCount = document.getElementById('projectCount');
    const modal = document.getElementById('previewModal');
    const previewIframe = document.getElementById('previewIframe');
    const modalTitle = document.getElementById('modalTitle');
    const modalExternal = document.getElementById('modalExternal');
    const modalClose = document.getElementById('modalClose');
    const themeToggle = document.getElementById('themeToggle');

    // Gestion du thème sombre / clair
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    themeToggle.addEventListener('click', () => {{
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    }});

    // Affichage des projets
    function renderProjects(items) {{
      grid.innerHTML = '';
      projectCount.textContent = items.length;

      if (items.length === 0) {{
        grid.innerHTML = `
          <div class="empty-state">
            <h3>Aucun projet trouvé</h3>
            <p>Essayez un autre mot-clé de recherche.</p>
          </div>
        `;
        return;
      }}

      items.forEach(p => {{
        const card = document.createElement('div');
        card.className = 'project-card';

        const badgeClass = p.has_warnings ? 'badge-warn' : 'badge-ok';
        const badgeText = p.has_warnings ? 'Vérifié' : 'Conforme';

        card.innerHTML = `
          <div>
            <div class="card-top">
              <h2 class="project-title">${{escapeHtml(p.label)}}</h2>
              <span class="badge ${{badgeClass}}">${{badgeText}}</span>
            </div>
            <div class="card-meta">
              <span>📂 ${{p.file_count}} fichier(s)</span>
              <span>💾 ${{p.size_kb}} Ko</span>
            </div>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary" onclick="openPreview('${{encodeURI(p.url)}}', '${{escapeHtml(p.label)}}')">
              👁️ Aperçu
            </button>
            <a class="btn btn-primary" href="${{encodeURI(p.url)}}" target="_blank">
              Visiter ↗
            </a>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    function escapeHtml(text) {{
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }}

    // Recherche instantanée
    searchInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase().trim();
      const filtered = projectsData.filter(p => 
        p.label.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q)
      );
      renderProjects(filtered);
    }});

    // Modal d'aperçu en direct
    function openPreview(url, title) {{
      modalTitle.textContent = title;
      modalExternal.href = url;
      previewIframe.src = url;
      modal.classList.add('active');
    }}

    function closePreview() {{
      modal.classList.remove('active');
      previewIframe.src = 'about:blank';
    }}

    modalClose.addEventListener('click', closePreview);
    modal.addEventListener('click', (e) => {{
      if (e.target === modal) closePreview();
    }});

    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape' && modal.classList.contains('active')) closePreview();
    }});

    // Rendu initial
    renderProjects(projectsData);
  </script>
</body>
</html>
"""
    (SITE / "index.html").write_text(html_content, encoding="utf-8")
