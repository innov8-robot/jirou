import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { StatusBadge } from '@/components/StatusBadge';

describe('StatusBadge', () => {
  it('renders the human label for a status', () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText('In Progress')).toBeInTheDocument();
  });

  it('applies the conventional status color classes', () => {
    render(<StatusBadge status="done" />);
    const badge = screen.getByText('Done');
    expect(badge).toHaveClass('bg-green-100', 'text-green-700');
    expect(badge).toHaveAttribute('data-status', 'done');
  });

  it('renders distinct labels per status', () => {
    const { rerender } = render(<StatusBadge status="todo" />);
    expect(screen.getByText('To Do')).toBeInTheDocument();
    rerender(<StatusBadge status="in_review" />);
    expect(screen.getByText('In Review')).toBeInTheDocument();
  });
});
