"""Interface graphique moderne pour la gestion des projets du club."""
import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import club


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Club • Gestionnaire de Projets Étudiants")
        self.geometry("820x600")
        self.minsize(740, 520)

        # Style TTK moderne
        self._setup_styles()

        # Onglets principaux
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_dashboard = ttk.Frame(notebook, padding=12)
        self.tab_upload = ttk.Frame(notebook, padding=14)
        self.tab_config = ttk.Frame(notebook, padding=16)
        self.tab_help = ttk.Frame(notebook, padding=16)

        notebook.add(self.tab_dashboard, text="  ⚡ Tableau de Bord  ")
        notebook.add(self.tab_upload, text="  🚀 Espace de Dépôt (Lien)  ")
        notebook.add(self.tab_config, text="  ⚙️ Paramètres  ")
        notebook.add(self.tab_help, text="  📖 Guide & Aide  ")

        self.server_thread = None
        self.server_running = False

        self._build_dashboard_tab()
        self._build_upload_tab()
        self._build_config_tab()
        self._build_help_tab()

        # Message d'accueil dans la console
        self.log("[INFO] Gestionnaire de projets initialisé avec succès.")
        cfg = club.load_config()
        if not club.CREDS.exists():
            self.log("[ATTENTION] Le fichier 'credentials.json' est absent. La synchronisation Drive nécessite ce fichier (voir l'onglet Guide).")
        elif "COLLEZ_ICI" in cfg.get("rendus_folder_id", ""):
            self.log("[ATTENTION] Les identifiants de dossiers Drive ne sont pas configurés. Rendez-vous dans l'onglet 'Paramètres'.")
        else:
            self.log("[SUCCES] Prêt ! Cliquez sur '⚡ Tout faire' ou sur une étape spécifique.")

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Configuration des polices et styles
        style.configure(".", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6)
        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), foreground="#0284c7")
        style.configure("Action.TButton", font=("Segoe UI", 9), padding=5)
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", foreground="#64748b")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#0f172a")

    # ---------- Onglet Tableau de bord ----------
    def _build_dashboard_tab(self):
        # Barre d'actions supérieures
        actions_frame = ttk.LabelFrame(self.tab_dashboard, text=" Actions Principales ", padding=10)
        actions_frame.pack(fill="x", pady=(0, 10))

        btn_box = ttk.Frame(actions_frame)
        btn_box.pack(fill="x")

        self.action_buttons = []

        b1 = ttk.Button(btn_box, text="1. 📥 Récupérer du Drive", style="Action.TButton",
                        command=lambda: self.run_steps([club.sync], "Récupération depuis Google Drive"))
        b1.pack(side="left", padx=(0, 6))
        self.action_buttons.append(b1)

        b2 = ttk.Button(btn_box, text="2. 🔨 Construire le site", style="Action.TButton",
                        command=lambda: self.run_steps([club.build], "Construction du site"))
        b2.pack(side="left", padx=(0, 6))
        self.action_buttons.append(b2)

        b3 = ttk.Button(btn_box, text="3. 💾 Sauvegarder sur Drive", style="Action.TButton",
                        command=lambda: self.run_steps([club.backup], "Sauvegarde vers Google Drive"))
        b3.pack(side="left", padx=(0, 6))
        self.action_buttons.append(b3)

        b_all = ttk.Button(btn_box, text="⚡ Tout faire", style="Primary.TButton",
                           command=lambda: self.run_steps([club.sync, club.build, club.backup], "Processus complet"))
        b_all.pack(side="left", padx=(6, 0))
        self.action_buttons.append(b_all)

        # Accès rapides à droite
        quick_box = ttk.Frame(actions_frame)
        quick_box.pack(fill="x", pady=(8, 0))

        ttk.Button(quick_box, text="🌐 Voir le site web", command=self.open_site).pack(side="right", padx=(4, 0))
        ttk.Button(quick_box, text="📁 Dossier Site", command=lambda: self.open_folder(club.SITE)).pack(side="right", padx=(4, 0))
        ttk.Button(quick_box, text="📁 Dossier Rendus", command=lambda: self.open_folder(club.RENDUS)).pack(side="right")

        # Barre d'état et progression
        status_box = ttk.Frame(self.tab_dashboard)
        status_box.pack(fill="x", pady=(0, 6))

        self.status_var = tk.StringVar(value="Prêt")
        self.status_label = ttk.Label(status_box, textvariable=self.status_var, font=("Segoe UI", 9, "italic"))
        self.status_label.pack(side="left")

        self.progress = ttk.Progressbar(status_box, mode="indeterminate", length=160)
        self.progress.pack(side="right")

        # Console de logs avec mise en forme
        log_frame = ttk.LabelFrame(self.tab_dashboard, text=" Journal d'exécution ", padding=6)
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

        # Tags de coloration dans la console
        self.out.tag_config("info", foreground="#94a3b8")
        self.out.tag_config("succes", foreground="#34d399", font=("Consolas", 9, "bold"))
        self.out.tag_config("attention", foreground="#fbbf24")
        self.out.tag_config("erreur", foreground="#f87171", font=("Consolas", 9, "bold"))

        # Bouton pour effacer les logs
        ttk.Button(log_frame, text="Effacer le journal", command=self.clear_logs).pack(anchor="e", pady=(4, 0))

    # ---------- Onglet Espace de Dépôt ----------
    def _build_upload_tab(self):
        import serveur_depot
        self.local_ip = serveur_depot.get_local_ip()

        ttk.Label(self.tab_upload, text="Espace de Dépôt Web pour les Étudiants", style="Header.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(
            self.tab_upload,
            text="Permet aux étudiants d'accéder à une page web moderne pour téléverser leur projet .zip (avec contrôle de conformité).",
            style="Muted.TLabel"
        ).pack(anchor="w", pady=(0, 16))

        # Boîte Serveur
        srv_frame = ttk.LabelFrame(self.tab_upload, text=" Serveur Web Intégré ", padding=14)
        srv_frame.pack(fill="x", pady=(0, 16))

        status_line = ttk.Frame(srv_frame)
        status_line.pack(fill="x", pady=(0, 12))

        self.srv_status_var = tk.StringVar(value="⚫ Serveur arrêté")
        ttk.Label(status_line, textvariable=self.srv_status_var, font=("Segoe UI", 10, "bold")).pack(side="left")

        self.btn_toggle_server = ttk.Button(
            status_line,
            text="🚀 Démarrer le serveur de dépôt",
            style="Primary.TButton",
            command=self.toggle_upload_server
        )
        self.btn_toggle_server.pack(side="right")

        # Liens d'accès
        links_box = ttk.Frame(srv_frame)
        links_box.pack(fill="x", pady=(4, 0))

        # Lien réseau pour les étudiants
        ttk.Label(links_box, text="Lien à partager aux étudiants (Wi-Fi / Réseau local) :", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.entry_net_link = ttk.Entry(links_box, width=42)
        self.entry_net_link.insert(0, f"http://{self.local_ip}:8080")
        self.entry_net_link.configure(state="readonly")
        self.entry_net_link.grid(row=0, column=1, sticky="w", padx=(10, 6), pady=4)

        ttk.Button(links_box, text="📋 Copier", command=lambda: self.copy_to_clipboard(f"http://{self.local_ip}:8080")).grid(row=0, column=2, pady=4)

        # Lien local pour tester
        ttk.Label(links_box, text="Lien local (sur ce PC) :").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_loc_link = ttk.Entry(links_box, width=42)
        self.entry_loc_link.insert(0, "http://localhost:8080")
        self.entry_loc_link.configure(state="readonly")
        self.entry_loc_link.grid(row=1, column=1, sticky="w", padx=(10, 6), pady=4)

        ttk.Button(links_box, text="🌐 Tester la page", command=lambda: webbrowser.open("http://localhost:8080")).grid(row=1, column=2, pady=4)

        # Boîte d'informations complémentaires
        info_frame = ttk.LabelFrame(self.tab_upload, text=" 💡 Comment partager ce lien ? ", padding=12)
        info_frame.pack(fill="both", expand=True)

        tips = (
            "1. SUR LE MÊME RÉSEAU (En salle de cours / Wi-Fi de l'établissement / à la maison) :\n"
            f"   • Donnez simplement le lien 'http://{self.local_ip}:8080' aux étudiants.\n"
            "   • Tous les appareils connectés au même réseau peuvent y déposer leur projet.\n\n"
            "2. À DISTANCE PAR INTERNET (Depuis chez eux) :\n"
            "   • Option A : Utilisez un tunnel gratuit et sécurisé (ex: 'cloudflared tunnel' ou 'localtunnel') pour obtenir un lien HTTPS public 'https://mon-club.trycloudflare.com'.\n"
            "   • Option B : Créez un Google Formulaire avec import de fichier lié à votre dossier Drive 'Rendus'.\n\n"
            "3. TRAITEMENT AUTOMATIQUE DES DÉPÔTS :\n"
            "   • Les projets déposés sont automatiquement renommés en 'nom-prenom.zip'.\n"
            "   • Ils sont enregistrés directement dans le dossier 'rendus/' et envoyés sur Google Drive (si configuré)."
        )
        tbox = scrolledtext.ScrolledText(info_frame, wrap="word", font=("Segoe UI", 9), height=10)
        tbox.insert("1.0", tips)
        tbox.configure(state="disabled")
        tbox.pack(fill="both", expand=True)

    def toggle_upload_server(self):
        import uvicorn
        import serveur_depot

        if not self.server_running:
            def run():
                config = uvicorn.Config(serveur_depot.app, host="0.0.0.0", port=8080, log_level="warning")
                self.server_instance = uvicorn.Server(config)
                self.server_instance.run()

            self.server_thread = threading.Thread(target=run, daemon=True)
            self.server_thread.start()
            self.server_running = True

            self.srv_status_var.set("🟢 Serveur en ligne sur le port 8080")
            self.btn_toggle_server.configure(text="🛑 Arrêter le serveur")
            self.log(f"[SUCCES] Serveur de dépôt démarré sur http://{self.local_ip}:8080")
            webbrowser.open("http://localhost:8080")
        else:
            if hasattr(self, 'server_instance'):
                self.server_instance.should_exit = True
            self.server_running = False
            self.srv_status_var.set("⚫ Serveur arrêté")
            self.btn_toggle_server.configure(text="🚀 Démarrer le serveur de dépôt")
            self.log("[INFO] Serveur de dépôt arrêté.")

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copié !", f"Le lien a été copié dans votre presse-papier :\n{text}")

    # ---------- Onglet Paramètres ----------
    def _build_config_tab(self):
        cfg = club.load_config()

        ttk.Label(self.tab_config, text="Configuration du Portail et de Google Drive", style="Header.TLabel").pack(anchor="w", pady=(0, 14))

        # Formulaire
        form = ttk.Frame(self.tab_config)
        form.pack(fill="x", pady=(0, 16))

        # Titre
        ttk.Label(form, text="Titre du portail :").grid(row=0, column=0, sticky="w", pady=6)
        self.var_titre = tk.StringVar(value=cfg.get("titre", "Travaux des étudiants"))
        ttk.Entry(form, textvariable=self.var_titre, width=50).grid(row=0, column=1, sticky="w", pady=6, padx=(10, 0))

        # Sous-titre
        ttk.Label(form, text="Sous-titre / Description :").grid(row=1, column=0, sticky="w", pady=6)
        self.var_sous_titre = tk.StringVar(value=cfg.get("sous_titre", "Portail des projets et réalisations web"))
        ttk.Entry(form, textvariable=self.var_sous_titre, width=50).grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))

        # Anonymisation
        self.var_anonymiser = tk.BooleanVar(value=cfg.get("anonymiser", False))
        cb = ttk.Checkbutton(form, text="Anonymiser les noms (ex: Projet 01, Projet 02...)", variable=self.var_anonymiser)
        cb.grid(row=2, column=1, sticky="w", pady=8, padx=(10, 0))

        # Séparateur
        ttk.Separator(self.tab_config, orient="horizontal").pack(fill="x", pady=12)

        # Section Google Drive
        drive_frame = ttk.LabelFrame(self.tab_config, text=" Dossiers Google Drive ", padding=12)
        drive_frame.pack(fill="x", pady=(0, 16))

        ttk.Label(drive_frame, text="ID Dossier 'Rendus' (source des zips) :").grid(row=0, column=0, sticky="w", pady=6)
        self.var_rendus_id = tk.StringVar(value=cfg.get("rendus_folder_id", ""))
        ttk.Entry(drive_frame, textvariable=self.var_rendus_id, width=50).grid(row=0, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(drive_frame, text="ID Dossier 'Sauvegardes' (archives) :").grid(row=1, column=0, sticky="w", pady=6)
        self.var_sauv_id = tk.StringVar(value=cfg.get("sauvegarde_folder_id", ""))
        ttk.Entry(drive_frame, textvariable=self.var_sauv_id, width=50).grid(row=1, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(
            drive_frame,
            text="L'ID se trouve à la fin de l'URL du dossier Drive : drive.google.com/drive/folders/IDENTIFIANT",
            style="Muted.TLabel"
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Boutons de sauvegarde
        btn_bar = ttk.Frame(self.tab_config)
        btn_bar.pack(fill="x", pady=10)

        ttk.Button(btn_bar, text="💾 Enregistrer les paramètres", style="Primary.TButton", command=self.save_settings).pack(side="left")
        ttk.Button(btn_bar, text="🔄 Réinitialiser", command=self.reload_settings).pack(side="left", padx=(8, 0))
        ttk.Button(btn_bar, text="🔑 Tester la connexion Drive", command=self.test_drive).pack(side="right")

    # ---------- Onglet Aide ----------
    def _build_help_tab(self):
        ttk.Label(self.tab_help, text="Guide pas-à-pas et Dépannage", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

        help_text = (
            "1. FICHIER CREDENTIALS.JSON :\n"
            "   • Créez un projet sur console.cloud.google.com\n"
            "   • Activez l'API 'Google Drive API'\n"
            "   • Dans 'Identifiants', créez un identifiant OAuth de type 'Application de bureau'\n"
            "   • Téléchargez le JSON, renommez-le 'credentials.json' et placez-le dans ce dossier.\n\n"
            "2. STRUCTURE DES ARCHIVES DES ÉTUDIANTS :\n"
            "   • Les étudiants déposent un fichier 'nom-prenom.zip'.\n"
            "   • L'archive doit contenir au minimum un fichier HTML principal ('index.html').\n"
            "   • Seules les ressources web (HTML, CSS, JS, polices, images, sons) sont extraites.\n"
            "   • Tout fichier exécutable (.exe, .bat, .sh) est automatiquement écarté par sécurité.\n\n"
            "3. PUBLICATION DU SITE :\n"
            "   • Une fois le site construit, le dossier 'site/' est prêt à être publié.\n"
            "   • Vous pouvez le déposer directement sur Netlify Drop, GitHub Pages ou votre serveur.\n"
        )

        txt = scrolledtext.ScrolledText(self.tab_help, wrap="word", font=("Segoe UI", 9), height=14)
        txt.insert("1.0", help_text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

    # ---------- Méthodes utilitaires et actions ----------
    def log(self, msg):
        def write():
            self.out.configure(state="normal")
            tag = None
            if msg.startswith("[SUCCES]"):
                tag = "succes"
            elif msg.startswith("[ERREUR]"):
                tag = "erreur"
            elif msg.startswith("[ATTENTION]") or msg.startswith("[A VERIFIER]"):
                tag = "attention"
            elif msg.startswith("[INFO]"):
                tag = "info"

            if tag:
                self.out.insert("end", msg + "\n", tag)
            else:
                self.out.insert("end", msg + "\n")

            self.out.see("end")
            self.out.configure(state="disabled")

        self.after(0, write)

    def clear_logs(self):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.configure(state="disabled")

    def run_steps(self, steps, task_name="Opération"):
        cfg = club.load_config()
        needs_drive = (club.sync in steps) or (club.backup in steps)
        rendus_id = (cfg.get("rendus_folder_id") or "").strip()
        sauv_id = (cfg.get("sauvegarde_folder_id") or "").strip()

        # Si l'action requiert Drive mais que les IDs ne sont pas configurés
        if needs_drive and ("COLLEZ_ICI" in rendus_id or "COLLEZ_ICI" in sauv_id or not rendus_id):
            if club.build in steps and len(steps) > 1:
                # L'utilisateur a cliqué sur "Tout faire"
                rep = messagebox.askyesno(
                    "Dossiers Google Drive non configurés",
                    "Les identifiants Google Drive ne sont pas encore renseignés dans l'onglet 'Paramètres'.\n\n"
                    "Souhaitez-vous plutôt lancer la construction du site en MODE LOCAL avec les fichiers déjà présents dans 'rendus/' ?"
                )
                if rep:
                    self.run_steps([club.build], "Construction du site (Mode local)")
                return
            else:
                messagebox.showwarning(
                    "Configuration Google Drive requise",
                    "Veuillez renseigner les identifiants de vos dossiers Drive dans l'onglet '⚙️ Paramètres' "
                    "avant de lancer cette opération."
                )
                return

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
            messagebox.showinfo("Site web", "Le site n'a pas encore été construit. Cliquez sur '2. Construire le site'.")

    def open_folder(self, path: Path):
        path.mkdir(exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            webbrowser.open(path.as_uri())

    def save_settings(self):
        cfg = {
            "titre": self.var_titre.get().strip(),
            "sous_titre": self.var_sous_titre.get().strip(),
            "anonymiser": self.var_anonymiser.get(),
            "rendus_folder_id": self.var_rendus_id.get().strip(),
            "sauvegarde_folder_id": self.var_sauv_id.get().strip()
        }
        club.save_config(cfg)
        self.log("[SUCCES] Paramètres enregistrés avec succès dans config.json.")
        messagebox.showinfo("Paramètres", "Paramètres enregistrés avec succès !")

    def reload_settings(self):
        cfg = club.load_config()
        self.var_titre.set(cfg.get("titre", "Travaux des étudiants"))
        self.var_sous_titre.set(cfg.get("sous_titre", "Portail des projets et réalisations web"))
        self.var_anonymiser.set(cfg.get("anonymiser", False))
        self.var_rendus_id.set(cfg.get("rendus_folder_id", ""))
        self.var_sauv_id.set(cfg.get("sauvegarde_folder_id", ""))
        self.log("[INFO] Paramètres rechargés depuis config.json.")

    def test_drive(self):
        self.log("[INFO] Test de la configuration Google Drive...")
        cfg = club.load_config()
        if not club.CREDS.exists():
            messagebox.showerror(
                "Erreur Credentials",
                "Le fichier 'credentials.json' est introuvable.\nConsultez l'onglet Guide pour savoir comment le générer."
            )
            return

        def work():
            try:
                svc = club.drive()
                # Test de lecture simple
                user_info = svc.about().get(fields="user").execute()
                user_name = user_info.get("user", {}).get("displayName", "Inconnu")
                email = user_info.get("user", {}).get("emailAddress", "")
                self.log(f"[SUCCES] Connexion Google Drive réussie ! Compte : {user_name} ({email})")
                messagebox.showinfo("Connexion réussie", f"Connexion Google Drive OK !\nCompte : {user_name}\n({email})")
            except Exception as e:
                self.log(f"[ERREUR] Échec du test Google Drive : {e}")
                messagebox.showerror("Erreur de connexion", f"Impossible de contacter Google Drive :\n{e}")

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
