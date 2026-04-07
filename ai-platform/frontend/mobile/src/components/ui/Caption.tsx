/**
 * Caption — muted helper / subtitle text below headings, inputs, or cards.
 *
 * Variants:
 *   default  → muted colour
 *   secondary → slightly less muted (for body copy)
 *   error    → red (inline field error messages)
 *   success  → green (inline confirmation)
 *
 * Usage:
 *   <Caption>Hold a card to delete</Caption>
 *   <Caption variant="error">This field is required</Caption>
 *   <Caption center>Add your first service and start taking bookings</Caption>
 */

import { Text } from 'react-native';

interface CaptionProps {
  children: React.ReactNode;
  variant?: 'default' | 'secondary' | 'error' | 'success';
  center?: boolean;
  className?: string;
}

const variantClass = {
  default:   'text-fixme-light-text-muted dark:text-fixme-text-muted',
  secondary: 'text-fixme-light-text-secondary dark:text-fixme-text-secondary',
  error:     'text-fixme-light-error dark:text-fixme-error',
  success:   'text-fixme-light-success dark:text-fixme-success',
} as const;

export function Caption({
  children,
  variant = 'default',
  center = false,
  className = '',
}: CaptionProps) {
  return (
    <Text
      className={`
        text-sm leading-[21px]
        ${variantClass[variant]}
        ${center ? 'text-center' : ''}
        ${className}
      `}
    >
      {children}
    </Text>
  );
}
