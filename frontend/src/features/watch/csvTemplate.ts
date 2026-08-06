import { saveBlob } from '@/lib/download';

/** En-tête attendu par `POST /watch/nodes/{id}/import`. */
export const CSV_HEADER = 'title,parent,type,status,note,links';

/** Modèle téléchargeable : montre la hiérarchie, les liens et une note. */
export const CSV_TEMPLATE = `${CSV_HEADER}
Xsens MTw Awinda,,techno,promising,"Précision excellente. Licence annuelle chère.","https://www.xsens.com;https://youtu.be/demo"
Tarifs Xsens,Xsens MTw Awinda,resource,,"Devis 2026 : ~12k€ pour 17 capteurs.",
Rokoko Smartsuit Pro,,techno,to_test,"5x moins cher, dérive plus forte sur les jambes.","https://rokoko.com"
Drift sur marche longue,Rokoko Smartsuit Pro,resource,abandoned,"Test 20 min : dérive ~15cm.",
`;

/** Déclenche le téléchargement du modèle CSV. */
export function downloadWatchCsvTemplate(): void {
  // BOM UTF-8 : Excel affiche alors correctement les accents.
  const blob = new Blob(['﻿' + CSV_TEMPLATE], {
    type: 'text/csv;charset=utf-8',
  });
  saveBlob(blob, 'veille-modele.csv');
}

/**
 * Consigne à donner à une IA pour qu'elle produise le CSV.
 *
 * Écrite pour être collée telle quelle devant une demande de recherche. Elle
 * insiste sur les points où un LLM se trompe en pratique : inventer des colonnes,
 * référencer un parent par un identifiant plutôt que par un titre, oublier les
 * guillemets autour d'une note contenant une virgule, ou produire du texte
 * autour du CSV.
 */
export const AI_PROMPT = `Produis un fichier CSV décrivant ce que tu as trouvé, destiné à être importé dans mon outil de veille technique sous un nœud existant.

Format — respecte-le à la lettre :
- Première ligne exactement : ${CSV_HEADER}
- Une ligne par élément. N'ajoute aucune colonne, n'en retire aucune.
- title : intitulé court et concret (nom du produit, de la techno, de la source). Obligatoire, et unique dans le fichier.
- parent : laisse VIDE pour un élément de premier niveau. Sinon, recopie à l'identique le "title" d'une AUTRE ligne du fichier. N'utilise jamais un numéro ou un identifiant.
- type : un seul de theme | techno | solution | resource. "techno" pour une technologie ou un produit, "solution" pour une approche, "resource" pour une source ou une donnée, "theme" pour un regroupement.
- status : un seul de to_test | in_progress | promising | abandoned, ou vide si tu ne sais pas.
- note : en Markdown, 1 à 5 phrases utiles — ce qui aide à décider (prix, limites mesurées, contraintes, verdict). Pas de remplissage.
- links : URLs séparées par des points-virgules, ou vide. Uniquement des URLs que tu as réellement consultées.

Règles CSV :
- Encadre de guillemets doubles tout champ contenant une virgule, un point-virgule, un retour à la ligne ou un guillemet ; double les guillemets internes ("").
- Pas de ligne vide, pas de commentaire, pas de numérotation.

Ta réponse doit contenir UNIQUEMENT le CSV, sans texte avant ni après, sans bloc de code.

Sujet à documenter : `;
