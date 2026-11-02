"""La pipeline de déploiement, depuis le PC : vérifie `main`, lance les tests, pousse sur GitHub, demande à Coolify de reconstruire,
et attend la fin. Le bot republie ensuite ses guides tout seul, à son démarrage.

Depuis le PC, parce que GitHub ne joint pas Coolify (port 8000 fermé vers Internet, on n'ouvre rien) : le PC est sur le réseau du
serveur, et appelle l'API de Coolify lui-même. Repris de tools/redeploy.py de CraftingOrderBot.

Réglages dans `.deploy.env` (jamais versionné, modèle `.deploy.env.example`), le jeton tapé par le user :
  COOLIFY_TOKEN     permissions « read » + « deploy » SEULEMENT : « root » et « read:sensitive » liraient
                    le jeton Discord rangé dans Coolify
  COOLIFY_URL       défaut http://192.168.5.213:8000 (le serveur sur le réseau local)
  COOLIFY_APP_UUID  facultatif : sinon l'appli est cherchée par le nom du dépôt
Le jeton n'est jamais affiché : on n'imprime que des champs choisis, jamais une réponse brute.

Usage : python tools/deploy.py [--verifier] [--force] [--sans-attendre]
  --verifier       lit seulement l'appli (prouve le jeton), ne teste, ne pousse ni ne déploie rien
  --force          reconstruit sans le cache Docker
  --sans-attendre  rend la main dès que le déploiement est en file
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bot.config import _read_env  # noqa: E402

SETTINGS = ROOT / ".deploy.env"
DEFAULT_URL = "http://192.168.5.213:8000"
REPO = "worldpvppolicebot"           # cherché dans git_repository quand COOLIFY_APP_UUID manque
DONE, FAILED = "finished", ("failed", "cancelled-by-user")
HINTS = {401: " (jeton refusé : mal copié ou révoqué)",
         403: " (permission manquante : le jeton veut « read » + « deploy »)",
         404: " (introuvable : vérifier COOLIFY_APP_UUID)"}


class CoolifyError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def settings(path: Path = SETTINGS) -> dict[str, str]:
    values = _read_env(path)
    values.update({k: v for k, v in os.environ.items() if k.startswith("COOLIFY_")})
    if not values.get("COOLIFY_TOKEN"):
        raise SystemExit(f"COOLIFY_TOKEN manquant : le taper dans {path.name} (voir .deploy.env.example).")
    return {"url": (values.get("COOLIFY_URL") or DEFAULT_URL).rstrip("/"),
            "token": values["COOLIFY_TOKEN"], "uuid": values.get("COOLIFY_APP_UUID", "").strip()}


class Api:
    def __init__(self, base: str, token: str, opener=urllib.request.urlopen):
        self.base, self._token, self._open = base, token, opener

    def __repr__(self) -> str:          # jamais le jeton dans une trace
        return f"Api({self.base!r})"

    def call(self, method: str, path: str):
        req = urllib.request.Request(self.base + "/api/v1" + path, method=method,
                                     headers={"Authorization": "Bearer " + self._token,
                                              "Accept": "application/json"})
        try:
            with self._open(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as e:
            raise CoolifyError(f"{method} {path} : HTTP {e.code}{HINTS.get(e.code, '')}", e.code) from None
        except urllib.error.URLError as e:
            raise CoolifyError(f"Coolify injoignable ({self.base}) : {e.reason}") from None


def describe(app: dict) -> str:
    """Les seuls champs d'une appli qu'on affiche : une réponse de Coolify peut porter des secrets."""
    return (f"{app.get('name')} (uuid {app.get('uuid')}, branche {app.get('git_branch')}, "
            f"état {app.get('status')})")


def find_app(api: Api, uuid: str) -> dict:
    if uuid:
        return api.call("GET", f"/applications/{quote(uuid)}")
    apps = api.call("GET", "/applications") or []
    found = [a for a in apps if REPO in (a.get("git_repository") or "").lower()]
    if len(found) != 1:
        names = ", ".join(describe(a) for a in found) or "aucune"
        raise CoolifyError(f"{len(found)} appli(s) pour le dépôt ({names}) : mettre COOLIFY_APP_UUID")
    return found[0]


def start(api: Api, uuid: str, force: bool) -> str:
    path = f"/deploy?uuid={quote(uuid)}&force={'true' if force else 'false'}"
    try:
        data = api.call("POST", path)
    except CoolifyError as e:
        if e.code != 405:
            raise
        data = api.call("GET", path)      # versions de Coolify où /deploy n'accepte que GET
    deployments = (data or {}).get("deployments") or []
    if not deployments or not deployments[0].get("deployment_uuid"):
        raise CoolifyError("Coolify n'a mis aucun déploiement en file")
    return deployments[0]["deployment_uuid"]


def wait(api: Api, deployment: str, out=sys.stdout, sleep=time.sleep, poll=5.0, timeout=900.0) -> bool:
    last, waited = None, 0.0
    while waited <= timeout:
        d = api.call("GET", f"/deployments/{quote(deployment)}") or {}
        status = d.get("status")
        if status != last:
            print(f"  {status}  (commit {str(d.get('commit') or '?')[:7]})", file=out, flush=True)
            last = status
        if status == DONE:
            return True
        if status in FAILED:
            return False
        sleep(poll)
        waited += poll
    print(f"  toujours « {last} » après {int(timeout)} s : voir les logs dans Coolify", file=out)
    return False


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def check_ready() -> None:
    """Refuse ce que Coolify ne verrait pas : une autre branche, un arbre sale ; et ce qu'on écraserait : GitHub en avance."""
    if git("branch", "--show-current") != "main":
        raise SystemExit("Pas sur main : Coolify construit main, fusionner d'abord.")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("Modifications non commitées : Coolify ne les verrait pas.")
    git("fetch", "origin", "main")
    if git("rev-list", "--count", "HEAD..origin/main") != "0":
        raise SystemExit("GitHub a des commits que ce PC n'a pas : rien n'est déployé.")


def run_tests() -> None:
    """Le garde-fou des guides compris : une commande sans son guide n'arrive pas jusqu'au Discord."""
    tests = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT)
    if tests.returncode != 0:
        raise SystemExit("Tests en échec : rien n'est poussé ni déployé.")


def push_main() -> str:
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    head = git("rev-parse", "HEAD")
    remote = git("ls-remote", "origin", "refs/heads/main").split()[:1]
    if remote != [head]:
        raise SystemExit(f"GitHub n'a pas main à {head[:7]} : rien n'est déployé.")
    return head


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sans-attendre", action="store_true")
    a = ap.parse_args(argv)
    conf = settings()
    api = Api(conf["url"], conf["token"])
    try:
        app = find_app(api, conf["uuid"])
        print("appli :", describe(app))
        if a.verifier:
            return
        check_ready()
        run_tests()
        head = push_main()
        deployment = start(api, app["uuid"], a.force)
        print(f"déploiement {deployment} en file pour {head[:7]}")
        if not a.sans_attendre and not wait(api, deployment):
            raise SystemExit("Déploiement en échec : voir ses logs dans Coolify.")
    except CoolifyError as e:
        raise SystemExit(str(e)) from None


if __name__ == "__main__":
    main()
