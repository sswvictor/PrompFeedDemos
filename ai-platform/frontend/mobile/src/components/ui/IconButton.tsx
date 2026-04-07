/**
 * IconButton — compact pressable for icons (share, QR, back, close).
 *
 * Variants:
 *   ghost   → no background, just the icon/text                 ← default
 *   filled  → subtle card-coloured background
 *   outline → border only
 *
 * Usage:
 *   <IconButton onPress={() => router.back()}>← Back</IconButton>
 *   <IconButton variant="filled" onPress={onShare}>⬆ Share</IconButton>
 */

import { Pressable, Text } from 'react-native';

interface IconButtonProps {
  children: React.ReactNode;
  onPress?: () => void;
  variant?: 'ghost' | 'filled' | 'outline';
  hitSlop?: number;
  className?: string;
}

const variantClass = {
  ghost:   'bg-transparent',
  filled:  'bg-fixme-light-card dark:bg-fixme-card rounded-2xl px-4 py-2.5',
  outline: 'border border-fixme-light-border dark:border-fixme-border rounded-2xl px-4 py-2.5',
} as const;

export function IconButton({
  children,
  onPress,
  variant = 'ghost',
  hitSlop = 12,
  className = '',
}: IconButtonProps) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={hitSlop}
      className={`
        flex-row items-center justify-center
        ${variantClass[variant]}
        ${className}
      `}
    >
      {typeof children === 'string' ? (
        <Text className="text-fixme-light-text-muted dark:text-fixme-text-muted text-[15px] font-medium">
          {children}
        </Text>
      ) : children}
    </Pressable>
  );
}
