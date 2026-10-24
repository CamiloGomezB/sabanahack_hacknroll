import { StyleSheet, View } from 'react-native';

import { colors, fonts } from '@/constants/theme';

import { Txt } from './Txt';

/** Monograma "N" dorado sobre círculo blanco, como en el PDF de referencia. */
export function Logo({ size = 92 }: { size?: number }) {
  return (
    <View
      accessibilityRole="image"
      accessibilityLabel="N Club"
      style={[styles.circle, { width: size, height: size, borderRadius: size / 2 }]}
    >
      <Txt
        style={{
          fontFamily: fonts.script,
          fontSize: size * 0.62,
          lineHeight: size * 0.9,
          color: colors.gold,
          marginTop: size * 0.06,
          marginLeft: -size * 0.04,
        }}
      >
        N
      </Txt>
    </View>
  );
}

export function Wordmark() {
  return (
    <View style={styles.wordmark}>
      <Txt variant="display" align="center" style={styles.welcome}>
        BIENVENIDO A
      </Txt>
      {/* Ancho completo y una sola línea: en iOS la fuente caligráfica medía de menos y "Club"
          se cortaba, así que solo se veía la "N". */}
      <Txt variant="script" align="center" numberOfLines={1} style={styles.script}>
        N Club
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  circle: {
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  wordmark: { alignItems: 'center', alignSelf: 'stretch' },
  welcome: { fontSize: 36, lineHeight: 44 },
  script: { fontSize: 50, lineHeight: 64, marginTop: -6, alignSelf: 'stretch', paddingHorizontal: 16 },
});
