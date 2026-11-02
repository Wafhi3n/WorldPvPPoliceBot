"""La pipeline de déploiement (tools/deploy.py) : sans réseau, devant un faux Coolify. Rien ne part si les tests échouent, et le
jeton ne sort nulle part : ni à l'écran, ni dans un message d'erreur."""

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tools import deploy as dp

TOKEN = "jeton-de-test-0123456789"
BASE = "http://coolify.test"
APP = {"uuid": "app1", "name": dp.REPO, "git_branch": "main", "status": "running:healthy",
       "git_repository": f"git@github.com:Wafhi3n/{dp.REPO}.git",
       "environment_variables": [{"key": "DISCORD_TOKEN", "value": "secret-discord"}]}
OTHER = {"uuid": "app2", "name": "autre", "git_repository": "Wafhi3n/autre"}


def fake_coolify(routes, seen=None):
    """`routes` = {(méthode, chemin): réponse | [réponses successives] | code HTTP d'erreur}."""
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout=None):
        path = req.full_url[len(BASE + "/api/v1"):]
        if seen is not None:
            seen.append((req.get_method(), path, req.get_header("Authorization")))
        answer = routes.get((req.get_method(), path), 404)
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, int):
            raise urllib.error.HTTPError(req.full_url, answer, "erreur", {}, None)
        return Resp(json.dumps(answer).encode("utf-8"))
    return opener


class Settings(unittest.TestCase):
    def test_url_par_defaut_et_jeton_lu(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".deploy.env"
            p.write_text(f"COOLIFY_TOKEN={TOKEN}\n", encoding="utf-8")
            with mock.patch.dict("os.environ", clear=True):
                conf = dp.settings(p)
        self.assertEqual((conf["url"], conf["token"], conf["uuid"]), (dp.DEFAULT_URL, TOKEN, ""))

    def test_sans_jeton_refuse(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", clear=True), self.assertRaises(SystemExit):
            dp.settings(Path(d) / "absent.env")


class Coolify(unittest.TestCase):
    def api(self, routes, seen=None):
        return dp.Api(BASE, TOKEN, fake_coolify(routes, seen))

    def test_appli_trouvee_par_le_depot_sans_afficher_ses_secrets(self):
        app = dp.find_app(self.api({("GET", "/applications"): [[OTHER, APP]]}), "")
        self.assertEqual(app["uuid"], "app1")
        self.assertNotIn("secret-discord", dp.describe(app))

    def test_deux_applis_du_meme_depot_refuse(self):
        with self.assertRaises(dp.CoolifyError):
            dp.find_app(self.api({("GET", "/applications"): [[APP, dict(APP, uuid="app3")]]}), "")

    def test_deploie_puis_attend_la_fin(self):
        seen = []
        api = self.api({("POST", "/deploy?uuid=app1&force=false"): {"deployments": [{"deployment_uuid": "d1"}]},
                        ("GET", "/deployments/d1"): [{"status": "queued", "commit": "abc1234ff"},
                                                     {"status": "finished", "commit": "abc1234ff"}]}, seen)
        out = io.StringIO()
        self.assertEqual(dp.start(api, "app1", False), "d1")
        self.assertTrue(dp.wait(api, "d1", out=out, sleep=lambda s: None))
        self.assertEqual(out.getvalue().count("abc1234"), 2, "un changement d'état = une ligne")
        self.assertEqual(seen[0][2], "Bearer " + TOKEN)

    def test_echec_du_deploiement(self):
        api = self.api({("GET", "/deployments/d1"): [{"status": "failed"}]})
        self.assertFalse(dp.wait(api, "d1", out=io.StringIO(), sleep=lambda s: None))

    def test_repli_sur_get_quand_post_refuse(self):
        api = self.api({("POST", "/deploy?uuid=app1&force=true"): 405,
                        ("GET", "/deploy?uuid=app1&force=true"): {"deployments": [{"deployment_uuid": "d2"}]}})
        self.assertEqual(dp.start(api, "app1", True), "d2")

    def test_jeton_refuse_sans_le_montrer(self):
        api = self.api({("GET", "/applications"): 401})
        with self.assertRaises(dp.CoolifyError) as e:
            dp.find_app(api, "")
        self.assertIn("401", str(e.exception))
        for text in (str(e.exception), repr(e.exception), repr(api)):
            self.assertNotIn(TOKEN, text)

    def test_coolify_injoignable(self):
        def down(req, timeout=None):
            raise urllib.error.URLError("connexion refusée")
        with self.assertRaises(dp.CoolifyError) as e:
            dp.find_app(dp.Api(BASE, TOKEN, down), "app1")
        self.assertIn("injoignable", str(e.exception))
        self.assertNotIn(TOKEN, str(e.exception))


class Ready(unittest.TestCase):
    def check(self, branch="main", dirty="", behind="0"):
        answers = {"branch": branch, "status": dirty, "fetch": "", "rev-list": behind}
        with mock.patch.object(dp, "git", side_effect=lambda *a: answers[a[0]]):
            dp.check_ready()

    def test_tout_va_bien(self):
        self.check()

    def test_une_autre_branche(self):
        with self.assertRaisesRegex(SystemExit, "Pas sur main"):
            self.check(branch="feat/x")

    def test_un_arbre_sale(self):
        with self.assertRaisesRegex(SystemExit, "non commitées"):
            self.check(dirty=" M bot/x.py")

    def test_github_en_avance(self):
        with self.assertRaisesRegex(SystemExit, "GitHub a des commits"):
            self.check(behind="2")

    def test_les_tests_en_echec(self):
        with mock.patch.object(dp.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaisesRegex(SystemExit, "rien n'est poussé"):
                dp.run_tests()

    def test_github_n_a_pas_le_commit(self):
        with mock.patch.object(dp.subprocess, "run"), mock.patch.object(dp, "git", side_effect=["aaa", "bbb refs/heads/main"]):
            with self.assertRaisesRegex(SystemExit, "rien n'est déployé"):
                dp.push_main()


class Order(unittest.TestCase):
    """L'ordre de la pipeline : rien ne part avant que tout soit vérifié."""

    def run_main(self, *argv, tests_fail=False):
        steps = []

        def step(name):
            return lambda *a, **k: steps.append(name)

        def tests():
            steps.append("tests")
            if tests_fail:
                raise SystemExit("Tests en échec")

        def push():
            steps.append("push")
            return "abc1234"

        def start(*a):
            steps.append("deploy")
            return "d1"

        def wait(*a):
            steps.append("wait")
            return True
        with mock.patch.multiple(dp, settings=lambda: {"url": BASE, "token": TOKEN, "uuid": "app1"},
                                 find_app=lambda *a: APP, check_ready=step("ready"), run_tests=tests, push_main=push,
                                 start=start, wait=wait), mock.patch("builtins.print"):
            try:
                dp.main(list(argv))
            except SystemExit:
                pass
        return steps

    def test_verifier_puis_tester_puis_pousser_puis_deployer(self):
        self.assertEqual(self.run_main(), ["ready", "tests", "push", "deploy", "wait"])

    def test_des_tests_en_echec_ne_poussent_rien(self):
        self.assertEqual(self.run_main(tests_fail=True), ["ready", "tests"])

    def test_verifier_seul_ne_touche_a_rien(self):
        self.assertEqual(self.run_main("--verifier"), [])

    def test_sans_attendre(self):
        self.assertEqual(self.run_main("--sans-attendre"), ["ready", "tests", "push", "deploy"])


if __name__ == "__main__":
    unittest.main()
