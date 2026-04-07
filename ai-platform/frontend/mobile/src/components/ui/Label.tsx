/**
 * Label — uppercase tracked label above form fields and sections.
 *
 * Usage:
 *   <Label>Service name</Label>
 *   <Label className="mb-3">Duration</Label>
 */

import { Text } from 'react-native';

interface LabelProps {
  children: React.ReactNode;
  className?: string;
}

export function Label({ children, className = '' }: LabelProps) {
  return (
    <Text
      className={`
        text-xs font-semibold uppercase tracking-wider mb-2.5
        text-fixme-light-text-muted dark:text-fixme-text-muted
        ${className}
      `}
    >
      {children}
    </Text>
  );
}
