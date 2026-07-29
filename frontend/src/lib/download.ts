/**
 * Téléchargement de fichiers côté navigateur.
 *
 * Mutualise la plomberie partagée par les exports (CSV des tickets, archive de
 * veille) et les modèles téléchargeables : lecture du nom proposé par le serveur
 * et déclenchement de l'enregistrement via un lien temporaire.
 */

/**
 * Nom de fichier porté par un en-tête `Content-Disposition`, ou `null`.
 *
 * L'API étant sur une autre origine que le front, cet en-tête n'est lisible que
 * parce que le backend l'expose (`expose_headers` du middleware CORS) ; prévoir
 * malgré tout un nom de repli à l'appel.
 */
export function filenameFromDisposition(
  disposition?: string | null
): string | null {
  const match = /filename="?([^"]+)"?/.exec(disposition ?? '');
  return match?.[1] ?? null;
}

/** Déclenche l'enregistrement de `blob` sous le nom `filename`. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
