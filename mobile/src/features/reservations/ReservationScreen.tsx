import { Ionicons } from '@expo/vector-icons';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { ChipSelector } from '@/components/ChipSelector';
import { Badge, GlassCard, Notice, SectionTitle } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { EmptyView, ErrorView, LoadingView } from '@/components/StateViews';
import { Txt } from '@/components/Txt';
import { RESERVATION_RULES, SPACES, SPACES_ARE_PLACEHOLDERS, getSpace, type SpaceConfig } from '@/constants/spaces';
import { colors, radius, spacing } from '@/constants/theme';
import type { SessionState } from '@/features/auth/SessionProvider';
import { useAsync } from '@/hooks/useAsync';
import { formatDateLabel, formatMinutes, upcomingDates } from '@/utils/time';

import { reservationsRepositoryFor, type Reservation, type Slot } from './repository';

type ReserveSession = Extract<SessionState, { status: 'real' | 'demo' }> & { profile: 'regular' | 'vip' };

const SLOT_REASON: Record<NonNullable<Slot['reason']>, string> = {
  ocupado: 'Ocupado',
  pasado: 'Ya pasó',
  tuya: 'Tu reserva',
};

export function ReservationScreen({ session }: { session: ReserveSession }) {
  const repo = useMemo(() => reservationsRepositoryFor(session), [session]);
  const rules = RESERVATION_RULES[session.profile];
  const [spaceKey, setSpaceKey] = useState<string | null>(null);
  const [date, setDate] = useState<string>(upcomingDates(1)[0]);
  const [start, setStart] = useState<number | null>(null);
  const [hours, setHours] = useState(1);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const loadSlots = useCallback(async () => {
    if (!repo.supported || !spaceKey) return [] as Slot[];
    return repo.slots(spaceKey, date);
  }, [repo, spaceKey, date]);
  const slots = useAsync(loadSlots, 'No se pudo consultar la disponibilidad.');

  const loadMine = useCallback(async () => (repo.supported ? repo.list() : ([] as Reservation[])), [repo]);
  const mine = useAsync(loadMine, 'No se pudieron cargar tus reservas.');

  const refresh = () => {
    void slots.reload();
    void mine.reload();
  };

  const resetSlot = () => {
    setStart(null);
    setHours(1);
  };
  const chooseSpace = (key: string) => {
    setSpaceKey(key);
    resetSlot();
  };
  const chooseDate = (d: string) => {
    setDate(d);
    resetSlot();
  };

  const space = getSpace(spaceKey);
  const allowed = SPACES.filter((s) => s.reservableBy.includes(session.profile));
  const locked = SPACES.filter((s) => s.reservableBy.length > 0 && !s.reservableBy.includes(session.profile));

  // Duraciones posibles: horas seguidas libres desde el inicio elegido, hasta el máximo del plan.
  const durationOptions = useMemo(() => {
    if (start === null || slots.state.status !== 'success' || !rules) return [];
    const list = slots.state.data;
    const out: number[] = [];
    for (let h = 1; h <= rules.maxHoursPerBooking; h++) {
      const slot = list.find((s) => s.startMinutes === start + (h - 1) * 60);
      if (!slot?.available) break;
      out.push(h);
    }
    return out;
  }, [start, slots.state, rules]);

  async function confirm() {
    if (!repo.supported || !spaceKey || start === null) return;
    setConfirming(true);
    setResult(null);
    const r = await repo.reserve(spaceKey, date, start, hours);
    setConfirming(false);
    if (r.ok) {
      setResult({
        ok: true,
        message: `${getSpace(spaceKey)?.name} · ${formatDateLabel(date)} · ${formatMinutes(start)}–${formatMinutes(start + hours * 60)}`,
      });
      setStart(null);
    } else {
      setResult({ ok: false, message: r.message });
    }
    refresh();
  }

  return (
    <Screen back title="Reservar espacio" dense>
      {repo.supported ? (
        <Notice
          tone="demo"
          icon="flask-outline"
          title="Disponibilidad simulada"
          message="Modo demostración: la reserva se guarda solo en este teléfono y no se registra en el club."
        />
      ) : (
        <Notice tone="warning" icon="construct-outline" title="Reservas pendientes de backend" message={repo.reason} />
      )}

      <SectionTitle right={<Badge label={session.profile === 'vip' ? 'PLAN VIP' : 'PLAN REGULAR'} tone="gold" />}>
        Espacios de tu plan
      </SectionTitle>
      <View style={styles.spaces}>
        {allowed.map((s) => (
          <SpaceCard key={s.key} space={s} selected={s.key === spaceKey} onPress={() => chooseSpace(s.key)} />
        ))}
        {locked.map((s) => (
          <SpaceCard key={s.key} space={s} locked />
        ))}
      </View>
      {SPACES_ARE_PLACEHOLDERS ? (
        <Txt variant="caption" align="center">
          Espacios de ejemplo configurables (src/constants/spaces.ts): aún no hay un catálogo real en la base.
        </Txt>
      ) : null}

      {repo.supported && space && rules ? (
        <GlassCard style={styles.booking}>
          <Txt variant="subtitle">{space.name}</Txt>
          <ChipSelector
            label="Fecha"
            options={upcomingDates(rules.maxAdvanceDays + 1).map((d) => ({ value: d, label: formatDateLabel(d) }))}
            value={date}
            onChange={chooseDate}
          />
          <Txt variant="label">Hora de inicio</Txt>
          {slots.state.status === 'loading' ? <LoadingView message="Consultando disponibilidad…" /> : null}
          {slots.state.status === 'error' ? <ErrorView message={slots.state.error} onRetry={() => void slots.reload()} /> : null}
          {slots.state.status === 'success' ? (
            slots.state.data.some((s) => s.available) ? (
              <ChipSelector
                layout="wrap"
                options={slots.state.data.map((s) => ({
                  value: s.startMinutes,
                  label: formatMinutes(s.startMinutes),
                  sublabel: s.available ? 'Libre' : SLOT_REASON[s.reason ?? 'ocupado'],
                  disabled: !s.available,
                }))}
                value={start}
                onChange={(v) => {
                  setStart(v);
                  setHours(1);
                }}
              />
            ) : (
              <EmptyView message="No hay franjas libres ese día." icon="calendar-clear-outline" />
            )
          ) : null}
          {start !== null && durationOptions.length > 0 ? (
            <ChipSelector
              label="Duración"
              options={durationOptions.map((h) => ({ value: h, label: `${h} h` }))}
              value={hours}
              onChange={setHours}
            />
          ) : null}
          <Txt variant="caption">
            Tu plan permite reservar hasta {rules.maxHoursPerBooking} h seguidas y con {rules.maxAdvanceDays} días de
            anticipación. Horas en hora de Colombia.
          </Txt>
          <PillButton
            label="Confirmar reserva"
            icon="checkmark"
            onPress={() => void confirm()}
            loading={confirming}
            disabled={start === null}
          />
        </GlassCard>
      ) : null}

      {result ? (
        <Notice
          tone={result.ok ? 'demo' : 'danger'}
          icon={result.ok ? 'checkmark-circle-outline' : 'alert-circle-outline'}
          title={result.ok ? 'Reserva de demostración guardada en este teléfono' : 'No se pudo reservar'}
          message={result.message}
        />
      ) : null}

      {repo.supported ? (
        <>
          <SectionTitle>Mis reservas (demo)</SectionTitle>
          <GlassCard>
            {mine.state.status === 'loading' ? <LoadingView /> : null}
            {mine.state.status === 'error' ? <ErrorView message={mine.state.error} onRetry={() => void mine.reload()} /> : null}
            {mine.state.status === 'success' && mine.state.data.length === 0 ? (
              <EmptyView message="Sin reservas próximas." icon="calendar-clear-outline" />
            ) : null}
            {mine.state.status === 'success'
              ? mine.state.data.map((r) => (
                  <View key={r.id} style={styles.reservation}>
                    <View style={styles.flex}>
                      <Txt variant="label">{getSpace(r.spaceKey)?.name ?? r.spaceKey}</Txt>
                      <Txt variant="caption">
                        {formatDateLabel(r.date)} · {formatMinutes(r.startMinutes)}–{formatMinutes(r.startMinutes + r.hours * 60)}
                      </Txt>
                    </View>
                    <PillButton
                      label="Cancelar"
                      variant="ghost"
                      style={styles.cancel}
                      onPress={async () => {
                        await repo.cancel(r.id);
                        refresh();
                      }}
                    />
                  </View>
                ))
              : null}
          </GlassCard>
        </>
      ) : null}
    </Screen>
  );
}

function SpaceCard({
  space,
  selected = false,
  locked = false,
  onPress,
}: {
  space: SpaceConfig;
  selected?: boolean;
  locked?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected, disabled: locked }}
      accessibilityLabel={locked ? `${space.name}, exclusivo VIP` : space.name}
      disabled={locked}
      onPress={onPress}
      style={[styles.space, selected && styles.spaceSelected, locked && styles.spaceLocked]}
    >
      <Ionicons name={locked ? 'lock-closed-outline' : space.icon} size={22} color={selected ? colors.ink : colors.white} />
      <View style={styles.flex}>
        <Txt variant="label" color={selected ? colors.ink : colors.white}>
          {space.name}
        </Txt>
        <Txt variant="caption" color={selected ? '#444' : colors.textMuted}>
          {locked ? 'Disponible con membresía VIP' : `${space.description} Capacidad ${space.capacity}.`}
        </Txt>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  spaces: { gap: spacing.sm },
  space: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glass,
  },
  spaceSelected: { backgroundColor: colors.white, borderColor: colors.white },
  spaceLocked: { opacity: 0.45 },
  flex: { flex: 1, gap: 2 },
  booking: { gap: spacing.md },
  reservation: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  cancel: { width: 'auto' },
});
