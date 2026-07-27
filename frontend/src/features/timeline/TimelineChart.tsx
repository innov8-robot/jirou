import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import type { Issue } from '@/features/issues/types';
import { ISSUE_TYPE_META } from '@/lib/issues';
import { cn } from '@/lib/utils';
import type { TimelineData } from './api';
import {
  addDays,
  dayDiff,
  formatDayMonth,
  formatMonth,
  parseDate,
  startOfDay,
  toISO,
} from './dateUtils';

export type Scale = 'weeks' | 'months' | 'quarters';
const PX: Record<Scale, number> = { weeks: 22, months: 8, quarters: 3 };
const ROW_H = 44;
const LEFT_W = 260;

interface Row {
  kind: 'epic' | 'child';
  issue: Issue;
  done?: number;
  total?: number;
}

interface Props {
  data: TimelineData;
  projectId: number | string;
  scale: Scale;
  canEdit: boolean;
  onCommitDates: (key: string, start: string, due: string) => void;
}

export function TimelineChart({
  data,
  projectId,
  scale,
  canEdit,
  onCommitDates,
}: Props) {
  const px = PX[scale];
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Lignes rendues (epics + enfants dépliés).
  const rows: Row[] = [];
  for (const te of data.epics) {
    rows.push({
      kind: 'epic',
      issue: te.epic,
      done: te.progress.done,
      total: te.progress.total,
    });
    if (expanded[String(te.epic.id)]) {
      for (const c of te.children) rows.push({ kind: 'child', issue: c });
    }
  }

  // Plage de dates.
  const dates: Date[] = [];
  for (const te of data.epics) {
    for (const iss of [te.epic, ...te.children]) {
      const s = parseDate(iss.start_date);
      const d = parseDate(iss.due_date);
      if (s) dates.push(s);
      if (d) dates.push(d);
    }
  }
  const today = startOfDay(new Date());
  let rangeStart = dates.length
    ? startOfDay(new Date(Math.min(...dates.map((d) => d.getTime()))))
    : addDays(today, -7);
  let rangeEnd = dates.length
    ? startOfDay(new Date(Math.max(...dates.map((d) => d.getTime()))))
    : addDays(today, 45);
  rangeStart = addDays(rangeStart, -3);
  rangeEnd = addDays(rangeEnd, 7);
  const totalDays = Math.max(1, dayDiff(rangeStart, rangeEnd) + 1);
  const width = totalDays * px;

  // Graduations.
  const ticks: { x: number; label: string }[] = [];
  if (scale === 'weeks') {
    for (let i = 0; i <= totalDays; i += 7) {
      ticks.push({ x: i * px, label: formatDayMonth(addDays(rangeStart, i)) });
    }
  } else {
    const cur = new Date(rangeStart.getFullYear(), rangeStart.getMonth(), 1);
    while (cur <= rangeEnd) {
      const x = dayDiff(rangeStart, cur) * px;
      if (x >= 0) ticks.push({ x, label: formatMonth(cur) });
      cur.setMonth(cur.getMonth() + 1);
    }
  }

  // Position verticale des barres d'epic (pour tracer les dépendances).
  const epicY: Record<string, { x1: number; x2: number; y: number }> = {};
  rows.forEach((row, idx) => {
    if (row.kind !== 'epic') return;
    const s = parseDate(row.issue.start_date);
    const d = parseDate(row.issue.due_date);
    if (!s && !d) return;
    const a = s ?? d!;
    const b = d ?? s!;
    const left = dayDiff(rangeStart, a) * px;
    const w = Math.max(px, (Math.max(0, dayDiff(a, b)) + 1) * px);
    epicY[row.issue.key] = {
      x1: left,
      x2: left + w,
      y: idx * ROW_H + ROW_H / 2,
    };
  });

  const deps = data.dependencies.filter(
    (dep) => epicY[dep.from_key] && epicY[dep.to_key]
  );

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <div style={{ minWidth: LEFT_W + width }}>
        {/* En-tête */}
        <div className="flex border-b border-border bg-surface">
          <div
            className="sticky left-0 z-20 shrink-0 border-r border-border bg-surface px-3 py-2 text-xs font-semibold uppercase text-muted-foreground"
            style={{ width: LEFT_W }}
          >
            Epic
          </div>
          <div className="relative" style={{ width, height: 32 }}>
            {ticks.map((t, i) => (
              <div
                key={i}
                className="absolute top-0 h-full border-l border-border/60 pl-1 text-[11px] text-muted-foreground"
                style={{ left: t.x }}
              >
                {t.label}
              </div>
            ))}
          </div>
        </div>

        {/* Corps */}
        <div className="relative">
          {/* Lignes de dépendance (SVG) */}
          <svg
            className="pointer-events-none absolute z-10"
            style={{ left: LEFT_W, top: 0, width, height: rows.length * ROW_H }}
          >
            <defs>
              <marker
                id="arrow"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L6,3 L0,6 Z" fill="#94a3b8" />
              </marker>
            </defs>
            {deps.map((dep, i) => {
              const a = epicY[dep.from_key];
              const b = epicY[dep.to_key];
              const midX = (a.x2 + b.x1) / 2;
              return (
                <path
                  key={i}
                  d={`M ${a.x2} ${a.y} C ${midX} ${a.y}, ${midX} ${b.y}, ${b.x1} ${b.y}`}
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                  markerEnd="url(#arrow)"
                />
              );
            })}
          </svg>

          {rows.map((row) => (
            <div
              key={`${row.kind}-${row.issue.id}`}
              className="flex border-b border-border/50"
              style={{ height: ROW_H }}
            >
              <div
                className={cn(
                  'sticky left-0 z-20 flex shrink-0 items-center gap-1.5 border-r border-border bg-background px-3',
                  row.kind === 'child' && 'pl-8'
                )}
                style={{ width: LEFT_W }}
              >
                {row.kind === 'epic' && (row.total ?? 0) > 0 ? (
                  <button
                    type="button"
                    onClick={() =>
                      setExpanded((e) => ({
                        ...e,
                        [String(row.issue.id)]: !e[String(row.issue.id)],
                      }))
                    }
                    className="text-muted-foreground"
                    aria-label="Déplier"
                  >
                    {expanded[String(row.issue.id)] ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                ) : (
                  <span className="w-4" />
                )}
                <IssueTypeBadge type={row.issue.type} showLabel={false} />
                <span className="truncate text-sm">{row.issue.summary}</span>
                {row.kind === 'epic' && (row.total ?? 0) > 0 && (
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                    {row.done}/{row.total}
                  </span>
                )}
              </div>

              <div className="relative" style={{ width }}>
                <Bar
                  issue={row.issue}
                  rangeStart={rangeStart}
                  px={px}
                  canEdit={canEdit}
                  isEpic={row.kind === 'epic'}
                  done={row.done}
                  total={row.total}
                  onCommit={onCommitDates}
                  projectId={projectId}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Bar({
  issue,
  rangeStart,
  px,
  canEdit,
  isEpic,
  done,
  total,
  onCommit,
  projectId,
}: {
  issue: Issue;
  rangeStart: Date;
  px: number;
  canEdit: boolean;
  isEpic: boolean;
  done?: number;
  total?: number;
  onCommit: (key: string, start: string, due: string) => void;
  projectId: number | string;
}) {
  const navigate = useNavigate();
  const start = parseDate(issue.start_date);
  const due = parseDate(issue.due_date);
  const deltaRef = useRef({ start: 0, end: 0 });
  const [delta, setDelta] = useState({ start: 0, end: 0 });

  if (!start && !due) {
    if (!canEdit) {
      return (
        <span className="flex h-full items-center pl-2 text-xs text-muted-foreground/50">
          pas de dates
        </span>
      );
    }
    const t0 = startOfDay(new Date());
    return (
      <button
        type="button"
        onClick={() => onCommit(issue.key, toISO(t0), toISO(addDays(t0, 7)))}
        className="flex h-full items-center pl-2 text-xs text-muted-foreground/60 hover:text-primary hover:underline"
      >
        + définir des dates
      </button>
    );
  }
  const s = start ?? due!;
  const e = due ?? start!;
  const baseLeft = dayDiff(rangeStart, s);
  const baseLen = Math.max(0, dayDiff(s, e));
  const left = (baseLeft + delta.start) * px;
  const len = baseLen + (delta.end - delta.start);
  const width = Math.max(px, (len + 1) * px);
  const color = ISSUE_TYPE_META[issue.type].color;
  const pct = total ? Math.round(((done ?? 0) / total) * 100) : 0;

  function drag(mode: 'move' | 'start' | 'end') {
    return (ev: React.PointerEvent) => {
      if (!canEdit) return;
      ev.stopPropagation();
      ev.preventDefault();
      const startX = ev.clientX;
      const onMove = (m: PointerEvent) => {
        const d = Math.round((m.clientX - startX) / px);
        const next =
          mode === 'move'
            ? { start: d, end: d }
            : mode === 'start'
              ? { start: d, end: 0 }
              : { start: 0, end: d };
        deltaRef.current = next;
        setDelta(next);
      };
      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        const { start: ds, end: de } = deltaRef.current;
        deltaRef.current = { start: 0, end: 0 };
        setDelta({ start: 0, end: 0 });
        if (ds === 0 && de === 0) return;
        let ns = addDays(s, ds);
        let ne = addDays(e, de);
        if (ns > ne) [ns, ne] = [ne, ns];
        onCommit(issue.key, toISO(ns), toISO(ne));
      };
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    };
  }

  return (
    <div
      className="absolute top-1/2 flex h-6 -translate-y-1/2 items-center overflow-hidden rounded text-xs text-white shadow-sm"
      style={{ left, width, backgroundColor: color, touchAction: 'none' }}
      onPointerDown={drag('move')}
      onDoubleClick={() =>
        navigate(`/projects/${projectId}/issues/${issue.key}`)
      }
      title={`${issue.key} · ${issue.summary}`}
    >
      {isEpic && total ? (
        <div
          className="absolute inset-y-0 left-0 bg-black/25"
          style={{ width: `${pct}%` }}
        />
      ) : null}
      {canEdit && (
        <span
          onPointerDown={drag('start')}
          className="absolute inset-y-0 left-0 w-1.5 cursor-ew-resize bg-black/20"
        />
      )}
      <span className="pointer-events-none z-10 truncate px-2">
        {issue.key}
      </span>
      {canEdit && (
        <span
          onPointerDown={drag('end')}
          className="absolute inset-y-0 right-0 w-1.5 cursor-ew-resize bg-black/20"
        />
      )}
    </div>
  );
}
