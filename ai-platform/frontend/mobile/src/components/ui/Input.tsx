/**
 * Input — single-line text field with optional label and error message.
 *
 * Usage:
 *   <Input label="Service name" value={name} onChangeText={setName} />
 *   <Input label="Email" keyboardType="email-address" autoCapitalize="none" />
 *   <Input label="Price" error="Enter a valid price" value={price} onChangeText={setPrice} />
 *   <Input label="Phone" returnKeyType="done" onSubmitEditing={handleSave} />
 */

import { forwardRef } from 'react';
import { TextInput, TextInputProps, View } from 'react-native';
import { colors } from '@/theme';
import { Label } from './Label';
import { Caption } from './Caption';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  /** Extra className on the outer wrapper */
  wrapperClassName?: string;
}

export const Input = forwardRef<TextInput, InputProps>(function Input(
  { label, error, wrapperClassName = '', style, ...rest },
  ref,
) {
  return (
    <View className={`mb-5 ${wrapperClassName}`}>
      {label && <Label>{label}</Label>}

      <TextInput
        ref={ref}
        className={`
          h-[52px] px-4 rounded-[14px] text-base
          bg-fixme-light-card dark:bg-fixme-card
          text-fixme-light-text-primary dark:text-fixme-text-primary
          border
          ${error
            ? 'border-fixme-light-error dark:border-fixme-error'
            : 'border-fixme-light-border dark:border-fixme-border'
          }
        `}
        placeholderTextColor={colors.textMuted}
        style={style}
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
