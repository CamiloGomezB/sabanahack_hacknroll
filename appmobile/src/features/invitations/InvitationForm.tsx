import { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ChipSelector, type ChipOption } from '@/components/ChipSelector';
import { Notice } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Txt } from '@/components/Txt';
import { UnderlineField } from '@/components/UnderlineField';
import type { ProfileKind } from '@/constants/profiles';
import { invitableSpacesFor, SPACES } from '@/constants/spaces';
import { spacing } from '@/constants/theme';
import type { PassCategory } from '@/features/temporary-access/pass';
import { clubDateString, clubMinutesOfDay, clubToUtc, formatDateLabel, formatMinutes, upcomingDates } from '@/utils/time';
import { hasErrors, type FieldErrors } from '@/utils/validation';

import type { InvitationInput } from './service';
import { MAX_ADVANCE_DAYS, VISIT_HOURS, validateInvitation, type InvitationField, type InvitationFormValues } from './validation';

const STEP = 30;

interface InvitationFormProps {
  categoria: PassCategory;
  profile: ProfileKind;
  submitting: boolean;
  submitError: string | null;
  onSubmit: (input: InvitationInput) => void;
}

/** Formulario del PDF ("Nombre", "E-mail", "Confirmar invitación") más destino y vigencia. */
export function InvitationForm({ categoria, profile, submitting, submitError, onSubmit }: InvitationFormProps) {
  const externo = categoria === 'externo';
  const [values, setValues] = useState<InvitationFormValues>({
    nombre: '',
    email: '',
    destino: '',
    empresa: '',
    motivo: '',
    date: clubDateString(),
    startMinutes: null,
    endMinutes: null,
  });
  const [errors, setErrors] = useState<FieldErrors<InvitationField>>({});

  const set = <K extends keyof InvitationFormValues>(key: K, value: InvitationFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  const spaces = externo ? SPACES : invitableSpacesFor(profile);
  const hours = VISIT_HOURS[categoria];

  const dateOptions: ChipOption<string>[] = useMemo(
    () =>
      upcomingDates(14).map((d, i) => ({
        value: d,
        label: i === 0 ? 'Hoy' : i === 1 ? 'Mañana' : formatDateLabel(d),
      })),
    [],
  );

  const startOptions: ChipOption<number>[] = useMemo(() => {
    const today = values.date === clubDateString();
    const nowMin = clubMinutesOfDay();
    const out: ChipOption<number>[] = [];
    for (let m = hours.start; m < hours.end; m += STEP) {
      out.push({ value: m, label: formatMinutes(m), disabled: today && m + STEP <= nowMin });
    }
    return out;
  }, [values.date, hours]);

  const endOptions: ChipOption<number>[] = useMemo(() => {
    if (values.startMinutes === null) return [];
    const out: ChipOption<number>[] = [];
    for (let m = values.startMinutes + STEP; m <= hours.end; m += STEP) out.push({ value: m, label: formatMinutes(m) });
    return out;
  }, [values.startMinutes, hours]);

  function submit() {
    const next = validateInvitation(categoria, values);
    setErrors(next);
    if (hasErrors(next) || !values.date || values.startMinutes === null || values.endMinutes === null) return;
    const now = Date.now();
    let inicio = clubToUtc(values.date, values.startMinutes);
    // Si la franja ya empezó, el acceso arranca ahora (la credencial no puede empezar en el pasado útil).
    if (inicio.getTime() < now) inicio = new Date(now);
    onSubmit({
      categoria,
      nombre: values.nombre,
      email: values.email,
      destino: values.destino,
      inicio,
      fin: clubToUtc(values.date, values.endMinutes),
      empresa: externo ? values.empresa : null,
      motivo: externo ? values.motivo : null,
    });
  }

  return (
    <View style={styles.form}>
      <UnderlineField
        label="Nombre"
        value={values.nombre}
        onChangeText={(t) => set('nombre', t)}
        autoComplete="off"
        error={errors.nombre}
      />
      <UnderlineField
        label="E-mail"
        value={values.email}
        onChangeText={(t) => set('email', t)}
        autoCapitalize="none"
        keyboardType="email-address"
        error={errors.email}
      />
      {externo ? (
        <>
          <UnderlineField label="Empresa" value={values.empresa} onChangeText={(t) => set('empresa', t)} error={errors.empresa} />
          <UnderlineField
            label="Servicio a realizar"
            value={values.motivo}
            onChangeText={(t) => set('motivo', t)}
            multiline
            error={errors.motivo}
          />
        </>
      ) : null}

      <ChipSelector
        label={externo ? 'Área del servicio' : 'Destino autorizado'}
        layout="wrap"
        options={spaces.map((s) => ({ value: s.key, label: s.name }))}
        value={values.destino || null}
        onChange={(v) => set('destino', v)}
        error={errors.destino}
      />
      <ChipSelector
        label="Fecha"
        options={dateOptions}
        value={values.date}
        onChange={(v) => setValues((s) => ({ ...s, date: v, startMinutes: null, endMinutes: null }))}
        error={errors.date}
      />
      <ChipSelector
        label="Desde"
        options={startOptions}
        value={values.startMinutes}
        onChange={(v) =>
          setValues((s) => ({ ...s, startMinutes: v, endMinutes: s.endMinutes !== null && s.endMinutes > v ? s.endMinutes : null }))
        }
      />
      {values.startMinutes !== null ? (
        <ChipSelector label="Hasta" options={endOptions} value={values.endMinutes} onChange={(v) => set('endMinutes', v)} />
      ) : null}
      {errors.window ? (
        <Txt variant="caption" color="#ff8a80">
          {errors.window}
        </Txt>
      ) : null}
      <Txt variant="caption">
        Horario permitido: {formatMinutes(hours.start)} – {formatMinutes(hours.end)} (hora de Colombia). Puedes invitar
        con hasta {Math.min(14, MAX_ADVANCE_DAYS)} días de anticipación.
      </Txt>

      {submitError ? <Notice tone="danger" icon="alert-circle-outline" title={submitError} /> : null}
      <PillButton
        label={externo ? 'Registrar acceso' : 'Confirmar invitación'}
        onPress={submit}
        loading={submitting}
        style={styles.submit}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing.lg, paddingHorizontal: spacing.xs },
  submit: { marginTop: spacing.sm },
});
