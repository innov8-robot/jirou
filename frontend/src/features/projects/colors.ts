/** Palette de couleurs proposée pour les projets (avatar/badge de clé). */
export const PROJECT_COLORS = [
  '#6D5AE6',
  '#3B82F6',
  '#0EA5E9',
  '#22C55E',
  '#F59E0B',
  '#EF4444',
  '#EC4899',
  '#8B5CF6',
] as const;

export const DEFAULT_PROJECT_COLOR = PROJECT_COLORS[0];

/** Suggère une clé (préfixe) à partir d'un nom : initiales, 2-5 lettres. */
export function suggestKey(name: string): string {
  const words = name
    .toUpperCase()
    .replace(/[^A-Z0-9\s]/g, '')
    .split(/\s+/)
    .filter(Boolean);

  let key = '';
  if (words.length >= 2) {
    key = words.map((w) => w[0]).join('');
  } else if (words.length === 1) {
    key = words[0].slice(0, 4);
  }
  key = key.replace(/[^A-Z0-9]/g, '').slice(0, 5);
  // La clé doit commencer par une lettre et faire au moins 2 caractères.
  if (key.length < 2) key = (key + 'PRJ').slice(0, 3);
  if (!/^[A-Z]/.test(key)) key = 'P' + key.slice(0, 4);
  return key;
}
