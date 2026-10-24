import { useState } from 'react';

import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { useSession } from '@/features/auth/SessionProvider';
import { demoPass } from '@/features/demo/demoData';

import { AccessPassView } from './AccessPassView';
import type { AccessPass } from './pass';

/** Inicio de invitados y externos: solo su pase. No hay invitaciones ni reservas. */
export function GuestHome({ pass: initial }: { pass: AccessPass }) {
  const { signOut } = useSession();
  const [pass, setPass] = useState(initial);
  const demo = pass.kind === 'demo';

  return (
    <Screen background="table">
      <AccessPassView
        pass={pass}
        audience="guest"
        onSimulate={demo ? (status) => setPass({ ...demoPass(pass.tipo, status), nombre: pass.nombre }) : undefined}
        footer={
          <PillButton
            label={demo ? 'Salir de la demostración' : 'Quitar pase de este teléfono'}
            variant="ghost"
            onPress={() => void signOut()}
          />
        }
      />
    </Screen>
  );
}
