import { useCallback, useEffect, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';

import { Badge, GlassCard, Notice } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Txt } from '@/components/Txt';
import { colors, radius, spacing } from '@/constants/theme';
import { useAsync } from '@/hooks/useAsync';
import { MAX_FOTOS, borrarFoto, fetchMisFotos, subirFotoRegistro, urlDeFoto } from '@/services/supabase/fotos';
import type { EstadoHuella, Fotografia } from '@/types/database';
import { friendlyError } from '@/utils/format';
import { formatClubDateTime } from '@/utils/time';

import { FaceCamera } from './FaceCamera';

const ESTADO: Record<EstadoHuella, { label: string; tone: 'success' | 'warning' | 'danger' }> = {
  pendiente: { label: 'Procesando', tone: 'warning' },
  lista: { label: 'Lista para reconocerte', tone: 'success' },
  sin_cara: { label: 'No sirvió', tone: 'danger' },
};
/** Mientras haya fotos procesándose, se vuelve a consultar cada tanto. */
const REVISAR_CADA_MS = 8000;

interface FacePhotosProps {
  userId: string;
  personaId: string;
  consent: boolean;
}

/** Fotos de registro para que el robot reconozca a la persona en recepción. */
export function FacePhotos({ userId, personaId, consent }: FacePhotosProps) {
  const load = useCallback(() => fetchMisFotos(personaId), [personaId]);
  const { state, reload } = useAsync(load, 'No se pudieron cargar tus fotos.');
  const [camera, setCamera] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const fotos = state.status === 'success' ? state.data : [];
  const procesando = fotos.some((f) => f.huella_estado === 'pendiente');

  useEffect(() => {
    if (!procesando) return;
    const id = setInterval(reload, REVISAR_CADA_MS);
    return () => clearInterval(id);
  }, [procesando, reload]);

  async function upload(base64: string) {
    try {
      await subirFotoRegistro(userId, personaId, base64);
    } catch (e) {
      throw new Error(friendlyError(e, 'No se pudo subir la foto.'));
    }
    setMessage({ ok: true, text: 'Foto subida. En unos segundos queda lista para el reconocimiento.' });
    reload();
  }

  async function remove(foto: Fotografia) {
    setMessage(null);
    try {
      await borrarFoto(foto);
      setMessage({ ok: true, text: 'Foto borrada, con su huella facial.' });
    } catch (e) {
      setMessage({ ok: false, text: friendlyError(e, 'No se pudo borrar la foto.') });
    }
    reload();
  }

  if (!consent) {
    return (
      <GlassCard>
        <Notice
          title="Activa el reconocimiento facial para subir tu foto"
          message="Usa el interruptor de Privacidad. Es opcional: siempre puedes entrar con tu QR."
        />
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <Txt variant="caption">
        El robot de recepción te reconoce con estas fotos. Se guardan en un espacio privado del club y puedes borrarlas
        cuando quieras. Con dos o tres fotos de frente y con buena luz es suficiente.
      </Txt>

      {state.status === 'loading' ? <Txt variant="caption">Cargando tus fotos…</Txt> : null}
      {state.status === 'error' ? <Notice tone="danger" title={state.error} /> : null}

      {fotos.map((f) => (
        <View key={f.id} style={styles.row}>
          <Thumbnail ruta={f.ruta} />
          <View style={styles.flex}>
            <Badge label={ESTADO[f.huella_estado].label} tone={ESTADO[f.huella_estado].tone} />
            <Txt variant="caption">{formatClubDateTime(f.tomada_en)}</Txt>
            {f.huella_estado === 'sin_cara' && f.huella_detalle ? (
              <Txt variant="caption">{f.huella_detalle}. Toma otra, de frente y con más luz.</Txt>
            ) : null}
          </View>
          <PillButton label="Borrar" variant="danger" icon="trash-outline" onPress={() => void remove(f)} />
        </View>
      ))}

      {message ? <Notice tone={message.ok ? 'success' : 'danger'} title={message.text} /> : null}

      {fotos.length < MAX_FOTOS ? (
        <PillButton
          label={fotos.length ? 'Tomar otra foto' : 'Tomar mi foto'}
          icon="camera-outline"
          disabled={state.status === 'loading'}
          onPress={() => {
            setMessage(null);
            setCamera(true);
          }}
        />
      ) : (
        <Txt variant="caption">Ya tienes {MAX_FOTOS} fotos. Borra una para tomar otra.</Txt>
      )}
      {procesando ? (
        <PillButton label="Actualizar estado" variant="outline" icon="refresh-outline" onPress={reload} />
      ) : null}

      <FaceCamera visible={camera} onClose={() => setCamera(false)} onAccept={upload} />
    </GlassCard>
  );
}

function Thumbnail({ ruta }: { ruta: string }) {
  const load = useCallback(() => urlDeFoto(ruta), [ruta]);
  const { state } = useAsync(load);
  const uri = state.status === 'success' ? state.data : null;
  return uri ? <Image source={{ uri }} style={styles.thumb} /> : <View style={styles.thumb} />;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  flex: { flex: 1, gap: 2, alignItems: 'flex-start' },
  thumb: { width: 56, height: 72, borderRadius: radius.sm, backgroundColor: colors.glass },
});
