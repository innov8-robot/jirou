# Serveur MCP Jirou

Donne à Claude Code un accès en lecture/écriture à Jirou pendant une session de
code : créer le ticket d'un bug qu'on vient de trouver, passer un ticket en
`in_review` quand la PR part, consigner une recherche technique dans la veille.

Dans les deux modes, l'identifiant est un **jeton d'API personnel** Jirou
(`jir_pat_…`) — pas de second secret à gérer.

## Deux modes, selon où tourne votre Claude Code

**stdio** — client et serveur sur la même machine. Claude Code lance le serveur
lui-même ; le jeton vient de son environnement.

```
Claude Code ──stdio(MCP)──▶ jirou-mcp ──▶ API Jirou
```

**HTTP** — le serveur tourne en service sur le VPS, le client est ailleurs (votre
poste). Chaque requête porte le jeton dans `Authorization: Bearer`.

```
Claude Code (poste) ──HTTPS──▶ Caddy ──▶ jirou-mcp-http (127.0.0.1:8012) ──▶ API Jirou
```

Le mode HTTP est décrit [plus bas](#mode-http--serveur-distant). Les sections qui
suivent (jeton, outils) valent pour les deux.

## 1. Créer un jeton

Dans Jirou : **Mon profil → Jetons d'API → Créer**. Le secret n'est affiché
qu'une fois — copiez-le tout de suite.

Le jeton porte **exactement vos droits** ; il ne peut ni changer votre mot de
passe ni créer d'autres jetons. Révocable à tout moment depuis le même écran.

## 2. Installer

```bash
cd mcp-server
python -m venv .venv && .venv/bin/pip install -e .
```

La commande `jirou-mcp` est alors dans `.venv/bin/`.

## 3. Déclarer le serveur à Claude Code

Deux emplacements possibles :

- `~/.claude.json` — disponible dans tous vos projets ;
- `.mcp.json` à la racine d'un dépôt — partagé avec l'équipe (⚠️ **ne committez
  pas un jeton** : voir la variante `${VAR}` plus bas).

```json
{
  "mcpServers": {
    "jirou": {
      "command": "/root/jirou/mcp-server/.venv/bin/jirou-mcp",
      "env": {
        "JIROU_API_URL": "https://api.jirou.innov9.fr",
        "JIROU_TOKEN": "jir_pat_votre-jeton-ici"
      }
    }
  }
}
```

Pour un `.mcp.json` committé, laissez le jeton hors du fichier — Claude Code
substitue les variables d'environnement :

```json
{
  "mcpServers": {
    "jirou": {
      "command": "jirou-mcp",
      "env": {
        "JIROU_API_URL": "https://api.jirou.innov9.fr",
        "JIROU_TOKEN": "${JIROU_TOKEN}"
      }
    }
  }
}
```

En développement local, `JIROU_API_URL` vaut `http://localhost:8010` (cf.
[docs/CONVENTIONS.md](../docs/CONVENTIONS.md)).

Vérifiez avec `/mcp` dans Claude Code : le serveur `jirou` doit apparaître
connecté, avec ses 18 outils.

## Outils exposés

Tout se désigne comme un humain le ferait : projet par sa clé (`JIR`), ticket par
sa clé (`JIR-42`), personne par son e-mail, sprint par son nom (ou `active`). Le
serveur traduit vers les identifiants numériques de l'API.

| Outil | Rôle |
|---|---|
| `jirou_list_projects` | Projets accessibles, avec leur clé |
| `jirou_search_issues` | Tickets filtrés (statut, type, assigné, sprint, epic, texte) |
| `jirou_get_issue` | Détail d'un ticket, description incluse |
| `jirou_create_issue` | Créer un ticket |
| `jirou_update_issue` | Statut, priorité, assigné, points, epic, labels, dates |
| `jirou_list_comments` / `jirou_add_comment` | Fil de discussion d'un ticket |
| `jirou_list_sprints` / `jirou_get_backlog` | Sprints et contenu du backlog |
| `jirou_move_issue_to_sprint` | Déplacer entre backlog et sprint |
| `jirou_list_watch_nodes` / `jirou_get_watch_node` | Lire l'arbre de veille R&D |
| `jirou_create_watch_node` / `jirou_update_watch_node` | Consigner une recherche |
| `jirou_list_documents` / `jirou_get_document` | Lire les docs projet et généraux |
| `jirou_create_document` / `jirou_update_document` | Écrire une note, une procédure |

**Aucun outil de suppression n'est exposé** : l'agent peut créer, corriger et
commenter, pas effacer le travail de quelqu'un. Les suppressions restent dans
l'interface web.

Deux commodités qui évitent des allers-retours : un label inconnu est **créé à la
volée** (comme à l'import CSV), et un identifiant qui ne correspond à rien
produit une erreur qui **liste les valeurs valides** — l'agent se corrige seul au
lieu d'abandonner.

## Exemples d'usage

> « Le test `test_export_respects_filters` échoue en CI. Crée un bug dans JIR
> assigné à moi, priorité high, label `ci`. »

> « Passe JIR-42 en in_review et commente avec le hash du commit. »

> « Qu'est-ce qu'il reste dans le sprint actif de JIR ? »

> « J'ai comparé trois libs d'export XLSX. Consigne-le dans la veille sous le
> thème Export, avec la conclusion. »

## Mode HTTP — serveur distant

Utile quand Claude Code tourne sur votre poste et Jirou sur le VPS. Le serveur
est un service systemd derrière Caddy.

### Le modèle d'authentification

**Le serveur n'a aucun jeton à lui.** Chaque requête doit porter celui de son
auteur, vérifié auprès de `/auth/me` avant qu'un outil ne s'exécute. Trois
conséquences voulues :

- pas de second secret à gérer, faire tourner ou fuiter ;
- **aucune identité par défaut à voler** : une requête non authentifiée ne peut
  rien lire, ce qui rend l'exposition publique acceptable ;
- révocation immédiate depuis l'interface Jirou, jeton par jeton.

`GET /healthz` répond sans authentification (sonde de vie), tout le reste exige
le jeton.

### Côté VPS

Service [`/etc/systemd/system/jirou-mcp.service`](/etc/systemd/system/jirou-mcp.service),
écoute sur `127.0.0.1:8012` — c'est Caddy qui termine le TLS :

```bash
systemctl status jirou-mcp
curl -s http://127.0.0.1:8012/healthz          # {"detail": "ok"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8012/mcp   # 401
```

Variables du service : `JIROU_API_URL` (obligatoire),
`JIROU_MCP_ALLOWED_HOSTS`, `JIROU_MCP_HOST`, `JIROU_MCP_PORT`. **Pas**
de `JIROU_TOKEN` — en HTTP le jeton vient du client.

> ⚠️ `JIROU_MCP_ALLOWED_HOSTS` doit contenir le nom public servi par le
> reverse-proxy. Le SDK MCP valide l'en-tête `Host` (protection
> anti-DNS-rebinding) et répond **421 Misdirected Request** à un hôte inconnu :
> sans cette variable, aucune requête proxifiée ne passe. La protection reste
> active à dessein — c'est elle qui empêche un site tiers de faire parler le
> service via le navigateur de la victime.

Bloc Caddy :

```caddy
mcp.jirou.innov9.fr {
	encode gzip zstd
	reverse_proxy 127.0.0.1:8012
}
```

### Côté poste

```bash
claude mcp add --transport http jirou https://mcp.jirou.innov9.fr/mcp \
  --header "Authorization: Bearer jir_pat_votre-jeton"
```

Sans DNS ni Caddy, un tunnel SSH suffit (`127.0.0.1` fait partie des hôtes
autorisés par défaut) :

```bash
ssh -N -L 8012:127.0.0.1:8012 root@le-vps
claude mcp add --transport http jirou http://127.0.0.1:8012/mcp \
  --header "Authorization: Bearer jir_pat_votre-jeton"
```

## Développement

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest        # 71 tests, appels HTTP simulés (respx)
.venv/bin/ruff check jirou_mcp tests
```

- [`jirou_mcp/client.py`](jirou_mcp/client.py) — transport HTTP et résolution
  des identifiants lisibles ;
- [`jirou_mcp/server.py`](jirou_mcp/server.py) — définition des outils. Les
  docstrings sont ce que le modèle lit pour choisir un outil : elles disent
  *quand* l'appeler, pas seulement ce qu'il fait ;
- [`jirou_mcp/http.py`](jirou_mcp/http.py) — transport HTTP et middleware
  d'authentification ;
- [`jirou_mcp/context.py`](jirou_mcp/context.py) — client de la requête en
  cours, partagé entre les deux précédents.

Le SDK utilisé est `mcp` **v2**, où la classe serveur s'appelle `MCPServer` (et
non `FastMCP` comme en v1) et les champs du protocole sont en `snake_case`
(`input_schema`, `structured_content`).
