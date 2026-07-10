import {
  Bug,
  Bookmark,
  CheckSquare,
  ChevronsDown,
  ChevronsUp,
  ChevronDown,
  ChevronUp,
  Equal,
  Zap,
  type LucideIcon,
} from 'lucide-react';

/**
 * Single source of truth for the issue taxonomy (types, statuses,
 * priorities) and their visual metadata. Every transverse component
 * (badges, priority icon…) reads from here so colors and labels stay
 * consistent with docs/CONVENTIONS.md and the backlog identity section.
 *
 * The string values match the backend contract (snake_case).
 */

// ---------------------------------------------------------------------------
// Issue types
// ---------------------------------------------------------------------------
export const ISSUE_TYPES = ['epic', 'story', 'task', 'bug'] as const;
export type IssueType = (typeof ISSUE_TYPES)[number];

export interface IssueTypeMeta {
  label: string;
  /** Hex color (mirrors the `type.*` Tailwind tokens). */
  color: string;
  icon: LucideIcon;
}

export const ISSUE_TYPE_META: Record<IssueType, IssueTypeMeta> = {
  epic: { label: 'Epic', color: '#8B5CF6', icon: Zap },
  story: { label: 'Story', color: '#22C55E', icon: Bookmark },
  task: { label: 'Task', color: '#3B82F6', icon: CheckSquare },
  bug: { label: 'Bug', color: '#EF4444', icon: Bug },
};

// ---------------------------------------------------------------------------
// Workflow statuses
// ---------------------------------------------------------------------------
export const ISSUE_STATUSES = [
  'todo',
  'in_progress',
  'in_review',
  'done',
] as const;
export type IssueStatus = (typeof ISSUE_STATUSES)[number];

export interface StatusMeta {
  label: string;
  color: string;
  /** Tailwind utility background/text pair for the pill. */
  className: string;
}

export const STATUS_META: Record<IssueStatus, StatusMeta> = {
  todo: {
    label: 'To Do',
    color: '#8993A4',
    className: 'bg-slate-100 text-slate-600',
  },
  in_progress: {
    label: 'In Progress',
    color: '#3B82F6',
    className: 'bg-blue-100 text-blue-700',
  },
  in_review: {
    label: 'In Review',
    color: '#F59E0B',
    className: 'bg-amber-100 text-amber-700',
  },
  done: {
    label: 'Done',
    color: '#22C55E',
    className: 'bg-green-100 text-green-700',
  },
};

// ---------------------------------------------------------------------------
// Priorities (highest → lowest)
// ---------------------------------------------------------------------------
export const PRIORITIES = [
  'highest',
  'high',
  'medium',
  'low',
  'lowest',
] as const;
export type Priority = (typeof PRIORITIES)[number];

export interface PriorityMeta {
  label: string;
  color: string;
  icon: LucideIcon;
}

export const PRIORITY_META: Record<Priority, PriorityMeta> = {
  highest: { label: 'Highest', color: '#CD1317', icon: ChevronsUp },
  high: { label: 'High', color: '#E9494A', icon: ChevronUp },
  medium: { label: 'Medium', color: '#E97F33', icon: Equal },
  low: { label: 'Low', color: '#2D8738', icon: ChevronDown },
  lowest: { label: 'Lowest', color: '#57A55A', icon: ChevronsDown },
};

/** Fibonacci scale used for story-point estimation. */
export const STORY_POINT_SCALE = [1, 2, 3, 5, 8, 13, 21] as const;
