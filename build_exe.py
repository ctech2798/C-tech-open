import PyInstaller.__main__
from pathlib import Path

BASE = Path(__file__).parent

params = [
    str(BASE / "lancer.py"),
    "--name=ClubProjets",
    "--onefile",
    "--windowed",
    "--collect-all=uvicorn",
    "--collect-all=fastapi",
    "--collect-all=starlette",
    "--collect-all=pydantic",
    "--collect-all=googleapiclient",
    "--clean",
    "-y"
]

print("Démarrage de la compilation en .exe...")
PyInstaller.__main__.run(params)
print("Compilation terminée avec succès.")
