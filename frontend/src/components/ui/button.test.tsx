import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Button } from '@/components/ui/button';

describe('Button', () => {
  it('renders its text content', () => {
    render(<Button>Se connecter</Button>);
    expect(
      screen.getByRole('button', { name: 'Se connecter' })
    ).toBeInTheDocument();
  });

  it('applies the primary variant classes by default', () => {
    render(<Button>OK</Button>);
    expect(screen.getByRole('button', { name: 'OK' })).toHaveClass(
      'bg-primary'
    );
  });
});
