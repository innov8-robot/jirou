import { useEffect, useRef, useState } from 'react';

/** Lit la valeur stockée sous `key`, ou `fallback` si absente/illisible. */
function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

/**
 * État React persisté dans le localStorage (JIR-46).
 *
 * Un changement de `key` recharge l'état depuis la nouvelle clé au lieu d'y
 * réécrire l'ancienne valeur : indispensable pour les préférences indexées par
 * projet (`jirou.issues.{id}`, `jirou.board.{id}`), la page restant montée
 * quand on passe d'un projet à l'autre.
 */
export function usePersistedState<T>(key: string, initial: T) {
  // Refs : la valeur initiale et la clé précédente ne doivent pas relancer l'effet.
  const initialRef = useRef(initial);
  const keyRef = useRef(key);
  const [value, setValue] = useState<T>(() => read(key, initialRef.current));

  useEffect(() => {
    if (keyRef.current !== key) {
      keyRef.current = key;
      setValue(read(key, initialRef.current));
      return;
    }
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* localStorage indisponible : on garde l'état en mémoire. */
    }
  }, [key, value]);

  return [value, setValue] as const;
}
