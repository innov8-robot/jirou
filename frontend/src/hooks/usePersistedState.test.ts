import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { usePersistedState } from '@/hooks/usePersistedState';

const DEFAULTS = { type: 'all', search: '' };

describe('usePersistedState', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts from the initial value when nothing is stored', () => {
    const { result } = renderHook(() =>
      usePersistedState('jirou.issues.1', DEFAULTS)
    );
    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('reads the stored value on mount', () => {
    localStorage.setItem(
      'jirou.issues.1',
      JSON.stringify({ type: 'bug', search: 'login' })
    );
    const { result } = renderHook(() =>
      usePersistedState('jirou.issues.1', DEFAULTS)
    );
    expect(result.current[0]).toEqual({ type: 'bug', search: 'login' });
  });

  it('persists updates to localStorage', () => {
    const { result } = renderHook(() =>
      usePersistedState('jirou.issues.1', DEFAULTS)
    );
    act(() => result.current[1]({ type: 'story', search: 'ci' }));
    expect(JSON.parse(localStorage.getItem('jirou.issues.1')!)).toEqual({
      type: 'story',
      search: 'ci',
    });
  });

  it('falls back to the initial value when the stored JSON is corrupt', () => {
    localStorage.setItem('jirou.issues.1', '{ pas du json');
    const { result } = renderHook(() =>
      usePersistedState('jirou.issues.1', DEFAULTS)
    );
    expect(result.current[0]).toEqual(DEFAULTS);
  });

  it('reloads from the new key instead of overwriting it (autre projet)', () => {
    localStorage.setItem(
      'jirou.issues.2',
      JSON.stringify({ type: 'epic', search: '' })
    );
    const { result, rerender } = renderHook(
      ({ key }) => usePersistedState(key, DEFAULTS),
      { initialProps: { key: 'jirou.issues.1' } }
    );
    act(() => result.current[1]({ type: 'bug', search: 'crash' }));

    rerender({ key: 'jirou.issues.2' });

    // La vue du projet 2 est restituée…
    expect(result.current[0]).toEqual({ type: 'epic', search: '' });
    // …et celle du projet 1 n'a pas été écrasée par la valeur de l'autre projet.
    expect(JSON.parse(localStorage.getItem('jirou.issues.1')!)).toEqual({
      type: 'bug',
      search: 'crash',
    });
  });

  it('falls back to the initial value for a key with nothing stored', () => {
    const { result, rerender } = renderHook(
      ({ key }) => usePersistedState(key, DEFAULTS),
      { initialProps: { key: 'jirou.issues.1' } }
    );
    act(() => result.current[1]({ type: 'bug', search: 'crash' }));

    rerender({ key: 'jirou.issues.9' });

    expect(result.current[0]).toEqual(DEFAULTS);
  });
});
