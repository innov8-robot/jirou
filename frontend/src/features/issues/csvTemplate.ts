/** Modèle CSV d'import de tickets (entête + exemples). */
export const CSV_HEADER =
  'type,summary,description,priority,story_points,status,labels,assignee_email,epic_key';

export const CSV_TEMPLATE = `${CSV_HEADER}
epic,Authentification,Gérer les comptes utilisateurs,high,,todo,auth,,
story,Écran de connexion,Formulaire email + mot de passe,high,5,todo,auth;frontend,,Authentification
task,Endpoint /login,JWT access + refresh,medium,3,in_progress,backend,,Authentification
bug,Le bouton ne répond pas,,highest,2,todo,frontend,,Authentification
`;

/** Déclenche le téléchargement du modèle CSV. */
export function downloadCsvTemplate(): void {
  const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'jirou-import-modele.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
