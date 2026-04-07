/**
 * Heading — page titles and hero text.
 *
 * Sizes:
 *   sm   → 22px  (section titles, modal titles)
 *   md   → 26px  (screen titles)       ← default
 *   lg   → 30px  (hero / welcome)
 *   xl   → 36px  (cinematic / splash)
 *
 * Usage:
 *   <Heading>Services</Heading>
 *   <Heading size="lg">More clients booked.</Heading>
 *   <Heading size="sm" secondary>Category</Heading>
 */

import { Text } from 'react-native';

interface HeadingProps {
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** Use secondary text colour instead of primary */
  secondary?: boolean;
  /** Centre-align */
  center?: boolean;
  className?: string;
}

const sizeClass = {
  sm: 'text-[22px] leading-[28px]',
  md: 'text-[26px] leading-[32px]',
  lg: 'text-[30px] leading-[36px]',
  xl: 'text-[36px] leading-[42px]',
} as const;

export function Heading({
  children,
  size = 'md',
  secondary = false,
  center = false,
  className = '',
}: HeadingProps) {
  return (
    <Text
      className={`
        font-bold tracking-tight
        ${sizeClass[size]}
        ${secondary
          ? 'text-fixme-light-text-secondary dark:text-fixme-text-secondary'
          : 'text-fixme-light-text-primary dark:text-fixme-text-primary'
        }
        ${center ? 'text-center' : ''}
        ${className}
      `}
    >
      {children}
    </Text>
  );
}
