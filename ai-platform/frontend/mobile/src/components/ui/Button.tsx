/**
 * Button — primary action button used across every screen.
 *
 * Variants:
 *   primary     → filled accent (off-white on dark / near-black on light)  ← default
 *   ghost       → transparent with border
 *   destructive → red border + red text (delete / logout)
 *
 * Sizes:
 *   sm  → compact (inside cards, modals)
 *   md  → standard                                                          ← default
 *   lg  → full-width CTA (welcome, onboarding)
 *
 * Usage:
 *   <Button onPress={handleSave}>Save</Button>
 *   <Button variant="ghost" onPress={onClose}>Cancel</Button>
 *   <Button variant="destructive" onPress={onDelete}>Delete account</Button>
 *   <Button size="lg" loading onPress={submit}>Continue</Button>
 *   <Button disabled onPress={…}>Unavailable</Button>
 */

import { ActivityIndicator, Pressable, Text } from 'react-native';
import { colors } from '@/theme';

interface ButtonProps {
  children: React.ReactNode;
  onPress?: () => void;
  variant?: 'primary' | 'ghost' | 'destructive';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  className?: string;
}

const containerSize = {
  xs: 'px-3 py-1.5 rounded-xl',
  sm: 'px-4 py-2.5 rounded-2xl',
  md: 'px-6 py-3.5 rounded-full',
  lg: 'px-8 py-4 rounded-full',
} as const;

const textSize = {
  xs: 'text-[12px]',
  sm: 'text-[13px]',
  md: 'text-[15px]',
  lg: 'text-base',
} as const;

export function Button({
  children,
  onPress,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  fullWidth = false,
  className = '',
}: ButtonProps) {
  const isDisabled = disabled || loading;

  const variantContainer = {
    primary:     'bg-fixme-light-accent dark:bg-fixme-accent',
    ghost:       'border border-fixme-light-border dark:border-fixme-border bg-transparent',
    destructive: 'border border-fixme-light-error dark:border-fixme-error bg-transparent',
  };

  const variantText = {
    primary:     'text-fixme-light-bg dark:text-fixme-bg font-bold',
    ghost:       'text-fixme-light-text-primary dark:text-fixme-text-primary font-semibold',
    destructive: 'text-fixme-light-error dark:text-fixme-error font-semibold',
  };

  const spinnerColor = variant === 'primary'
    ? colors.bg
    : variant === 'destructive'
      ? colors.error
      : colors.textPrimary;

  return (
    <Pressable
      onPress={isDisabled ? undefined : onPress}
      style={{ opacity: isDisabled ? 0.45 : 1 }}
      className={`
        flex-row items-center justify-center
        ${containerSize[size]}
        ${variantContainer[variant]}
        ${fullWidth ? 'w-full' : 'self-start'}
        ${className}
      `}
    >
      {loading
        ? <ActivityIndicator size="small" color={spinnerColor} />
        : (
          <Text className={`${textSize[size]} ${variantText[variant]}`}>
            {children}
          </Text>
        )
      }
    </Pressable>
  );
}
