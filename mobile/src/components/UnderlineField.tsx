import { forwardRef, useState } from 'react';
import { StyleSheet, TextInput, View, type TextInputInstance, type TextInputProps } from 'react-native';

import { colors, fonts } from '@/constants/theme';

import { Txt } from './Txt';

interface UnderlineFieldProps extends TextInputProps {
  label: string;
  error?: string;
  hint?: string;
}

/** Campo con etiqueta y línea inferior blanca, como "Username" / "Nombre" en el PDF. */
export const UnderlineField = forwardRef<TextInputInstance, UnderlineFieldProps>(function UnderlineField(
  { label, error, hint, style, onFocus, onBlur, ...rest },
  ref,
) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.wrapper}>
      <Txt variant="label" style={styles.label}>
        {label}
      </Txt>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        placeholderTextColor={colors.textFaint}
        selectionColor={colors.goldLight}
        onFocus={(e) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          onBlur?.(e);
        }}
        style={[
          styles.input,
          focused && styles.focused,
          error ? styles.errorLine : null,
          rest.multiline ? styles.multiline : null,
          style,
        ]}
        {...rest}
      />
      {error ? (
        <Txt variant="caption" color={colors.danger} accessibilityLiveRegion="polite">
          {error}
        </Txt>
      ) : hint ? (
        <Txt variant="caption">{hint}</Txt>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  wrapper: { width: '100%', gap: 4 },
  label: { marginBottom: 2 },
  input: {
    fontFamily: fonts.body,
    fontSize: 15,
    color: colors.white,
    paddingVertical: 8,
    borderBottomWidth: 1.5,
    borderBottomColor: colors.line,
  },
  focused: { borderBottomColor: colors.goldLight },
  errorLine: { borderBottomColor: colors.danger },
  multiline: { minHeight: 70, textAlignVertical: 'top' },
});
