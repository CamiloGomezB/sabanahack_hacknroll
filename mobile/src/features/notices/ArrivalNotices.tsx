import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Badge, GlassCard, SectionTitle } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Txt } from '@/components/Txt';
import { spacing } from '@/constants/theme';
import { useAsync } from '@/hooks/useAsync';
import { fetchMyAvisos, responderAviso, subscribeAvisos, type EstadoAviso } from '@/services/supabase/avisos';
import { friendlyError } from '@/utils/format';
import { formatClubDateTime } from '@/utils/time';

const ESTADO: Record<EstadoAviso, { label: string; tone: 'gold' | 'neutral' | 'success' | 'danger' }> = {
  emitido: { label: 'Nuevo', tone: 'gold' },
  recibido: { label: 'Recibido', tone: 'neutral' },
  aceptado: { label: 'Aceptado', tone: 'success' },
  sin_respuesta: { label: 'Sin respuesta', tone: 'danger' },
};

/**
 * Avisos que deja el robot cuando llega un invitado o externo a cargo de esta persona. "Recibido"
 * confirma que lo vio; "Aceptado", que va al punto de encuentro. Solo con sesión real.
 */
export function ArrivalNotices({ personaId }: { personaId: string }) {
  const load = useCallback(() => fetchMyAvisos(personaId), [personaId]);
  const { state, reload } = useAsync(load, 'No se pudieron cargar los avisos.');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => subscribeAvisos(personaId, reload), [personaId, reload]);

  async function answer(id: string, estado: 'recibido' | 'aceptado') {
    setError(null);
    try {
      await responderAviso(id, estado);
      reload();
    } catch (e) {
      setError(friendlyError(e, 'No se pudo responder el aviso.'));
    }
  }

  if (state.status !== 'success' || state.data.length === 0) return null;
  return (
    <>
      <SectionTitle>Avisos de llegada</SectionTitle>
      {state.data.map((a) => (
        <GlassCard key={a.id}>
          <View style={styles.row}>
            <Txt variant="label" style={styles.flex}>
              {a.mensaje}
            </Txt>
            <Badge label={ESTADO[a.estado].label} tone={ESTADO[a.estado].tone} />
          </View>
          <Txt variant="caption">{formatClubDateTime(a.creado_en)}</Txt>
          {a.estado === 'emitido' || a.estado === 'recibido' ? (
            <View style={styles.row}>
              {a.estado === 'emitido' ? (
                <PillButton label="Recibido" variant="outline" style={styles.flex} onPress={() => void answer(a.id, 'recibido')} />
              ) : null}
              <PillButton label="Voy en camino" style={styles.flex} onPress={() => void answer(a.id, 'aceptado')} />
            </View>
          ) : null}
        </GlassCard>
      ))}
      {error ? <Txt variant="caption">{error}</Txt> : null}
    </>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  flex: { flex: 1 },
});
