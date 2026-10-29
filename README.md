# Club • Gestionnaire de Projets Étudiants

Application moderne pour collecter les travaux des étudiants depuis Google Drive, inspecter leur contenu de manière sécurisée, générer un portail web vitrine interactif et effectuer des sauvegardes régulières.

---

## 🚀 Fonctionnalités Clés

- **Espace de Dépôt Web pour les Étudiants (Nouveau !)** :
  - Page web dédiée avec formulaire Nom / Prénom et zone de glisser-déposer (*Drag & Drop*).
  - Contrôle automatique avant enregistrement : vérification de l'archive `.zip`, présence obligatoire d'un `index.html`, rejet des exécutables.
  - Sauvegarde locale dans `rendus/nom-prenom.zip` et envoi automatique et direct sur Google Drive.
  - Lien partageable en un clic sur le réseau local (Wi-Fi de l'établissement ou salle de cours) ou à distance via tunnel.
- **Synchronisation Google Drive** : Récupération automatique et incrémentale des archives `.zip` déposées par les étudiants.
- **Portail Web Vitrine Moderne** :
  - Design soigné avec thème sombre/clair dynamique et responsive.
  - Recherche instantanée par nom ou étudiant.
  - Aperçu rapide intégré (*Live Preview*) dans une fenêtre modale sécurisée.
  - Cartes interactives détaillant le nombre de fichiers et la taille.
- **Sécurité et Conformité Renforcées** :
  - Protection contre les attaques d'archives (*Zip-Slip*, *Zip-bombs*, quotas de décompression).
  - Filtrage strict des fichiers autorisés (HTML, CSS, JS, polices web, images, vidéos/audios légitimes, documentation).
  - Détection automatique et signalement des dépendances et appels distants (CDNs, polices externes, `fetch`, `WebSocket`).
  - Tolérance aux variations de casse (`index.html`, `Index.html`) et sélection de secours.
- **Interface Graphique Complète** :
  - Tableau de bord avec suivi de progression et console de journalisation colorée.
  - Onglet Paramètres pour configurer directement le titre, le sous-titre, l'anonymisation et les identifiants Drive sans modifier de fichier manuellement.
  - Outil de test direct de la connexion Google Drive.
  - Accès en un clic au site web généré, au dossier des rendus et des sources.

---

## 🛠️ Installation

1. **Prérequis** : Python 3.10 ou supérieur.
2. **Dépendances** :
   ```bash
   pip install -r requirements.txt
   ```
3. **Identifiants Google Cloud (une seule fois)** :
   - Rendez-vous sur [Google Cloud Console](https://console.cloud.google.com).
   - Créez un projet et activez l'API **Google Drive API**.
   - Dans le menu **Identifiants**, créez un identifiant OAuth de type **Application de bureau**.
   - Téléchargez le fichier JSON obtenu, nommez-le `credentials.json` et déposez-le à la racine du dossier.
   - Au premier lancement, une fenêtre s'ouvrira dans votre navigateur pour autoriser l'accès au compte du club.

---

## 💻 Utilisation

1. Lancez l'application graphique :
   ```bash
   python lancer.py
   ```
   *(ou `py lancer.py` sous Windows)*.
2. Dans l'onglet **Paramètres**, indiquez :
   - Le titre de votre portail web.
   - L'identifiant de votre dossier Drive **Rendus** (fin de l'URL du dossier : `.../folders/IDENTIFIANT`).
   - L'identifiant de votre dossier Drive **Sauvegardes**.
   - Cliquez sur **Enregistrer les paramètres**.
3. Dans l'onglet **Tableau de Bord**, cliquez sur **⚡ Tout faire** :
   - Vos rendus sont téléchargés.
   - Le portail web est généré dans le dossier `site/`.
   - Une archive de sauvegarde est envoyée sur le Drive.
4. Cliquez sur **🌐 Voir le site web** pour admirer le résultat !

---

## 🌐 Déploiement du Site

Le dossier `site/` est totalement autonome et statique. Vous pouvez simplement :
- Le glisser-déposer sur [Netlify Drop](https://app.netlify.com/drop).
- L'envoyer sur **GitHub Pages**, **Vercel** ou tout hébergeur web classique.
