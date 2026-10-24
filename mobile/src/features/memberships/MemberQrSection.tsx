import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { GlassCard, Notice } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { QrCard } from '@/components/QrCard';
import { ErrorView, LoadingView } from '@/components/StateViews';
import { Txt } from '@/components/Txt';
import { spacing } from '@/constants/theme';
import type { SessionState } from '@/features/auth/SessionProvider';
import { formatClubDateTime } from '@/utils/time';

import { useMemberQr } from './useMemberQr';

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

/** QR personal de miembros y personal: real (token verificado), de demostración o pendiente. */
export function MemberQrSection({ session, membershipActive }: { session: Active; membershipActive: boolean }) {
  const { state, generate, generating, reload } = useMemberQr(session, membershipActive);
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);

  switch (state.status) {
    case 'loading':
      return (
        <GlassCard style={styles.placeholder}>
          <LoadingView message="Verificando tu QR…" />
        </GlassCard>
      );
    case 'error':
      return (
        <GlassCard>
          <ErrorView message={state.message} onRetry={() => void reload()} />
        </GlassCard>
      );
    case 'unavailable':
      return <Notice tone="danger" icon="lock-closed-outline" title="QR no disponible" message={state.reason} />;
    case 'demo':
      return <QrCard value={state.value} kind="demo" />;
    case 'missing':
      return (
        <GlassCard style={styles.missing}>
          <Txt variant="subtitle" align="center">
            Genera tu QR de acceso
          </Txt>
          <Txt variant="caption" align="center">
            {state.reason} Al generar uno nuevo, cualquier QR anterior deja de funcionar.
          </Txt>
          <PillButton label="Generar mi QR" icon="qr-code-outline" onPress={() => void generate()} loading={generating} />
        </GlassCard>
      );
    case 'real':
      return (
        <View style={styles.real}>
          <QrCard value={state.token} kind="real" />
          {state.validUntil ? (
            <Txt variant="caption" align="center">
              Válido hasta {formatClubDateTime(state.validUntil)}
            </Txt>
          ) : null}
          {confirmRegenerate ? (
            <GlassCard>
              <Txt variant="caption" align="center">
                ¿Generar un QR nuevo? El actual quedará revocado de inmediato.
              </Txt>
              <View style={styles.row}>
                <PillButton label="Cancelar" variant="ghost" onPress={() => setConfirmRegenerate(false)} />
                <PillButton
                  label="Sí, generar"
                  variant="outline"
                  loading={generating}
                  onPress={() => {
                    setConfirmRegenerate(false);
                    void generate();
                  }}
                />
              </View>
            </GlassCard>
          ) : (
            <PillButton label="Generar un QR nuevo" variant="ghost" onPress={() => setConfirmRegenerate(true)} />
          )}
        </View>
      );
  }
}

const styles = StyleSheet.create({
  placeholder: { minHeight: 200, justifyContent: 'center' },
  missing: { alignItems: 'center', gap: spacing.md, paddingVertical: spacing.lg },
  real: { gap: spacing.sm },
  row: { flexDirection: 'row', justifyContent: 'center', gap: spacing.sm },
});
