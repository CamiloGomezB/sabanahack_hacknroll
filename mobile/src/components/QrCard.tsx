import { StyleSheet, View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';

import { colors, fonts, radius } from '@/constants/theme';

import { Txt } from './Txt';

export type QrKind = 'real' | 'demo';

interface QrCardProps {
  /** Token de acceso (real) o valor de demostración. Nunca datos personales. */
  value: string;
  kind: QrKind;
  /** Pase pendiente o vencido: el QR se atenúa y se indica que no está vigente. */
  inactiveLabel?: string | null;
  size?: number;
}

/**
 * Tarjeta blanca con el QR, como en el PDF. Un QR de demostración se distingue a simple vista:
 * trazo gris, marca de agua "DEMO", borde punteado y la leyenda "no autoriza el ingreso".
 */
export function QrCard({ value, kind, inactiveLabel, size = 190 }: QrCardProps) {
  const demo = kind === 'demo';
  const muted = demo || Boolean(inactiveLabel);
  return (
    <View
      style={[styles.card, demo && styles.demoCard]}
      accessibilityRole="image"
      accessibilityLabel={
        demo
          ? 'Código QR de demostración. No autoriza el ingreso.'
          : inactiveLabel
            ? `Código QR de acceso. ${inactiveLabel}.`
            : 'Código QR de acceso al club.'
      }
    >
      <View style={muted ? styles.mutedQr : null}>
        <QRCode value={value} size={size} color={demo ? '#8f8f8f' : colors.qrInk} backgroundColor="#ffffff" ecl="M" />
      </View>
      {demo ? (
        <View style={styles.watermark} pointerEvents="none">
          <Txt style={styles.watermarkText}>DEMO</Txt>
        </View>
      ) : null}
      {inactiveLabel && !demo ? (
        <View style={styles.watermark} pointerEvents="none">
          <Txt style={[styles.watermarkText, styles.inactiveText]}>{inactiveLabel.toUpperCase()}</Txt>
        </View>
      ) : null}
      <View style={[styles.caption, demo ? styles.captionDemo : styles.captionReal]}>
        <Txt style={[styles.captionText, { color: demo ? '#7a5a12' : colors.qrInk }]}>
          {demo ? 'QR DE DEMOSTRACIÓN · NO AUTORIZA EL INGRESO' : 'QR de acceso · se valida al escanear'}
        </Txt>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    paddingTop: 26,
    paddingHorizontal: 26,
    paddingBottom: 14,
    alignItems: 'center',
    alignSelf: 'center',
    gap: 14,
  },
  demoCard: { borderWidth: 3, borderStyle: 'dashed', borderColor: colors.demo },
  mutedQr: { opacity: 0.35 },
  watermark: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    paddingBottom: 30,
  },
  watermarkText: {
    fontFamily: fonts.semibold,
    fontSize: 46,
    letterSpacing: 6,
    color: 'rgba(160, 110, 20, 0.85)',
    transform: [{ rotate: '-24deg' }],
  },
  inactiveText: { fontSize: 22, letterSpacing: 2, color: 'rgba(170, 40, 30, 0.9)' },
  caption: { borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 4 },
  captionDemo: { backgroundColor: '#fbefd2' },
  captionReal: { backgroundColor: '#eef3f3' },
  captionText: { fontFamily: fonts.semibold, fontSize: 10, lineHeight: 14, letterSpacing: 0.4, textAlign: 'center' },
});
