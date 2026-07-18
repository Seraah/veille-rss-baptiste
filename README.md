# La Veille RSS de Baptiste — kit GitHub Pages

Ce kit agrège automatiquement **232 flux RSS complets** extraits du catalogue PDF,
puis publie :

- `index.html` : interface lisible et filtrable ;
- `articles.json` : corpus structuré exploitable par une IA ou un script ;
- `status.json` : état détaillé de chaque flux ;
- `feeds.opml` : export réutilisable dans un autre lecteur RSS.

## Installation la plus simple

### 1. Créer le dépôt

1. Créez un compte gratuit sur GitHub si nécessaire.
2. Cliquez sur **New repository**.
3. Nom conseillé : `veille-rss-baptiste`.
4. Choisissez **Public**.
5. Ne cochez pas l'ajout automatique d'un README.
6. Cliquez sur **Create repository**.

### 2. Envoyer les fichiers

1. Décompressez le ZIP.
2. Dans le dépôt vide, cliquez sur **uploading an existing file**.
3. Déposez tous les fichiers et dossiers contenus dans ce kit, y compris le dossier `.github`.
4. Validez avec **Commit changes**.

Si le navigateur ne conserve pas le dossier `.github`, utilisez GitHub Desktop :
créez/clonez le dépôt, copiez le contenu du kit dans le dossier local, puis cliquez sur
**Commit to main** et **Push origin**.

### 3. Activer GitHub Pages

1. Ouvrez **Settings** dans le dépôt.
2. Dans la colonne de gauche, cliquez sur **Pages**.
3. Sous **Build and deployment**, sélectionnez **GitHub Actions** comme source.

### 4. Lancer la première mise à jour

1. Ouvrez l'onglet **Actions**.
2. Sélectionnez **Mettre à jour la veille RSS**.
3. Cliquez sur **Run workflow**, puis confirmez.
4. Attendez généralement deux à cinq minutes.

L'adresse prendra cette forme :

`https://VOTRE-NOM-GITHUB.github.io/veille-rss-baptiste/`

Le fichier structuré sera disponible ici :

`https://VOTRE-NOM-GITHUB.github.io/veille-rss-baptiste/articles.json`

## Fonctionnement

La mise à jour est programmée à **5 h 37, 11 h 37, 17 h 37 et 23 h 37,
heure de Paris**. Le décalage été/hiver est géré par GitHub.

Le script :

- télécharge les flux en parallèle ;
- garde les articles des dix derniers jours ;
- déduplique les liens ;
- tronque les résumés à 500 caractères ;
- publie un tableau de bord avec recherche et filtres ;
- indique les flux qui échouent.

GitHub désactive normalement les workflows programmés d'un dépôt public sans activité
pendant 60 jours. Ce kit crée automatiquement un petit commit de maintien tous les
30 jours pour éviter cela.

## Modifier les sources

Ouvrez `feeds.csv`. Chaque ligne contient :

`category,source,url`

Vous pouvez supprimer ou ajouter des lignes. Ne mettez aucun identifiant, cookie,
mot de passe ou URL privée dans ce dépôt public.

## Modifier la fréquence

Ouvrez `.github/workflows/update-rss.yml` et changez :

```yaml
- cron: "37 5,11,17,23 * * *"
  timezone: "Europe/Paris"
```

## Confidentialité et droits

Le dépôt et le site sont publics. Le tableau de bord ne publie que les titres,
métadonnées et courts extraits présents dans les flux, avec un lien vers l'article original.
Un fichier `robots.txt` et une balise `noindex` demandent aux moteurs de ne pas indexer le site,
mais cela ne le rend pas privé.

N'ajoutez pas de flux privés, de jetons RSS.app confidentiels ou de contenus internes.
