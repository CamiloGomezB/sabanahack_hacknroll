import { StyleSheet, Text, type TextProps } from 'react-native';

import { colors, fonts } from '@/constants/theme';

export type TxtVariant = 'display' | 'script' | 'title' | 'subtitle' | 'body' | 'label' | 'caption' | 'overline';

interface TxtProps extends TextProps {
  variant?: TxtVariant;
  color?: string;
  align?: 'left' | 'center' | 'right';
}

export function Txt({ variant = 'body', color, align, style, ...rest }: TxtProps) {
  return (
    <Text
      {...rest}
      style={[styles[variant], color ? { color } : null, align ? { textAlign: align } : null, style]}
    />
  );
}

const styles = StyleSheet.create({
  display: { fontFamily: fonts.display, fontSize: 34, letterSpacing: 0.5, color: colors.text },
  script: { fontFamily: fonts.script, fontSize: 46, color: colors.text },
  title: { fontFamily: fonts.semibold, fontSize: 20, color: colors.text },
  subtitle: { fontFamily: fonts.medium, fontSize: 16, color: colors.text },
  body: { fontFamily: fonts.body, fontSize: 14, lineHeight: 21, color: colors.text },
  label: { fontFamily: fonts.medium, fontSize: 13, color: colors.text },
  caption: { fontFamily: fonts.body, fontSize: 12, lineHeight: 17, color: colors.textMuted },
  overline: { fontFamily: fonts.semibold, fontSize: 11, letterSpacing: 1.2, color: colors.textMuted },
});
