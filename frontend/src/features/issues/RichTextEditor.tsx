import { useEditor, EditorContent, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import {
  Bold,
  Code,
  Heading2,
  Italic,
  List,
  ListOrdered,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '@/lib/utils';

interface RichTextEditorProps {
  /** Contenu HTML initial. */
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  className?: string;
}

const PROSE =
  'prose prose-sm max-w-none focus:outline-none [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_h2]:text-lg [&_h2]:font-semibold [&_code]:rounded [&_code]:bg-muted [&_code]:px-1';

function ToolbarButton({
  icon: Icon,
  isActive,
  onClick,
  label,
}: {
  icon: LucideIcon;
  isActive: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={isActive}
      onClick={onClick}
      className={cn(
        'flex h-7 w-7 items-center justify-center rounded transition-colors',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-muted'
      )}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function Toolbar({ editor }: { editor: Editor }) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-border p-1">
      <ToolbarButton
        icon={Bold}
        label="Gras"
        isActive={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarButton
        icon={Italic}
        label="Italique"
        isActive={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <ToolbarButton
        icon={Heading2}
        label="Titre"
        isActive={editor.isActive('heading', { level: 2 })}
        onClick={() =>
          editor.chain().focus().toggleHeading({ level: 2 }).run()
        }
      />
      <ToolbarButton
        icon={List}
        label="Liste à puces"
        isActive={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <ToolbarButton
        icon={ListOrdered}
        label="Liste numérotée"
        isActive={editor.isActive('orderedList')}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />
      <ToolbarButton
        icon={Code}
        label="Code"
        isActive={editor.isActive('codeBlock')}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
      />
    </div>
  );
}

/** Éditeur rich text (Tiptap) — JIR-38. */
export function RichTextEditor({
  content,
  onChange,
  placeholder,
  className,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: content || '',
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
    editorProps: {
      attributes: { class: cn(PROSE, 'min-h-24 px-3 py-2') },
    },
  });

  if (!editor) return null;

  return (
    <div className={cn('rounded-md border border-border', className)}>
      <Toolbar editor={editor} />
      <EditorContent editor={editor} data-placeholder={placeholder} />
    </div>
  );
}

/** Rendu lecture seule d'un contenu HTML rich text. */
export function RichTextView({
  html,
  className,
}: {
  html: string | null;
  className?: string;
}) {
  if (!html || html === '<p></p>') {
    return (
      <p className={cn('text-sm italic text-muted-foreground', className)}>
        Aucune description.
      </p>
    );
  }
  return (
    <div
      className={cn(PROSE, className)}
      // Contenu produit par notre propre éditeur Tiptap.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
