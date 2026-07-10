import { useEffect, useState } from 'react';

/** État React persisté dans le localStorage (JIR-46). */
export function usePersistedState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* localStorage indisponible : on garde l'état en mémoire. */
    }
  }, [key, value]);

  return [value, setValue] as const;
}
