import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const SHORTCUTS: [string, string][] = [
  ['c', 'Créer un ticket'],
  ['/', 'Rechercher'],
  ['?', 'Afficher cette aide'],
  ['Échap', 'Fermer une fenêtre'],
];

export function ShortcutsHelp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Raccourcis clavier</DialogTitle>
        </DialogHeader>
        <ul className="space-y-2">
          {SHORTCUTS.map(([key, label]) => (
            <li key={key} className="flex items-center justify-between text-sm">
              <span>{label}</span>
              <kbd className="rounded border border-border bg-muted px-2 py-0.5 font-mono text-xs">
                {key}
              </kbd>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
