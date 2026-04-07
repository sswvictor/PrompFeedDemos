/**
 * Divider — thin horizontal separator.
 *
 * Usage:
 *   <Divider />
 *   <Divider soft />          ← even lighter border
 *   <Divider className="my-4" />
 */

import { View } from 'react-native';

interface DividerProps {
  /** Use the softer border colour */
  soft?: boolean;
  className?: string;
}

export function Divider({ soft = false, className = '' }: DividerProps) {
  return (
    <View
      className={`
        h-px w-full
        ${soft
          ? 'bg-fixme-light-border-soft dark:bg-fixme-border-soft'
          : 'bg-fixme-light-border dark:bg-fixme-border'
        }
        ${className}
      `}
    />
  );
}
