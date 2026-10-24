import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { colors, fonts, radius } from '@/constants/theme';

import { Txt } from './Txt';

export interface ChipOption<T extends string | number> {
  value: T;
  label: string;
  sublabel?: string;
  disabled?: boolean;
}

interface ChipSelectorProps<T extends string | number> {
  label?: string;
  options: ChipOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  error?: string;
  /** wrap: rejilla; scroll: fila horizontal desplazable. */
  layout?: 'wrap' | 'scroll';
}

export function ChipSelector<T extends string | number>({
  label,
  options,
  value,
  onChange,
  error,
  layout = 'scroll',
}: ChipSelectorProps<T>) {
  const chips = options.map((o) => {
    const selected = o.value === value;
    return (
      <Pressable
        key={String(o.value)}
        accessibilityRole="radio"
        accessibilityState={{ selected, disabled: o.disabled }}
        accessibilityLabel={o.sublabel ? `${o.label}, ${o.sublabel}` : o.label}
        disabled={o.disabled}
        onPress={() => onChange(o.value)}
        style={[styles.chip, selected && styles.selected, o.disabled && styles.disabled]}
      >
        <Txt style={[styles.text, selected && styles.selectedText, o.disabled && styles.disabledText]}>{o.label}</Txt>
        {o.sublabel ? (
          <Txt style={[styles.sub, selected && styles.selectedSub]}>{o.sublabel}</Txt>
        ) : null}
      </Pressable>
    );
  });

  return (
    <View style={styles.wrapper} accessibilityRole="radiogroup">
      {label ? <Txt variant="label">{label}</Txt> : null}
      {layout === 'scroll' ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
          {chips}
        </ScrollView>
      ) : (
        <View style={[styles.row, styles.wrap]}>{chips}</View>
      )}
      {error ? (
        <Txt variant="caption" color={colors.danger}>
          {error}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: 8, width: '100%' },
  row: { flexDirection: 'row', gap: 8, paddingVertical: 2 },
  wrap: { flexWrap: 'wrap' },
  chip: {
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: 'rgba(0,0,0,0.25)',
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignItems: 'center',
  },
  selected: { backgroundColor: colors.white, borderColor: colors.white },
  disabled: { opacity: 0.35 },
  text: { fontFamily: fonts.medium, fontSize: 13, color: colors.white },
  selectedText: { color: colors.ink },
  disabledText: { textDecorationLine: 'line-through' },
  sub: { fontFamily: fonts.body, fontSize: 10, color: colors.textMuted },
  selectedSub: { color: '#555' },
});
