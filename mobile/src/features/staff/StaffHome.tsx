import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Badge, GlassCard, Notice, SectionTitle } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { ProfileHeader } from '@/components/ProfileHeader';
import { Screen } from '@/components/Screen';
import { LoadingView } from '@/components/StateViews';
import { Txt } from '@/components/Txt';
import { colors, spacing } from '@/constants/theme';
import { canRegisterExternal } from '@/features/auth/permissions';
import type { SessionState } from '@/features/auth/SessionProvider';
import { MemberQrSection } from '@/features/memberships/MemberQrSection';
import { membershipStatus } from '@/features/memberships/status';
import { useNow } from '@/hooks/useNow';
import { memberCode } from '@/utils/format';

import { SHIFT_PHASE_LABEL, shiftFromPersona } from './shift';
import { useStaffTasks } from './useStaffTasks';

type StaffSession = Extract<SessionState, { status: 'real' | 'demo' }> & { profile: 'personal' };

export function StaffHome({ session }: { session: StaffSession }) {
  const persona = session.persona;
  const now = useNow();
  const { tasks, toggle, loading } = useStaffTasks(persona?.id ?? 'sin-persona');
  const [showQr, setShowQr] = useState(false);
  if (!persona) return null;

  const status = membershipStatus(persona);
  const shift = shiftFromPersona(persona, now);
  const completed = tasks.filter((t) => t.done).length;
  const roleLabel = persona.rol === 'usuario' ? 'Personal del club' : `Personal · ${persona.rol}`;

  return (
    <Screen background="table">
      <ProfileHeader
        name={persona.nombre_demo}
        badges={
          <>
            <Badge label={roleLabel.toUpperCase()} tone="gold" />
            <Badge label={status.active ? 'Vínculo activo' : 'Vínculo inactivo'} tone={status.active ? 'success' : 'danger'} />
          </>
        }
      />
      <Txt variant="caption" align="center">
        Código {memberCode('personal', persona.id)}
      </Txt>

      <SectionTitle>Jornada de hoy</SectionTitle>
      <GlassCard>
        {shift ? (
          <>
            <View style={styles.shiftRow}>
              <ShiftCell label="Inicio" value={shift.start} />
              <ShiftCell label="Fin" value={shift.end} />
              <ShiftCell label="Duración" value={shift.duration} />
            </View>
            <View style={styles.phase}>
              <Badge
                label={SHIFT_PHASE_LABEL[shift.phase]}
                tone={shift.phase === 'en_turno' ? 'success' : shift.phase === 'antes' ? 'warning' : 'neutral'}
              />
              <Txt variant="caption">Hora de Colombia</Txt>
            </View>
            <Txt variant="caption">
              {session.status === 'demo'
                ? 'Horario de demostración.'
                : 'Horario registrado por el club en tu perfil (personas.horario_inicio / horario_fin).'}
            </Txt>
          </>
        ) : (
          <Notice tone="warning" title="Sin horario asignado" message="El club aún no registra tu turno." />
        )}
      </GlassCard>

      <SectionTitle right={<Badge label="SIMULADO" tone="demo" />}>Tareas del día</SectionTitle>
      <GlassCard>
        {loading ? (
          <LoadingView />
        ) : (
          <>
            <Txt variant="caption">
              {completed} de {tasks.length} completadas
            </Txt>
            {tasks.map((t) => (
              <Pressable
                key={t.id}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: t.done }}
                accessibilityLabel={`${t.title}, ${t.done ? 'completada' : 'pendiente'}`}
                onPress={() => toggle(t.id)}
                style={styles.task}
              >
                <Ionicons
                  name={t.done ? 'checkmark-circle' : 'ellipse-outline'}
                  size={22}
                  color={t.done ? colors.success : colors.textMuted}
                />
                <View style={styles.taskText}>
                  <Txt variant="label" style={t.done ? styles.done : null}>
                    {t.title}
                  </Txt>
                  <Txt variant="caption">
                    {t.time} · {t.area}
                  </Txt>
                </View>
                <Badge label={t.done ? 'Completada' : 'Pendiente'} tone={t.done ? 'success' : 'warning'} />
              </Pressable>
            ))}
            <Txt variant="caption">
              No existe un modelo de tareas en la base de datos: son tareas de ejemplo y su estado se guarda solo en este
              teléfono.
            </Txt>
          </>
        )}
      </GlassCard>

      <View style={styles.actions}>
        <PillButton
          label="Equipo de trabajo externo"
          icon="construct-outline"
          onPress={() => router.push('/externos')}
          disabled={!canRegisterExternal(session)}
        />
        <PillButton label="Accesos registrados" variant="outline" icon="list-outline" onPress={() => router.push('/invitaciones')} />
        <PillButton
          label={showQr ? 'Ocultar mi QR de acceso' : 'Mostrar mi QR de acceso'}
          variant="ghost"
          onPress={() => setShowQr((v) => !v)}
        />
      </View>
      {showQr ? <MemberQrSection session={session} membershipActive={status.active} /> : null}
    </Screen>
  );
}

function ShiftCell({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.cell}>
      <Txt variant="caption">{label}</Txt>
      <Txt variant="subtitle">{value}</Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  shiftRow: { flexDirection: 'row', justifyContent: 'space-between' },
  cell: { flex: 1, alignItems: 'center', gap: 2 },
  phase: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, justifyContent: 'center' },
  task: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 6 },
  taskText: { flex: 1, gap: 1 },
  done: { textDecorationLine: 'line-through', opacity: 0.7 },
  actions: { gap: spacing.md, marginTop: spacing.sm },
});
