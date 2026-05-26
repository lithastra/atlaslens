import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import KpiCard from '../components/KpiCard';

describe('KpiCard', () => {
  it('renders label and value', () => {
    render(<KpiCard label="Total events" value="1,234" />);
    expect(screen.getByText('Total events')).toBeInTheDocument();
    expect(screen.getByText('1,234')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<KpiCard label="Sign-ins" value="0" subtitle="Guard gap" />);
    expect(screen.getByText('Guard gap')).toBeInTheDocument();
  });

  it('renders without subtitle', () => {
    const { container } = render(<KpiCard label="Test" value="42" />);
    expect(container.querySelector('.k-sub')).toBeNull();
  });

  it('applies accent color to bar', () => {
    const { container } = render(<KpiCard label="Test" value="1" accent="#ff0000" />);
    const bar = container.querySelector('.k-acc') as HTMLElement;
    expect(bar.style.background).toBe('rgb(255, 0, 0)');
  });

  it('uses default accent when not provided', () => {
    const { container } = render(<KpiCard label="Test" value="1" />);
    const bar = container.querySelector('.k-acc') as HTMLElement;
    expect(bar.style.background).toBeTruthy();
  });
});
