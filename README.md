# Calyps'HOME (Avidsen Cloud) pour Home Assistant

[English](README.md) | **Français**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=akoonet-homeassistant&repository=Calypshome-ha&category=integration)
[![GitHub release](https://img.shields.io/github/v/release/akoonet-homeassistant/Calypshome-ha?display_name=tag)](https://github.com/akoonet-homeassistant/Calypshome-ha/releases)
[![License](https://img.shields.io/github/license/akoonet-homeassistant/Calypshome-ha)](LICENSE)

Intégration personnalisée (custom component) permettant de piloter des **volets roulants Profalux Neosol 868** depuis Home Assistant via le cloud **Calyps'HOME / Avidsen**, avec les mêmes identifiants que l'application mobile.

Le cloud Avidsen ne renvoie pas la position réelle des volets : l'intégration **estime la position par minuterie** (temps de course configurable par volet), ce qui permet malgré tout d'exposer des entités `cover` avec position en pourcentage et commande à position précise.

| | |
|---|---|
| **Domaine** | `calypshome` |
| **Classe IoT** | `cloud_polling` |
| **Configuration** | Interface (config flow), aucun YAML requis |
| **Matériel visé** | Volets `Rolling_Shutter_Profalux` (Neosol 868) |
| **Langues** | Français, Anglais |

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Captures d'écran](#captures-décran)
- [Entités créées](#entités-créées-par-volet)
- [Installation](#installation)
- [Configuration](#configuration)
- [Fonctionnement de l'estimation de position](#fonctionnement-de-lestimation-de-position)
- [Structure du dépôt](#structure-du-dépôt)
- [Limitations connues](#limitations-connues)
- [Dépannage](#dépannage)
- [Contribuer](#contribuer)
- [Licence](#licence)

---

## Fonctionnalités

- Découverte automatique des volets du compte (les objets masqués sont ignorés).
- Entité `cover` par volet avec **Ouvrir / Fermer / Stop** et **positionnement précis** (0–100 %).
- Estimation de position par temps de course, avec envoi automatique d'un `STOP` à l'arrivée sur une position intermédiaire.
- **Bouton « position favorite »** (`FAV_CALL_1`) pour rappeler la position mémorisée dans le moteur, créé uniquement si le volet la supporte.
- **Curseurs de réglage** par volet : temps de montée, temps de descente, et pourcentage correspondant à la position favorite.
- Interface entièrement **traduite (français / anglais)**, noms d'entités inclus.
- Restauration de la dernière position estimée et des réglages après un redémarrage de Home Assistant.
- Gestion du token JWT (~6 h) avec rafraîchissement automatique et re-login transparent sur expiration.

---

## Captures d'écran

**Volets découverts dans l'intégration** — un appareil par volet, avec ses entités :

<p align="center">
  <img src="images/integration-devices.png" width="80%" alt="Liste des volets découverts par l'intégration Calyps'HOME">
</p>

**Détail d'un volet** — contrôles (ouverture / stop / fermeture, position favorite), réglage des temps de course et historique d'activité :

<p align="center">
  <img src="images/device-detail.png" width="90%" alt="Page d'un volet : contrôles, configuration des temps et activité">
</p>

---

## Entités créées par volet

Les noms sont **localisés selon la langue de Home Assistant** (exemples en français ci-dessous).

| Entité | Type | Rôle |
|--------|------|------|
| `<volet>` | Cover | Pilotage ouverture / fermeture / stop / position |
| `<volet> Position favorite` | Button | Rappel de la position favorite du moteur (`FAV_CALL_1`) |
| `<volet> Temps de montée` | Number (3–120 s) | Temps de course complet à la montée (estimation de position) |
| `<volet> Temps de descente` | Number (3–120 s) | Temps de course complet à la descente |
| `<volet> Position favorite (%)` | Number (0–100 %) | Pourcentage attribué à la position favorite pour recaler l'estimation |

Le bouton et le curseur « position favorite » ne sont créés que pour les volets exposant l'action `FAV_CALL_1`. Toutes ces entités sont regroupées sous un même appareil (`manufacturer` : Profalux / Avidsen, `model` : Volet Neosol 868).

---

## Installation

### Via HACS (recommandé)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=akoonet-homeassistant&repository=Calypshome-ha&category=integration)

Ou manuellement :

1. HACS → menu ⋮ → **Dépôts personnalisés**.
2. Ajouter l'URL `https://github.com/akoonet-homeassistant/Calypshome-ha`, catégorie **Integration**.
3. Rechercher **Calyps'HOME**, installer, puis **redémarrer Home Assistant**.

### Installation manuelle

1. Copier le dossier `custom_components/calypshome` dans le répertoire `custom_components` de votre configuration Home Assistant.
2. Redémarrer Home Assistant.

---

## Configuration

1. **Paramètres → Appareils et services → Ajouter une intégration**.
2. Rechercher **Calyps'HOME**.
3. Saisir l'**email** et le **mot de passe** de votre compte Calyps'HOME (identiques à ceux de l'application mobile).

<p align="center">
  <img src="images/config-flow.png" width="60%" alt="Écran de connexion Calyps'HOME">
</p>

Un compte ne peut être configuré qu'une seule fois. Les volets sont ensuite créés automatiquement.

### Réglage des temps de course

Le fonctionnement en position repose entièrement sur les **temps de course**. Pour chaque volet :

1. Mesurer au chronomètre le temps d'une **montée complète** et d'une **descente complète**.
2. Reporter ces valeurs dans les curseurs `Temps de montée` / `Temps de descente` du volet.

Plus la mesure est précise, plus l'estimation de position sera fiable. Un menu **Options** hérité permet aussi de saisir ces temps, mais les curseurs `number` sont la méthode recommandée (prise en compte dynamique, sans rechargement).

### Position favorite

Le curseur `Position favorite (%)` indique à quel pourcentage correspond la position mémorisée dans le moteur. Lors d'un appui sur le bouton favori, le volet rejoint sa position matérielle et l'estimation Home Assistant est recalée sur cette valeur.

---

## Fonctionnement de l'estimation de position

Le cloud Avidsen n'expose pas de retour de position. À chaque commande, l'intégration :

1. envoie l'action (`OPEN`, `CLOSE`, `STOP`, `FAV_CALL_1`) ;
2. démarre un minuteur (tick de 1 s) qui interpole la position à partir du temps de course configuré ;
3. envoie un `STOP` automatique lorsque la cible est une position intermédiaire.

En conséquence, la position affichée est une **estimation**. Une désynchronisation peut survenir après une commande émise en dehors de Home Assistant (télécommande physique, application mobile) ou après une coupure moteur. Une ouverture ou fermeture complète permet de recaler l'estimation.

---

## Structure du dépôt

```
Calypshome-ha/
├── custom_components/
│   └── calypshome/
│       ├── __init__.py
│       ├── api.py
│       ├── button.py
│       ├── config_flow.py
│       ├── const.py
│       ├── cover.py
│       ├── number.py
│       ├── manifest.json
│       ├── strings.json
│       └── translations/
│           ├── en.json
│           └── fr.json
├── images/
│   ├── config-flow.png
│   ├── device-detail.png
│   └── integration-devices.png
├── .gitignore
├── hacs.json
├── LICENSE
├── README.md          (anglais)
└── README.fr.md       (français)
```

---

## Limitations connues

- **Position estimée, non mesurée** : dépend de la justesse des temps de course et peut dériver si le volet est piloté par un autre moyen.
- **Cloud uniquement** : nécessite l'accès aux serveurs Avidsen ; pas de pilotage local.
- **Limite d'appareils Avidsen** : le compte est associé à un nombre restreint d'appareils (erreur `too_much_mobiles`).

> **À propos de l'identifiant d'appareil**
> Home Assistant s'enregistre auprès d'Avidsen avec un `deviceID` **stable, dérivé du login** (généré via `uuid5`). Il reste identique à chaque redémarrage, ce qui évite de créer un nouvel appareil à chaque démarrage et de déclencher l'erreur `too_much_mobiles`. Aucun identifiant matériel personnel n'est utilisé ni stocké.

---

## Dépannage

- **« Identifiants invalides »** : vérifier email / mot de passe dans l'application mobile Calyps'HOME.
- **« Impossible de contacter le serveur »** : problème réseau ou indisponibilité du cloud Avidsen.
- **Erreur `too_much_mobiles`** : limite d'appareils atteinte côté Avidsen ; supprimer un appareil inutilisé depuis l'application mobile, ou contacter le support, puis recharger l'intégration.
- **Position incohérente** : lancer une ouverture ou fermeture complète pour recaler l'estimation, et affiner les temps de course.

Pour des logs détaillés, ajouter dans `configuration.yaml` :

```yaml
logger:
  logs:
    custom_components.calypshome: debug
```

---

## Contribuer

Les issues et pull requests sont les bienvenues. Merci de décrire votre modèle de volet et le comportement observé (logs en niveau `debug` si possible).

---

## Licence

Distribué sous licence [MIT](LICENSE).

Projet non affilié à Avidsen ni à Profalux. Utilisation à vos propres risques ; l'API cloud est non documentée et peut évoluer sans préavis.
