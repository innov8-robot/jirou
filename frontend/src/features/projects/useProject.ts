import { useOutletContext } from 'react-router-dom';

import type { ProjectDetail } from './types';

export interface ProjectContext {
  project: ProjectDetail;
}

/** Accès typé au projet courant depuis les sous-pages du ProjectLayout. */
export function useProject(): ProjectContext {
  return useOutletContext<ProjectContext>();
}
