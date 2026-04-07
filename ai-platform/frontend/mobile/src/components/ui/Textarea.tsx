/**
 * Textarea — multiline text field (bio, notes, descriptions).
 *
 * Usage:
 *   <Textarea label="Bio" value={bio} onChangeText={setBio} />
 *   <Textarea label="Notes" rows={6} value={notes} onChangeText={setNotes} />
 */

import { forwardRef } from 'react';
import { TextInput, TextInputProps, View } from 'react-native';
import { colors } from '@/theme';
import { Label } from './Label';
import { Caption } from './Caption';

interface TextareaProps extends Omit<TextInputProps, 'multiline'> {
  label?: string;
  error?: string;
  /** Number of visible lines. Default: 4 */
  rows?: number;
  wrapperClassName?: string;
}

export const Textarea = forwardRef<TextInput, TextareaProps>(function Textarea(
  { label, error, rows = 4, wrapperClassName = '', style, ...rest },
  ref,
) {
  // 24px per line approx for base font + line-height
  const minHeight = rows * 24 + 28;

  return (
    <View className={`mb-5 ${wrapperClassName}`}>
      {label && <Label>{label}</Label>}

      <TextInput
        ref={ref}
        multiline
        textAlignVertical="top"
        className={`
          px-4 py-3.5 rounded-[14px] text-base
          bg-fixme-light-card dark:bg-fixme-card
          text-fixme-light-text-primary dark:text-fixme-text-primary
          border
          ${error
            ? 'border-fixme-light-error dark:border-fixme-error'
            : 'border-fixme-light-border dark:border-fixme-border'
          }
        `}
        placeholderTextColor={colors.textMuted}
        style={[{ minHeight }, style]}
        {...rest}
      />

      {error && (
        <Caption variant="error" className="mt-1.5">
          {error}
        </Caption>
      )}
    </View>
  );
});
