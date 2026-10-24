import type { ReactNode } from 'react';
import { Share, StyleSheet, View } from 'react-native';

import { ChipSelector } from '@/components/ChipSelector';
import { Badge, GlassCard, InfoRow, Notice } from '@/components/Card';
import { Logo } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { QrCard } from '@/components/QrCard';
import { Txt } from '@/components/Txt';
import { spaceName } from '@/constants/spaces';
import { spacing } from '@/constants/theme';
import { useNow } from '@/hooks/useNow';
import { formatClubDateTime, formatClubRange } from '@/utils/time';

import { PASS_STATUS_LABEL, encodePassCode, passStatus, type AccessPass, type PassStatus } from './pass';

const STATUS_TONE: Record<PassStatus, 'success' | 'warning' | 'danger'> = {
  vigente: 'success',
  pendiente: 'warning',
  vencido: 'danger',
};

interface AccessPassViewProps {
  pass: AccessPass;
  /** guest: lo ve el invitado / externo. host: lo ve quien lo emitió (puede compartirlo). */
  audience: 'guest' | 'host';
  /** Solo en demostración: permite simular los estados de vigencia. */
  onSimulate?: (status: PassStatus) => void;
  footer?: ReactNode;
}

/** Pantalla de acceso temporal compartida por invitados y trabajadores externos. */
export function AccessPassView({ pass, audience, onSimulate, footer }: AccessPassViewProps) {
  const now = useNow();
  const status = passStatus(pass, now);
  const externo = pass.tipo === 'externo';
  const demo = pass.kind === 'demo';

  async function share() {
    const code = encodePassCode(pass);
    await Share.share({
      message: [
        `Hola ${pass.nombre}, ${pass.anfitrion} ${externo ? 'autorizó tu acceso de servicio' : 'te invitó'} a N Club.`,
        `Destino: ${spaceName(pass.destino)}`,
        `Vigencia: ${formatClubRange(pass.desde, pass.hasta)} (hora de Colombia)`,
        '',
        'Abre la app N Club → "Tengo un pase de acceso" y pega este código:',
        code,
      ].join('\n'),
    }).catch(() => undefined);
  }

  return (
    <View style={styles.wrapper}>
      <Logo size={84} />
      <View style={styles.heading}>
        <Txt variant="overline" align="center">
          {externo ? 'ACCESO DE TRABAJADOR EXTERNO' : 'PASE DE INVITADO'}
        </Txt>
        <Txt variant="title" align="center">
          {pass.nombre}
        </Txt>
        <View style={styles.badges}>
          <Badge label={PASS_STATUS_LABEL[status]} tone={STATUS_TONE[status]} />
          {demo ? <Badge label="DEMO" tone="demo" /> : null}
        </View>
      </View>

      <QrCard
        value={pass.token}
        kind={pass.kind}
        inactiveLabel={status === 'vigente' ? null : status === 'pendiente' ? 'Aún no vigente' : 'Vencido'}
      />

      <GlassCard>
        <InfoRow label="Nombre" value={pass.nombre} />
        {externo ? <InfoRow label="Empresa" value={pass.empresa ?? '—'} /> : null}
        <InfoRow label={externo ? 'Autorizado por' : 'Invitado por'} value={pass.anfitrion} />
        <InfoRow label={externo ? 'Área del servicio' : 'Destino autorizado'} value={spaceName(pass.destino)} />
        {pass.motivo ? <InfoRow label="Servicio" value={pass.motivo} /> : null}
        <InfoRow label="Desde" value={formatClubDateTime(pass.desde)} />
        <InfoRow label="Hasta" value={formatClubDateTime(pass.hasta)} />
        <Txt variant="caption">Horas en hora de Colombia.</Txt>
      </GlassCard>

      {externo ? <ValidationState status={status} demo={demo} desde={pass.desde} /> : null}

      {onSimulate ? (
        <GlassCard>
          <ChipSelector
            label="Simular estado (solo demostración)"
            value={status}
            onChange={onSimulate}
            options={[
              { value: 'pendiente', label: 'Pendiente' },
              { value: 'vigente', label: 'Vigente' },
              { value: 'vencido', label: 'Vencido' },
            ]}
          />
        </GlassCard>
      ) : null}

      {audience === 'guest' ? (
        <Notice
          icon="shield-checkmark-outline"
          title={demo ? 'Pase de demostración' : 'Pase personal e intransferible'}
          message={
            demo
              ? 'Este QR es de ejemplo y no autoriza el ingreso.'
              : 'Solo sirve para el destino y el horario indicados. Desde un pase no se pueden crear invitaciones ni cambiar el nivel de acceso.'
          }
        />
      ) : (
        <View style={styles.hostActions}>
          {demo ? (
            <Notice tone="demo" icon="flask-outline" title="Invitación de demostración" message="No se registró en Supabase y su QR no autoriza el ingreso." />
          ) : (
            <Txt variant="caption" align="center">
              Comparte el código con {pass.nombre}. Por seguridad, la base solo guarda el hash del token: este teléfono
              es el único lugar donde queda el código.
            </Txt>
          )}
          <PillButton label="Compartir pase" icon="share-outline" onPress={() => void share()} disabled={status === 'vencido'} />
        </View>
      )}
      {footer}
    </View>
  );
}

function ValidationState({ status, demo, desde }: { status: PassStatus; demo: boolean; desde: string }) {
  const content: Record<PassStatus, { tone: 'success' | 'warning' | 'danger'; title: string; message: string }> = {
    pendiente: {
      tone: 'warning',
      title: 'Validación: pendiente de activación',
      message: `El QR empieza a funcionar el ${formatClubDateTime(desde)}.`,
    },
    vigente: {
      tone: 'success',
      title: 'Validación: listo para ingresar',
      message: 'Recepción valida el QR al llegar. El trabajador externo siempre ingresa acompañado.',
    },
    vencido: {
      tone: 'danger',
      title: 'Validación: acceso vencido',
      message: 'Solicita un nuevo acceso al personal del club.',
    },
  };
  const c = content[status];
  return (
    <Notice
      tone={demo ? 'demo' : c.tone}
      icon="checkmark-done-outline"
      title={c.title}
      message={demo ? `${c.message} (Estado simulado.)` : c.message}
    />
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.md, paddingTop: spacing.md },
  heading: { gap: spacing.xs, alignItems: 'center' },
  badges: { flexDirection: 'row', gap: spacing.sm, justifyContent: 'center', marginTop: spacing.xs },
  hostActions: { gap: spacing.sm },
});
