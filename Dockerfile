# World PvP Police Bot dans un conteneur, pour un serveur toujours allumé (Coolify, Docker, ou à la main).
# Ce que l'image NE contient PAS : le jeton (passé par l'environnement, jamais copié : .dockerignore),
# ni aucune image du jeu (les cartes de zone se téléchargent à la demande sur wago.tools, dans /app/state).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_LOG=/app/state/bot.log \
    BOT_STATE=/app/state \
    TZ=Europe/Paris

# Incident eMudhra/emSign (2026-10-20, discuss.python.org/t/109576) : la racine « emSign ECC Root
# CA - G3 » ne doit plus être crue. aiohttp (donc discord.py) croit le magasin Debian de l'image :
# on prend son ca-certificates corrigé, par apt (dépôts signés, sûr même avant le correctif).
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Le pip de l'image croit toujours son certifi embarqué : il faut pip ≥ 26.2.2, tiré par son
# empreinte (vérifiée sur PyPI le 2026-10-22) pour ne pas dépendre du pip d'avant pour ce téléchargement.
RUN pip install --no-cache-dir --disable-pip-version-check \
    "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

# Un utilisateur sans droits ; /app/state est le volume du journal et du cache des cartes.
RUN useradd --create-home --uid 10001 bot && mkdir -p /app/state && chown bot:bot /app/state
USER bot
VOLUME ["/app/state"]

CMD ["python", "-m", "bot"]
