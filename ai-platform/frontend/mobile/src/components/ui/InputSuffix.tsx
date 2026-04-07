/**
 * InputSuffix — single-line input with a fixed unit label on the right.
 *
 * Used for: price (kr), percentages (%), distances (km), etc.
 *
 * Usage:
 *   <InputSuffix label="Price ex. VAT" suffix="kr" value={price} onChangeText={setPrice} keyboardType="decimal-pad" />
 *   <InputSuffix label="Distance" suffix="km" value={dist} onChangeText={setDist} />
 */

import { forwardRef } from 'react';
import { Text, TextInput, TextInputProps, View } from 'react-native';
import { colors } from '@/theme';
import { Label } from './Label';
import { Caption } from './Caption';

interface InputSuffixProps extends TextInputProps {
  label?: string;
  suffix: string;
  error?: string;
  wrapperClassName?: string;
}

export const InputSuffix = forwardRef<TextInput, InputSuffixProps>(
  function InputSuffix(
    { label, suffix, error, wrapperClassName = '', style, ...rest },
    ref,
  ) {
    return (
      <View className={`mb-5 ${wrapperClassName}`}>
        {label && <Label>{label}</Label>}

        <View className="relative">
          <TextInput
            ref={ref}
            className={`
              h-[52px] pl-4 pr-14 rounded-[14px] text-base
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

          {/* Suffix label — absolutely positioned inside the input */}
          <Text
            style={{
              position: 'absolute',
              right: 16,
              top: 0,
              bottom: 0,
              lineHeight: 52,
              textAlignVertical: 'center',
              fontSize: 15,
              color: colors.textMuted,
            }}
          >
            {suffix}
          </Text>
        </View>

        {error && (
          <Caption variant="error" className="mt-1.5">
            {error}
          </Caption>
        )}
      </View>
    );
  },
);
