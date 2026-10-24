import { router } from 'expo-router';
import { useState } from 'react';
import { Share, StyleSheet, View } from 'react-native';

import { ChipSelector } from '@/components/ChipSelector';
import { GlassCard, Notice, SectionTitle } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { UnderlineField } from '@/components/UnderlineField';
import { SPACES } from '@/constants/spaces';
import { spacing } from '@/constants/theme';
import { formatDateLabel, upcomingDates } from '@/utils/time';
import { hasErrors, type FieldErrors } from '@/utils/validation';

import {
  SERVICE_TYPES,
  requestSummary,
  validateExternalRequest,
  type ExternalRequestField,
  type ExternalRequestValues,
} from './externalRequest';

const EMPTY: ExternalRequestValues = { serviceType: '', description: '', area: '', date: null, workers: '1', provider: '' };

export function ExternalServiceScreen({ requester }: { requester: string }) {
  const [values, setValues] = useState<ExternalRequestValues>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors<ExternalRequestField>>({});
  const [prepared, setPrepared] = useState<string | null>(null);

  const set = <K extends keyof ExternalRequestValues>(key: K, value: ExternalRequestValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  function submit() {
    const next = validateExternalRequest(values);
    setErrors(next);
    if (hasErrors(next)) return;
    setPrepared(requestSummary(values, requester));
  }

  return (
    <Screen back title="Equipo de trabajo externo" dense>
      <SectionTitle>Acceso de un trabajador</SectionTitle>
      <GlassCard>
        <Txt variant="body">
          Si el proveedor ya está acordado, registra el acceso temporal de cada trabajador con su empresa, área y
          vigencia. Se guarda en N Club y genera su QR.
        </Txt>
        <PillButton
          label="Registrar acceso externo"
          icon="id-card-outline"
          onPress={() => router.push({ pathname: '/invitar', params: { tipo: 'externo' } })}
        />
      </GlassCard>

      <SectionTitle>Consultar o solicitar un servicio</SectionTitle>
      <Notice
        tone="warning"
        icon="construct-outline"
        title="Contratación pendiente de backend"
        message="El sistema no tiene un proceso de contratación. Esta consulta prepara la solicitud para enviarla a administración, pero no contrata ni registra nada."
      />

      {prepared ? (
        <GlassCard>
          <Txt variant="subtitle">Solicitud preparada (no enviada)</Txt>
          <Txt variant="caption" selectable>
            {prepared}
          </Txt>
          <PillButton
            label="Compartir con administración"
            icon="share-outline"
            onPress={() => void Share.share({ message: prepared }).catch(() => undefined)}
          />
          <PillButton
            label="Nueva consulta"
            variant="ghost"
            onPress={() => {
              setPrepared(null);
              setValues(EMPTY);
            }}
          />
        </GlassCard>
      ) : (
        <View style={styles.form}>
          <ChipSelector
            label="Servicio requerido"
            layout="wrap"
            options={SERVICE_TYPES.map((t) => ({ value: t, label: t }))}
            value={values.serviceType || null}
            onChange={(v) => set('serviceType', v)}
            error={errors.serviceType}
          />
          <UnderlineField
            label="Descripción del trabajo"
            value={values.description}
            onChangeText={(t) => set('description', t)}
            multiline
            error={errors.description}
          />
          <ChipSelector
            label="Área del servicio"
            layout="wrap"
            options={SPACES.map((s) => ({ value: s.key, label: s.name }))}
            value={values.area || null}
            onChange={(v) => set('area', v)}
            error={errors.area}
          />
          <ChipSelector
            label="Fecha requerida"
            options={upcomingDates(21).map((d, i) => ({ value: d, label: i === 0 ? 'Hoy' : formatDateLabel(d) }))}
            value={values.date}
            onChange={(v) => set('date', v)}
            error={errors.date}
          />
          <UnderlineField
            label="Número de trabajadores"
            value={values.workers}
            onChangeText={(t) => set('workers', t.replace(/[^0-9]/g, ''))}
            keyboardType="number-pad"
            error={errors.workers}
          />
          <UnderlineField
            label="Proveedor sugerido (opcional)"
            value={values.provider}
            onChangeText={(t) => set('provider', t)}
          />
          <PillButton label="Preparar solicitud" onPress={submit} />
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing.lg, paddingHorizontal: spacing.xs },
});
