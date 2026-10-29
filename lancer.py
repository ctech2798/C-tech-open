"""Gestionnaire de Projets Étudiants • Application unifiée tout-en-un."""
import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

# Définition du répertoire de travail (compatible PyInstaller .exe)
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent

import club
import serveur_depot


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Club • Gestionnaire & Collecteur de Projets")
        self.geometry("860x650")
        self.minsize(780, 560)

        # Style TTK moderne
        self._setup_styles()

        self.server_instance = None
        self.server_thread = None
        self.server_running = False
        self.local_ip = serveur_depot.get_local_ip()

        # Onglets principaux
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_main = ttk.Frame(notebook, padding=14)
        self.tab_config = ttk.Frame(notebook, padding=16)
        self.tab_help = ttk.Frame(notebook, padding=16)

        notebook.add(self.tab_main, text="  ⚡ Tableau de Bord Unifié  ")
        notebook.add(self.tab_config, text="  ⚙️ Paramètres  ")
        notebook.add(self.tab_help, text="  📖 Guide & Aide  ")

        self._build_main_tab()
        self._build_config_tab()
        self._build_help_tab()

        # Démarrage du serveur local uniquement si aucun lien en ligne n'est configuré
        if not self.online_link:
            self.start_upload_server(silent=True)
            self.log("[SUCCES] Logiciel prêt. Le lien de dépôt réseau est actif pour les étudiants.")
        else:
            self.log(f"[SUCCES] Logiciel prêt. Lien de dépôt en ligne : {self.online_link}")

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6)
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), foreground="#0284c7")
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"), foreground="#047857")
        style.configure("Muted.TLabel", foreground="#64748b")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#0f172a")

    # ---------- Tableau de bord unifié ----------
    def _build_main_tab(self):
        # 1. Section Dépôt Étudiants
        depot_frame = ttk.LabelFrame(self.tab_main, text=" 1. Espace de Téléversement des Étudiants ", padding=12)
        depot_frame.pack(fill="x", pady=(0, 12))

        top_line = ttk.Frame(depot_frame)
        top_line.pack(fill="x", pady=(0, 8))

        cfg = club.load_config()
        default_public_url = "https://script.google.com/macros/s/AKfycbzXl0v_h0i8JsnD-M_iq72Yv73DlwdihRPhU3bnwi_uMQqoMFFJD-b28S6Zncuit0DL-g/exec"
        self.online_link = cfg.get("lien_depot_web", "").strip() or default_public_url

        self.lbl_server_status = ttk.Label(top_line, text="🌐 Lien de dépôt en ligne (Accessible 24h/24 partout sur Internet)", style="Status.TLabel")
        self.lbl_server_status.pack(side="left")

        # Boîte du lien principal
        link_box = ttk.Frame(depot_frame)
        link_box.pack(fill="x", pady=(4, 6))

        ttk.Label(link_box, text="Lien à donner aux étudiants :", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 8))

        self.entry_link = ttk.Entry(link_box, font=("Segoe UI", 10), width=38)
        self.entry_link.insert(0, self.online_link)
        self.entry_link.configure(state="readonly")
        self.entry_link.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(link_box, text="📋 Copier le lien", style="Primary.TButton", command=self.copy_link).pack(side="left", padx=(0, 6))
        ttk.Button(link_box, text="🌐 Ouvrir le lien", command=self.open_current_link).pack(side="left")

        # Compteur et infos
        info_line = ttk.Frame(depot_frame)
        info_line.pack(fill="x", pady=(6, 0))

        self.lbl_count = ttk.Label(
            info_line,
            text="📦 0 archive(s) reçue(s) dans le dossier 'rendus/'",
            font=("Segoe UI", 9, "bold"),
            foreground="#0369a1"
        )
        self.lbl_count.pack(side="left")

        if not self.online_link:
            ttk.Label(
                info_line,
                text="💡 Astuce : Déployez votre page en ligne (voir onglet Guide) pour un lien public 24h/24.",
                style="Muted.TLabel"
            ).pack(side="right")
        else:
            ttk.Label(
                info_line,
                text="✅ Page web en ligne active.",
                foreground="#047857",
                font=("Segoe UI", 9, "bold")
            ).pack(side="right")

        # 2. Section Traitement & Génération du site
        actions_frame = ttk.LabelFrame(self.tab_main, text=" 2. Construction du Portail & Synchronisation ", padding=12)
        actions_frame.pack(fill="x", pady=(0, 12))

        btn_row = ttk.Frame(actions_frame)
        btn_row.pack(fill="x", pady=(0, 8))

        self.action_buttons = []

        b_build = ttk.Button(
            btn_row,
            text="🔨 Construire le site",
            style="Action.TButton",
            command=lambda: self.run_steps([club.build], "Construction du site web")
        )
        b_build.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b_build)

        b_all = ttk.Button(
            btn_row,
            text="⚡ Tout Faire (Sync Drive + Construire + Sauvegarde)",
            style="Primary.TButton",
            command=self.run_full_process
        )
        b_all.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b_all)

        ttk.Button(btn_row, text="🌐 Ouvrir le Portail Web", style="Big.TButton", command=self.open_site).pack(side="right", padx=(4, 0))
        ttk.Button(btn_row, text="📁 Dossier Rendus", command=lambda: self.open_folder(club.RENDUS)).pack(side="right")

        # Statut & barre de progression
        status_bar = ttk.Frame(actions_frame)
        status_bar.pack(fill="x", pady=(4, 0))

        self.status_var = tk.StringVar(value="Prêt")
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 9, "italic"))
        self.status_label.pack(side="left")

        self.progress = ttk.Progressbar(status_bar, mode="indeterminate", length=180)
        self.progress.pack(side="right")

        # 3. Console de logs
        log_frame = ttk.LabelFrame(self.tab_main, text=" Journal d'Activité en Direct ", padding=6)
        log_frame.pack(fill="both", expand=True)

        self.out = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            font=("Consolas", 9),
            bg="#0f172a",
            fg="#f8fafc",
            insertbackground="#ffffff",
            padx=8,
            pady=8
        )
        self.out.pack(fill="both", expand=True)

        self.out.tag_config("info", foreground="#94a3b8")
        self.out.tag_config("succes", foreground="#34d399", font=("Consolas", 9, "bold"))
        self.out.tag_config("attention", foreground="#fbbf24")
        self.out.tag_config("erreur", foreground="#f87171", font=("Consolas", 9, "bold"))

        ttk.Button(log_frame, text="Effacer le journal", command=self.clear_logs).pack(anchor="e", pady=(4, 0))

    # ---------- Surveillance du compteur de fichiers ----------
    def _poll_received_count(self):
        try:
            club.RENDUS.mkdir(exist_ok=True)
            count = len(list(club.RENDUS.glob("*.zip")))
            self.lbl_count.configure(text=f"📦 {count} projet(s) reçu(s) dans le dossier 'rendus/'")
        except Exception:
            pass
        self.after(2000, self._poll_received_count)

    # ---------- Serveur de dépôt Web ----------
    def start_upload_server(self, silent=False):
        import uvicorn

        if self.server_running:
            return

        def run():
            cfg = uvicorn.Config(serveur_depot.app, host="0.0.0.0", port=8080, log_level="warning")
            self.server_instance = uvicorn.Server(cfg)
            self.server_instance.run()

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()
        self.server_running = True
        if hasattr(self, "lbl_server_status") and not self.online_link:
            self.lbl_server_status.configure(text="🟢 Serveur de dépôt en ligne", foreground="#047857")

        if not silent:
            self.log(f"[SUCCES] Serveur de dépôt en ligne sur http://{self.local_ip}:8080")

    def restart_upload_server(self):
        self.local_ip = serveur_depot.get_local_ip()
        self.entry_link.configure(state="normal")
        self.entry_link.delete(0, "end")
        self.entry_link.insert(0, f"http://{self.local_ip}:8080")
        self.entry_link.configure(state="readonly")
        self.log(f"[INFO] Adresse réseau actualisée : http://{self.local_ip}:8080")
        messagebox.showinfo("Serveur", f"Lien réseau actualisé :\nhttp://{self.local_ip}:8080")

    def open_current_link(self):
        link = self.entry_link.get().strip()
        if link:
            webbrowser.open(link)

    def copy_link(self):
        link = self.entry_link.get().strip()
        self.clipboard_clear()
        self.clipboard_append(link)
        messagebox.showinfo("Lien Copié", f"Le lien a été copié dans le presse-papier :\n{link}\n\nDonnez-le aux étudiants !")

    # ---------- Onglet Paramètres ----------
    def _build_config_tab(self):
        cfg = club.load_config()

        ttk.Label(self.tab_config, text="Configuration Générale & Liens", style="Header.TLabel").pack(anchor="w", pady=(0, 14))

        form = ttk.Frame(self.tab_config)
        form.pack(fill="x", pady=(0, 16))

        # Lien Web en ligne
        ttk.Label(form, text="Lien Web public de dépôt :", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        self.var_lien_web = tk.StringVar(value=cfg.get("lien_depot_web", ""))
        entry_web = ttk.Entry(form, textvariable=self.var_lien_web, width=54)
        entry_web.grid(row=0, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(form, text="Titre du portail :").grid(row=1, column=0, sticky="w", pady=6)
        self.var_titre = tk.StringVar(value=cfg.get("titre", "Travaux des étudiants"))
        ttk.Entry(form, textvariable=self.var_titre, width=54).grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(form, text="Sous-titre :").grid(row=2, column=0, sticky="w", pady=6)
        self.var_sous_titre = tk.StringVar(value=cfg.get("sous_titre", "Portail des projets et réalisations web"))
        ttk.Entry(form, textvariable=self.var_sous_titre, width=54).grid(row=2, column=1, sticky="w", pady=6, padx=(10, 0))

        self.var_anonymiser = tk.BooleanVar(value=cfg.get("anonymiser", False))
        ttk.Checkbutton(form, text="Anonymiser les projets (ex: Projet 01, Projet 02...)", variable=self.var_anonymiser).grid(row=3, column=1, sticky="w", pady=8, padx=(10, 0))

        ttk.Separator(self.tab_config, orient="horizontal").pack(fill="x", pady=12)

        drive_frame = ttk.LabelFrame(self.tab_config, text=" Google Drive (Optionnel) ", padding=12)
        drive_frame.pack(fill="x", pady=(0, 16))

        ttk.Label(drive_frame, text="ID Dossier 'Rendus' :").grid(row=0, column=0, sticky="w", pady=6)
        self.var_rendus_id = tk.StringVar(value=cfg.get("rendus_folder_id", ""))
        ttk.Entry(drive_frame, textvariable=self.var_rendus_id, width=54).grid(row=0, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(drive_frame, text="ID Dossier 'Sauvegardes' :").grid(row=1, column=0, sticky="w", pady=6)
        self.var_sauv_id = tk.StringVar(value=cfg.get("sauvegarde_folder_id", ""))
        ttk.Entry(drive_frame, textvariable=self.var_sauv_id, width=54).grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))

        btn_bar = ttk.Frame(self.tab_config)
        btn_bar.pack(fill="x", pady=10)

        ttk.Button(btn_bar, text="💾 Enregistrer les paramètres", style="Primary.TButton", command=self.save_settings).pack(side="left")
        ttk.Button(btn_bar, text="🔑 Tester la connexion Drive", command=self.test_drive).pack(side="right")

    # ---------- Onglet Aide ----------
    def _build_help_tab(self):
        ttk.Label(self.tab_help, text="Guide d'utilisation simplifié", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

        help_text = (
            "COMMENT FONCTIONNE LE LOGICIEL ?\n\n"
            "1. DÉPÔT DES ÉTUDIANTS :\n"
            "   • Au démarrage, l'application crée automatiquement un espace de dépôt sur votre réseau local.\n"
            "   • Cliquez sur '📋 Copier le lien' et transmettez-le aux étudiants (ex: http://192.168.1.XX:8080).\n"
            "   • Dès qu'un étudiant valide son envoi, son archive apparaît directement dans votre dossier 'rendus/'.\n\n"
            "2. GÉNÉRATION DU SITE VITRINE :\n"
            "   • Cliquez sur '🔨 Construire le site' : le logiciel extrait et contrôle chaque archive de manière sécurisée.\n"
            "   • Cliquez sur '🌐 Ouvrir le Portail Web' pour parcourir la galerie avec recherche instantanée et aperçu direct.\n\n"
            "3. CONNEXION GOOGLE DRIVE (OPTIONNELLE) :\n"
            "   • Si vous souhaitez synchroniser et sauvegarder sur Drive, renseignez vos identifiants dans 'Paramètres'.\n"
            "   • Le logiciel fonctionne aussi à 100% en local sans Google Drive !"
        )

        txt = scrolledtext.ScrolledText(self.tab_help, wrap="word", font=("Segoe UI", 9), height=14)
        txt.insert("1.0", help_text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

    # ---------- Actions et exécution ----------
    def log(self, msg):
        def write():
            self.out.configure(state="normal")
            tag = None
            if msg.startswith("[SUCCES]"): tag = "succes"
            elif msg.startswith("[ERREUR]"): tag = "erreur"
            elif msg.startswith("[ATTENTION]") or msg.startswith("[A VERIFIER]"): tag = "attention"
            elif msg.startswith("[INFO]"): tag = "info"

            self.out.insert("end", msg + "\n", tag)
            self.out.see("end")
            self.out.configure(state="disabled")

        self.after(0, write)

    def clear_logs(self):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.configure(state="disabled")

    def run_full_process(self):
        cfg = club.load_config()
        rendus_id = cfg.get("rendus_folder_id", "").strip()
        sauv_id = cfg.get("sauvegarde_folder_id", "").strip()

        # Si Drive est configuré, on fait tout
        if rendus_id and sauv_id and club.CREDS.exists():
            self.run_steps([club.sync, club.build, club.backup], "Synchronisation, Construction et Sauvegarde")
        else:
            # Mode local automatique sans forcer Drive
            self.run_steps([club.build], "Construction du site web (Mode local)")

    def run_steps(self, steps, task_name="Opération"):
        for b in self.action_buttons:
            b.state(["disabled"])
        self.progress.start(10)
        self.status_var.set(f"En cours : {task_name}...")

        def work():
            try:
                current_cfg = club.load_config()
                for step in steps:
                    step(current_cfg, self.log)
                self.status_var.set("Terminé avec succès")
            except Exception as e:
                self.log(f"[ERREUR] Échec : {e}")
                self.status_var.set("Erreur survenue")
            finally:
                self.after(0, self._on_work_finished)

        threading.Thread(target=work, daemon=True).start()

    def _on_work_finished(self):
        self.progress.stop()
        for b in self.action_buttons:
            b.state(["!disabled"])

    def open_site(self):
        page = club.SITE / "index.html"
        if page.exists():
            webbrowser.open(page.as_uri())
        else:
            messagebox.showinfo("Site web", "Construisez d'abord le site en cliquant sur '🔨 Construire le site'.")

    def open_folder(self, path: Path):
        path.mkdir(exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            webbrowser.open(path.as_uri())

    def save_settings(self):
        new_link = self.var_lien_web.get().strip()
        cfg = {
            "titre": self.var_titre.get().strip(),
            "sous_titre": self.var_sous_titre.get().strip(),
            "anonymiser": self.var_anonymiser.get(),
            "rendus_folder_id": self.var_rendus_id.get().strip(),
            "sauvegarde_folder_id": self.var_sauv_id.get().strip(),
            "lien_depot_web": new_link
        }
        club.save_config(cfg)

        # Mettre à jour l'entrée du tableau de bord
        self.entry_link.configure(state="normal")
        self.entry_link.delete(0, "end")
        self.entry_link.insert(0, new_link if new_link else f"http://{self.local_ip}:8080")
        self.entry_link.configure(state="readonly")

        self.log("[SUCCES] Paramètres enregistrés avec succès.")
        messagebox.showinfo("Paramètres", "Paramètres et lien de dépôt enregistrés avec succès !")

    def test_drive(self):
        self.log("[INFO] Test de la configuration Google Drive...")
        if not club.CREDS.exists():
            messagebox.showerror("Erreur", "Fichier 'credentials.json' introuvable.")
            return

        def work():
            try:
                svc = club.drive()
                user = svc.about().get(fields="user").execute().get("user", {})
                self.log(f"[SUCCES] Connexion Google Drive réussie : {user.get('displayName')} ({user.get('emailAddress')})")
                messagebox.showinfo("Succès", f"Connexion réussie avec {user.get('displayName')} !")
            except Exception as e:
                self.log(f"[ERREUR] Échec Google Drive : {e}")
                messagebox.showerror("Erreur", f"Échec de connexion :\n{e}")

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
