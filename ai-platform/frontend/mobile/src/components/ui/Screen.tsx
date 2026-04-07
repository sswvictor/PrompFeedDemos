/**
 * Screen — root wrapper for every screen.
 *
 * Handles:
 *  - SafeAreaView with correct bg (dark / light)
 *  - Optional ScrollView with consistent padding
 *  - Keyboard avoiding on iOS
 *
 * Usage:
 *   <Screen>…</Screen>
 *   <Screen scroll>…</Screen>
 *   <Screen scroll padded={false}>…</Screen>
 *   <Screen centered>…</Screen>
 */

import React from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

interface ScreenProps {
  children: React.ReactNode;
  /** Wrap content in a ScrollView */
  scroll?: boolean;
  /** Apply standard horizontal + bottom padding. Default: true */
  padded?: boolean;
  /** Centre content vertically and horizontally */
  centered?: boolean;
  /** Extra className on the outer SafeAreaView */
  className?: string;
}

export function Screen({
  children,
  scroll = false,
  padded = true,
  centered = false,
  className = '',
}: ScreenProps) {
  const inner = scroll ? (
    <ScrollView
      className="flex-1"
      contentContainerClassName={`${padded ? 'px-5 pb-12' : ''} ${centered ? 'flex-1 items-center justify-center' : ''}`}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  ) : (
    <View
      className={`flex-1 ${padded ? 'px-5' : ''} ${centered ? 'items-center justify-center' : ''}`}
    >
      {children}
    </View>
  );

  return (
    <SafeAreaView
      className={`flex-1 bg-fixme-light-bg dark:bg-fixme-bg ${className}`}
      edges={['top']}
    >
      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {inner}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
