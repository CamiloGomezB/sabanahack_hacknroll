import { useState } from 'react';
import { StyleSheet, Switch, View } from 'react-native';

import { GlassCard, InfoRow, Notice, SectionTitle } from '@/components/Card';
import { Logo } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { UnderlineField } from '@/components/UnderlineField';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { PROFILE_LABELS } from '@/constants/profiles';
import { colors, spacing } from '@/constants/theme';
import { useActiveSession } from '@/features/auth/SessionProvider';
import { membershipStatus } from '@/features/memberships/status';
import { updateMyConsent, updateMyTrato } from '@/services/supabase/personas';
import { friendlyError, memberCode } from '@/utils/format';
import { formatClock, formatClubDateTime } from '@/utils/time';

export default function ProfileScreen() {
  const { session, signOut, setPersona } = useActiveSession();
  const persona = session.status === 'pass' ? null : session.persona;
  const [consent, setConsent] = useState(persona?.consentimiento_biometrico ?? false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [trato, setTrato] = useState(persona?.trato ?? '');
  const [tratoMsg, setTratoMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function saveTrato() {
    setTratoMsg(null);
    if (trato.trim().length > 400) {
      setTratoMsg({ ok: false, text: 'Máximo 400 caracteres.' });
      return;
    }
    if (session.status !== 'real') {
      setTratoMsg({ ok: true, text: 'Cambio de demostración: no se guardó en Supabase.' });
      return;
    }
    setSaving(true);
    try {
      const updated = await updateMyTrato(session.userId, trato);
      setPersona(updated);
      setTratoMsg({ ok: true, text: 'Listo. El robot usará este tono al recibirte.' });
    } catch (e) {
      setTratoMsg({ ok: false, text: friendlyError(e, 'No se pudo guardar.') });
    } finally {
      setSaving(false);
    }
  }

  async function toggleConsent(value: boolean) {
    setMessage(null);
    if (session.status !== 'real') {
      setConsent(value);
      setMessage({ ok: true, text: 'Cambio de demostración: no se guardó en Supabase.' });
      return;
    }
    setSaving(true);
    try {
      const updated = await updateMyConsent(session.userId, value);
      setPersona(updated);
      setConsent(updated.consentimiento_biometrico);
      setMessage({
        ok: true,
        text: value
          ? 'Consentimiento registrado.'
          : 'Consentimiento retirado. Tus huellas faciales se eliminaron del sistema.',
      });
    } catch (e) {
      setMessage({ ok: false, text: friendlyError(e, 'No se pudo actualizar el consentimiento.') });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen back title="Mi perfil" dense>
      <Logo size={72} />
      {persona ? (
        <>
          <GlassCard>
            <Txt variant="subtitle">{persona.nombre_demo}</Txt>
            {persona.email ? <InfoRow label="Correo" value={persona.email} /> : null}
            <InfoRow label="Perfil" value={PROFILE_LABELS[session.profile]} />
            <InfoRow label="Código ID" value={memberCode(session.profile, persona.id)} />
            <InfoRow label="Estado" value={membershipStatus(persona).label} />
            <InfoRow label="Horario" value={`${formatClock(persona.horario_inicio)} – ${formatClock(persona.horario_fin)}`} />
            {persona.rol !== 'usuario' ? <InfoRow label="Rol en la app" value={persona.rol} /> : null}
            <Txt variant="caption">El nivel, el horario y el estado los administra el club.</Txt>
          </GlassCard>

          <SectionTitle>Cómo te habla el robot</SectionTitle>
          <GlassCard>
            <UnderlineField
              label="Cómo prefieres que el robot te hable"
              value={trato}
              onChangeText={setTrato}
              multiline
              maxLength={400}
              placeholder="Ej.: háblame de usted, llámame Sebas, respuestas cortas…"
            />
            <Txt variant="caption">
              Solo cambia el tono del saludo y las indicaciones; no cambia tus permisos ni a dónde puedes entrar.
            </Txt>
            {tratoMsg ? <Notice tone={tratoMsg.ok ? 'success' : 'danger'} title={tratoMsg.text} /> : null}
            <PillButton label="Guardar" icon="chatbubble-ellipses-outline" disabled={saving} onPress={() => void saveTrato()} />
          </GlassCard>

          <SectionTitle>Privacidad</SectionTitle>
          <GlassCard>
            <View style={styles.switchRow}>
              <View style={styles.flex}>
                <Txt variant="label">Reconocimiento facial en recepción</Txt>
                <Txt variant="caption">
                  Opcional. Es independiente del inicio de sesión de esta app, que no captura ni usa tu rostro. Si lo
                  retiras, el sistema borra tus huellas faciales; siempre puedes ingresar con tu QR.
                </Txt>
                {consent && persona.consentimiento_fecha ? (
                  <Txt variant="caption">Autorizado el {formatClubDateTime(persona.consentimiento_fecha)}</Txt>
                ) : null}
              </View>
              <Switch
                value={consent}
                disabled={saving}
                onValueChange={(v) => void toggleConsent(v)}
                accessibilityLabel="Consentimiento biométrico"
                trackColor={{ true: colors.goldLight, false: 'rgba(255,255,255,0.25)' }}
                thumbColor={colors.white}
              />
            </View>
            {message ? (
              <Notice tone={message.ok ? 'success' : 'danger'} title={message.text} />
            ) : null}
            <Txt variant="caption">
              La foto de registro para el reconocimiento se gestiona en recepción (pendiente en la app).
            </Txt>
          </GlassCard>
        </>
      ) : null}

      <PillButton
        label={session.status === 'demo' ? 'Salir de la demostración' : 'Cerrar sesión'}
        variant="outline"
        icon="log-out-outline"
        onPress={() => void signOut()}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  flex: { flex: 1, gap: 4 },
});
