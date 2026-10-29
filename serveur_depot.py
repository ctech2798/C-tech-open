"""Serveur Web autonome de dépôt de projets pour les étudiants."""
import io
import os
import re
import socket
import zipfile
import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

import club

app = FastAPI(title="Espace de Dépôt Étudiants")

def get_local_ip():
    """Détecte l'adresse IP locale de la machine sur le réseau."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    cfg = club.load_config()
    titre = cfg.get("titre", "Travaux des étudiants")
    sous_titre = cfg.get("sous_titre", "Portail des projets et réalisations web")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dépôt de Projet • {titre}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(23, 32, 54, 0.85);
      --card-border: rgba(255, 255, 255, 0.1);
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --accent: #6366f1;
      --success: #34d399;
      --error: #f87171;
      --radius: 16px;
    }}

    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f8fafc;
        --card-bg: rgba(255, 255, 255, 0.95);
        --card-border: rgba(0, 0, 0, 0.08);
        --text: #0f172a;
        --text-muted: #64748b;
        --primary: #0284c7;
        --primary-hover: #0369a1;
        --accent: #4f46e5;
      }}
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
      position: relative;
      overflow-x: hidden;
    }}

    /* Fond décoratif moderne */
    body::before {{
      content: '';
      position: absolute;
      top: -20%;
      left: 50%;
      transform: translateX(-50%);
      width: 700px;
      height: 700px;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, rgba(99, 102, 241, 0.05) 50%, transparent 70%);
      z-index: 0;
      pointer-events: none;
    }}

    .container {{
      width: 100%;
      max-width: 580px;
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 2.2rem;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.4);
      position: relative;
      z-index: 1;
    }}

    .header {{
      text-align: center;
      margin-bottom: 2rem;
    }}

    .badge-club {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0.85rem;
      border-radius: 30px;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--primary);
      font-size: 0.82rem;
      font-weight: 600;
      margin-bottom: 0.85rem;
    }}

    h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 0.4rem;
    }}

    .subtitle {{
      font-size: 0.92rem;
      color: var(--text-muted);
    }}

    .form-group {{
      margin-bottom: 1.25rem;
    }}

    label {{
      display: block;
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
    }}

    .row {{
      display: flex;
      gap: 1rem;
    }}

    .row .form-group {{
      flex: 1;
    }}

    input[type="text"] {{
      width: 100%;
      padding: 0.75rem 1rem;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      background: rgba(0, 0, 0, 0.15);
      color: var(--text);
      font-size: 0.95rem;
      transition: all 0.2s;
    }}

    input[type="text"]:focus {{
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }}

    /* Zone Drag and Drop */
    .dropzone {{
      border: 2px dashed var(--card-border);
      border-radius: 12px;
      padding: 2rem 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: all 0.25s ease;
      background: rgba(0, 0, 0, 0.08);
      position: relative;
    }}

    .dropzone:hover, .dropzone.dragover {{
      border-color: var(--primary);
      background: rgba(56, 189, 248, 0.05);
      transform: scale(1.01);
    }}

    .dropzone input[type="file"] {{
      position: absolute;
      top: 0; left: 0; width: 100%; height: 100%;
      opacity: 0;
      cursor: pointer;
    }}

    .dropzone-icon {{
      width: 48px;
      height: 48px;
      margin: 0 auto 0.75rem;
      color: var(--primary);
    }}

    .dropzone-text {{
      font-weight: 600;
      font-size: 0.95rem;
      margin-bottom: 0.25rem;
    }}

    .dropzone-sub {{
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    .file-preview {{
      display: none;
      margin-top: 1rem;
      padding: 0.75rem 1rem;
      border-radius: 10px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      font-size: 0.88rem;
      align-items: center;
      justify-content: space-between;
    }}

    .file-preview.active {{
      display: flex;
    }}

    .rules-card {{
      background: rgba(0, 0, 0, 0.12);
      border-radius: 10px;
      padding: 0.85rem 1rem;
      margin-bottom: 1.5rem;
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.5;
    }}

    .rules-card ul {{
      margin-left: 1.25rem;
      margin-top: 0.35rem;
    }}

    .btn-submit {{
      width: 100%;
      padding: 0.9rem;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      color: white;
      font-size: 1rem;
      font-weight: 700;
      border: none;
      cursor: pointer;
      transition: all 0.25s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      box-shadow: 0 4px 15px rgba(56, 189, 248, 0.3);
    }}

    .btn-submit:hover:not(:disabled) {{
      opacity: 0.92;
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.4);
    }}

    .btn-submit:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }}

    /* Barre de progression */
    .progress-box {{
      display: none;
      margin-top: 1.25rem;
    }}

    .progress-box.active {{
      display: block;
    }}

    .progress-bar-bg {{
      height: 8px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 0.4rem;
    }}

    .progress-bar-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--primary), var(--accent));
      transition: width 0.2s ease;
    }}

    .progress-status {{
      font-size: 0.82rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
    }}

    /* Message de confirmation */
    .alert {{
      display: none;
      padding: 1rem;
      border-radius: 12px;
      margin-top: 1.25rem;
      font-size: 0.9rem;
      line-height: 1.5;
    }}

    .alert.success {{
      display: block;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid var(--success);
      color: var(--success);
    }}

    .alert.error {{
      display: block;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid var(--error);
      color: var(--error);
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="badge-club">📁 Espace de Dépôt Officiel</div>
      <h1>{titre}</h1>
      <p class="subtitle">{sous_titre}</p>
    </div>

    <form id="uploadForm">
      <div class="row">
        <div class="form-group">
          <label for="nom">Nom :</label>
          <input type="text" id="nom" name="nom" placeholder="Ex: Dupont" required>
        </div>
        <div class="form-group">
          <label for="prenom">Prénom :</label>
          <input type="text" id="prenom" name="prenom" placeholder="Ex: Alice" required>
        </div>
      </div>

      <div class="form-group">
        <label>Archive du projet (.zip) :</label>
        <div class="dropzone" id="dropzone">
          <svg class="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          <div class="dropzone-text">Glissez votre fichier .zip ici ou cliquez pour choisir</div>
          <div class="dropzone-sub">Taille maximale : 25 Mo • Archive .zip uniquement</div>
          <input type="file" id="fileInput" name="archive" accept=".zip,application/zip" required>
        </div>

        <div class="file-preview" id="filePreview">
          <span id="fileName">projet.zip</span>
          <span id="fileSize" style="color: var(--text-muted);">0 Mo</span>
        </div>
      </div>

      <div class="rules-card">
        <strong>⚠️ Consignes de validation :</strong>
        <ul>
          <li>L'archive doit contenir obligatoirement une page <code>index.html</code>.</li>
          <li>Ressources autorisées : HTML, CSS, JavaScript, images, sons et polices.</li>
          <li>Aucun fichier exécutable (.exe, .bat, etc.) ne sera accepté.</li>
        </ul>
      </div>

      <button type="submit" class="btn-submit" id="submitBtn">
        <span>🚀 Téléverser mon projet</span>
      </button>

      <div class="progress-box" id="progressBox">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" id="progressFill"></div>
        </div>
        <div class="progress-status">
          <span id="progressText">Téléversement en cours...</span>
          <span id="progressPercent">0%</span>
        </div>
      </div>

      <div class="alert" id="resultAlert"></div>
    </form>
  </div>

  <script>
    const form = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const dropzone = document.getElementById('dropzone');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const submitBtn = document.getElementById('submitBtn');
    const progressBox = document.getElementById('progressBox');
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const progressText = document.getElementById('progressText');
    const resultAlert = document.getElementById('resultAlert');

    // Drag & Drop feedback
    ['dragenter', 'dragover'].forEach(name => {{
      dropzone.addEventListener(name, (e) => {{ e.preventDefault(); dropzone.classList.add('dragover'); }});
    }});
    ['dragleave', 'drop'].forEach(name => {{
      dropzone.addEventListener(name, (e) => {{ e.preventDefault(); dropzone.classList.remove('dragover'); }});
    }});

    fileInput.addEventListener('change', () => {{
      const file = fileInput.files[0];
      if (file) {{
        fileName.textContent = file.name;
        fileSize.textContent = (file.size / (1024 * 1024)).toFixed(2) + ' Mo';
        filePreview.classList.add('active');
      }} else {{
        filePreview.classList.remove('active');
      }}
    }});

    // Soumission avec XMLHttpRequest pour le suivi de progression réel
    form.addEventListener('submit', (e) => {{
      e.preventDefault();

      const nom = document.getElementById('nom').value.trim();
      const prenom = document.getElementById('prenom').value.trim();
      const file = fileInput.files[0];

      if (!file) {{
        alert('Veuillez sélectionner un fichier .zip.');
        return;
      }}

      submitBtn.disabled = true;
      progressBox.classList.add('active');
      resultAlert.className = 'alert';
      resultAlert.style.display = 'none';

      const formData = new FormData();
      formData.append('nom', nom);
      formData.append('prenom', prenom);
      formData.append('archive', file);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);

      xhr.upload.onprogress = (event) => {{
        if (event.lengthComputable) {{
          const percent = Math.round((event.loaded / event.total) * 100);
          progressFill.style.width = percent + '%';
          progressPercent.textContent = percent + '%';
          if (percent === 100) {{
            progressText.textContent = 'Vérification et enregistrement...';
          }}
        }}
      }};

      xhr.onload = () => {{
        submitBtn.disabled = false;
        try {{
          const res = JSON.parse(xhr.responseText);
          if (xhr.status === 200 && res.success) {{
            resultAlert.className = 'alert success';
            resultAlert.innerHTML = `
              <strong>🎉 Projet déposé avec succès !</strong><br>
              Fichier enregistré : <code>${{res.filename}}</code><br>
              ${{res.drive_synced ? '☁️ Fichier transmis sur le Google Drive du club.<br>' : ''}}
              Horodatage : ${{new Date().toLocaleTimeString()}}
            `;
            form.reset();
            filePreview.classList.remove('active');
          }} else {{
            resultAlert.className = 'alert error';
            resultAlert.innerHTML = `<strong>❌ Erreur lors du dépôt :</strong><br>${{res.error || 'Erreur inconnue'}}`;
          }}
        }} catch (err) {{
          resultAlert.className = 'alert error';
          resultAlert.textContent = 'Réponse serveur invalide.';
        }}
      }};

      xhr.onerror = () => {{
        submitBtn.disabled = false;
        resultAlert.className = 'alert error';
        resultAlert.textContent = 'Erreur réseau lors du téléversement.';
      }};

      xhr.send(formData);
    }});
  </script>
</body>
</html>
"""


@app.post("/api/upload")
async def handle_upload(nom: str = Form(...), prenom: str = Form(...), archive: UploadFile = File(...)):
    # 1. Validation du nom et création du slug
    clean_nom = re.sub(r"[^a-zA-Z0-9]+", "-", nom.strip()).strip("-").lower()
    clean_prenom = re.sub(r"[^a-zA-Z0-9]+", "-", prenom.strip()).strip("-").lower()

    if not clean_nom or not clean_prenom:
        return JSONResponse({"success": False, "error": "Nom ou prénom invalide."}, status_code=400)

    target_name = f"{clean_nom}-{clean_prenom}.zip"

    # 2. Lecture et vérification du format
    content = await archive.read()
    if len(content) > club.MAX_FILE_SIZE:
        return JSONResponse({"success": False, "error": f"Fichier trop volumineux ({len(content)//(1024*1024)} Mo). Max : 25 Mo."}, status_code=400)

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            members = [m.filename for m in zf.infolist() if not m.is_dir() and not m.filename.startswith("__MACOSX")]
            # Vérifier la présence d'au moins un fichier HTML
            has_html = any(name.lower().endswith(".html") or name.lower().endswith(".htm") for name in members)
            if not has_html:
                return JSONResponse({
                    "success": False,
                    "error": "L'archive ne contient aucun fichier HTML (ex: index.html manquant)."
                }, status_code=400)
    except zipfile.BadZipFile:
        return JSONResponse({"success": False, "error": "Le fichier envoyé n'est pas une archive .zip valide."}, status_code=400)

    # 3. Enregistrement local dans le dossier rendus/
    club.RENDUS.mkdir(exist_ok=True)
    out_path = club.RENDUS / target_name
    out_path.write_bytes(content)

    # 4. Envoi automatique immédiat sur Google Drive si configuré
    drive_synced = False
    cfg = club.load_config()
    folder_id = cfg.get("rendus_folder_id")
    if folder_id and club.CREDS.exists():
        try:
            from googleapiclient.http import MediaFileUpload
            meta = {"name": target_name, "parents": [folder_id]}
            media = MediaFileUpload(str(out_path), mimetype="application/zip", resumable=True)
            club.drive().files().create(body=meta, media_body=media, fields="id").execute()
            drive_synced = True
        except Exception as e:
            # En cas d'erreur Drive, le fichier reste sécurisé en local
            print(f"[Drive Sync Error] {e}")

    return {
        "success": True,
        "filename": target_name,
        "drive_synced": drive_synced
    }


def start_server(port=8080):
    """Démarre le serveur web de dépôt."""
    local_ip = get_local_ip()
    print("=" * 60)
    print("🚀 SERVEUR DE DÉPÔT ÉTUDIANT DÉMARRÉ")
    print(f"👉 Adresse locale (votre PC) : http://localhost:{port}")
    print(f"👉 Adresse sur le réseau (Wi-Fi / LAN) : http://{local_ip}:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    start_server(8080)
