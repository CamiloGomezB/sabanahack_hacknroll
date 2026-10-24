import { router } from 'expo-router';
import { useCallback } from 'react';
import { StyleSheet, View } from 'react-native';

import { Badge, GlassCard, InfoRow, Notice, SectionTitle } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { ProfileHeader } from '@/components/ProfileHeader';
import { Screen } from '@/components/Screen';
import { EmptyView, ErrorView, LoadingView } from '@/components/StateViews';
import { Txt } from '@/components/Txt';
import { PROFILE_LABELS } from '@/constants/profiles';
import { reservableSpacesFor, spaceName } from '@/constants/spaces';
import { spacing } from '@/constants/theme';
import { canInviteGuests, canReserve } from '@/features/auth/permissions';
import type { SessionState } from '@/features/auth/SessionProvider';
import { invitationsServiceFor } from '@/features/invitations/service';
import { VISIT_STATE } from '@/features/invitations/visitState';
import { reservationsRepositoryFor } from '@/features/reservations/repository';
import { useAsync } from '@/hooks/useAsync';
import { memberCode } from '@/utils/format';
import { formatClock, formatClubRange, formatDateLabel, formatMinutes } from '@/utils/time';

import { MemberQrSection } from './MemberQrSection';
import { membershipStatus } from './status';

type MemberSession = Extract<SessionState, { status: 'real' | 'demo' }> & { profile: 'regular' | 'vip' };

/** Panel compartido por miembro regular y VIP; las diferencias salen de la configuración de espacios. */
export function MemberHome({ session }: { session: MemberSession }) {
  const persona = session.persona;
  if (!persona) return null;
  const vip = session.profile === 'vip';
  const status = membershipStatus(persona);

  return (
    <Screen background="table">
      <ProfileHeader
        name={persona.nombre_demo}
        badges={
          <>
            {vip ? <Badge label="NIVEL VIP" tone="gold" /> : null}
            <Badge label={`Membresía ${status.label.toLowerCase()}`} tone={status.active ? 'success' : 'danger'} />
          </>
        }
      />

      <MemberQrSection session={session} membershipActive={status.active} />

      <View style={styles.info}>
        <InfoRow label="Plan" value={PROFILE_LABELS[session.profile]} />
        <InfoRow label="Código ID" value={memberCode(session.profile, persona.id)} />
        <InfoRow label="Estado" value={status.detail ? `${status.label} · ${status.detail}` : status.label} />
        <InfoRow
          label="Horario de ingreso"
          value={`${formatClock(persona.horario_inicio)} – ${formatClock(persona.horario_fin)} (hora Colombia)`}
        />
      </View>

      <View style={styles.actions}>
        <PillButton
          label="Reservar espacio"
          icon="calendar-outline"
          onPress={() => router.push('/reservar')}
          disabled={!canReserve(session)}
        />
        <PillButton
          label="Invitar a alguien"
          icon="person-add-outline"
          onPress={() => router.push({ pathname: '/invitar', params: { tipo: 'invitado' } })}
          disabled={!canInviteGuests(session)}
        />
        {!status.active ? (
          <Txt variant="caption" align="center">
            Las invitaciones y reservas requieren una membresía activa.
          </Txt>
        ) : null}
        {!vip ? (
          <PillButton label="Ver mis invitaciones" variant="ghost" onPress={() => router.push('/invitaciones')} />
        ) : null}
      </View>

      {vip ? <VipSections session={session} /> : null}
    </Screen>
  );
}

function VipSections({ session }: { session: MemberSession }) {
  const loadInvitations = useCallback(async () => {
    const service = invitationsServiceFor(session);
    return service ? (await service.list()).slice(0, 3) : [];
  }, [session]);
  const loadReservations = useCallback(async () => {
    const repo = reservationsRepositoryFor(session);
    return repo.supported ? { supported: true as const, items: (await repo.list()).slice(0, 3) } : { supported: false as const, reason: repo.reason };
  }, [session]);
  const invitations = useAsync(loadInvitations, 'No se pudieron cargar tus invitaciones.');
  const reservations = useAsync(loadReservations, 'No se pudieron cargar tus reservas.');

  return (
    <View style={styles.sections}>
      <SectionTitle right={<PillButton label="Ver todas" variant="ghost" style={styles.inlineLink} onPress={() => router.push('/invitaciones')} />}>
        Invitaciones
      </SectionTitle>
      <GlassCard>
        {invitations.state.status === 'loading' ? <LoadingView /> : null}
        {invitations.state.status === 'error' ? (
          <ErrorView message={invitations.state.error} onRetry={() => void invitations.reload()} />
        ) : null}
        {invitations.state.status === 'success' && invitations.state.data.length === 0 ? (
          <EmptyView message="Aún no has invitado a nadie." icon="mail-open-outline" />
        ) : null}
        {invitations.state.status === 'success'
          ? invitations.state.data.map((inv) => (
              <View key={inv.id} style={styles.item}>
                <View style={styles.itemText}>
                  <Txt variant="label">{inv.nombre}</Txt>
                  <Txt variant="caption">
                    {spaceName(inv.destino)} · {formatClubRange(inv.inicio, inv.fin)}
                  </Txt>
                </View>
                <Badge label={VISIT_STATE[inv.estado].label} tone={VISIT_STATE[inv.estado].tone} />
              </View>
            ))
          : null}
      </GlassCard>

      <SectionTitle right={<PillButton label="Reservar" variant="ghost" style={styles.inlineLink} onPress={() => router.push('/reservar')} />}>
        Reservas
      </SectionTitle>
      <GlassCard>
        {reservations.state.status === 'loading' ? <LoadingView /> : null}
        {reservations.state.status === 'error' ? (
          <ErrorView message={reservations.state.error} onRetry={() => void reservations.reload()} />
        ) : null}
        {reservations.state.status === 'success' && !reservations.state.data.supported ? (
          <Notice tone="warning" icon="construct-outline" title="Pendiente de backend" message={reservations.state.data.reason} />
        ) : null}
        {reservations.state.status === 'success' && reservations.state.data.supported ? (
          reservations.state.data.items.length === 0 ? (
            <EmptyView message="No tienes reservas próximas." icon="calendar-clear-outline" />
          ) : (
            reservations.state.data.items.map((r) => (
              <View key={r.id} style={styles.item}>
                <View style={styles.itemText}>
                  <Txt variant="label">{spaceName(r.spaceKey)}</Txt>
                  <Txt variant="caption">
                    {formatDateLabel(r.date)} · {formatMinutes(r.startMinutes)}–{formatMinutes(r.startMinutes + r.hours * 60)}
                  </Txt>
                </View>
                <Badge label="DEMO" tone="demo" />
              </View>
            ))
          )
        ) : null}
      </GlassCard>

      <Txt variant="caption" align="center">
        Tu plan VIP incluye {reservableSpacesFor('vip').length} espacios reservables frente a{' '}
        {reservableSpacesFor('regular').length} del plan regular.
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  info: { gap: spacing.sm, paddingHorizontal: spacing.sm, marginTop: spacing.sm },
  actions: { gap: spacing.md, marginTop: spacing.sm },
  sections: { gap: spacing.sm },
  inlineLink: { width: 'auto', minHeight: 28, paddingHorizontal: 0 },
  item: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 4 },
  itemText: { flex: 1, gap: 2 },
});
