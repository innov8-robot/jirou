import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { ISSUE_TYPE_META } from '@/lib/issues';

describe('IssueTypeBadge', () => {
  it('renders the label for the given type', () => {
    render(<IssueTypeBadge type="story" />);
    expect(screen.getByText('Story')).toBeInTheDocument();
  });

  it('applies the conventional type color to the icon tile', () => {
    const { container } = render(<IssueTypeBadge type="bug" />);
    const tile = container.querySelector('[data-issue-type="bug"] span');
    expect(tile).toHaveStyle({ backgroundColor: ISSUE_TYPE_META.bug.color });
  });

  it('hides the label but keeps it accessible when showLabel is false', () => {
    render(<IssueTypeBadge type="epic" showLabel={false} />);
    // Label still present for screen readers (sr-only), but only once.
    expect(screen.getByText('Epic')).toHaveClass('sr-only');
  });
});
