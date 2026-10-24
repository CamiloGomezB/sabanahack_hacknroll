// Edge Function: le manda al invitado o al trabajador externo un correo con su pase (el mismo
// código QR que ve el anfitrión en la app, formato "NC1." + JSON en base64url). No decide nada de
// acceso: registrar_llegada() en el servidor vuelve a validar el token al escanearlo.
//
// La llama la app justo después de crear_invitacion(), con el token en texto plano (solo existe en
// ese momento: la base solo guarda su hash). Antes de enviar nada, confirma contra la base que
// quien llama es el anfitrión o responsable de esa visita y que el token corresponde a su
// credencial — así nadie puede usar esta función para mandar correos con datos inventados.
//
// Variables de entorno:
//   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY: las pone Supabase automáticamente.
//   RESEND_API_KEY (obligatoria): clave de Resend (resend.com). Se configura con
//     `supabase secrets set RESEND_API_KEY=... --project-ref <ref>`, nunca en el código.
//   RESEND_FROM (opcional): remitente, por ejemplo "N Club <invitaciones@tudominio.com>". Sin
//     dominio propio verificado en Resend, usa "onboarding@resend.dev", que es solo para pruebas:
//     entrega únicamente al correo del dueño de la cuenta de Resend.

import { createClient } from "npm:@supabase/supabase-js@2.49.2";
import QRCode from "npm:qrcode@1.5.4";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

interface Body {
  visitaId: string;
  token: string;
  email: string;
  nombre: string;
  anfitrion: string;
  destino: string;
  destinoNombre: string;
  categoria: "invitado" | "externo";
  empresa: string | null;
  motivo: string | null;
  desde: string;
  hasta: string;
}

function isBody(x: unknown): x is Body {
  if (!x || typeof x !== "object") return false;
  const b = x as Record<string, unknown>;
  return (
    typeof b.visitaId === "string" && b.visitaId.length > 0 &&
    typeof b.token === "string" && /^[0-9a-f]{64}$/.test(b.token) &&
    typeof b.email === "string" && b.email.includes("@") &&
    typeof b.nombre === "string" && b.nombre.trim().length > 0 &&
    typeof b.anfitrion === "string" &&
    typeof b.destino === "string" &&
    typeof b.destinoNombre === "string" &&
    (b.categoria === "invitado" || b.categoria === "externo") &&
    (b.empresa === null || typeof b.empresa === "string") &&
    (b.motivo === null || typeof b.motivo === "string") &&
    typeof b.desde === "string" && !Number.isNaN(Date.parse(b.desde)) &&
    typeof b.hasta === "string" && !Number.isNaN(Date.parse(b.hasta))
  );
}

async function sha256Hex(texto: string): Promise<string> {
  const bytes = new TextEncoder().encode(texto);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Mismo formato que appmobile/src/features/temporary-access/pass.ts: encodePassCode. */
function encodePassCode(pass: Record<string, unknown>): string {
  const bytes = new TextEncoder().encode(JSON.stringify(pass));
  let binario = "";
  for (const b of bytes) binario += String.fromCharCode(b);
  const b64 = btoa(binario);
  return "NC1." + b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatRango(desde: string, hasta: string): string {
  const fmt = new Intl.DateTimeFormat("es-CO", {
    timeZone: "America/Bogota", day: "numeric", month: "long", hour: "numeric", minute: "2-digit",
  });
  const soloHora = new Intl.DateTimeFormat("es-CO", {
    timeZone: "America/Bogota", hour: "numeric", minute: "2-digit",
  });
  const d = new Date(desde), h = new Date(hasta);
  const mismoDia = d.toDateString() === h.toDateString();
  return mismoDia ? `${fmt.format(d)} – ${soloHora.format(h)}` : `${fmt.format(d)} – ${fmt.format(h)}`;
}

function emailHtml(o: {
  nombre: string; anfitrion: string; categoriaLabel: string; destinoNombre: string;
  empresaLinea: string; motivoLinea: string; rango: string;
}): string {
  return `<!doctype html>
<html lang="es">
  <body style="margin:0;padding:0;background:#f4f1ec;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;">
          <tr><td style="background:#14100b;padding:24px 32px;">
            <p style="margin:0;color:#e9c46a;font-size:13px;letter-spacing:2px;text-transform:uppercase;">N Club</p>
            <h1 style="margin:6px 0 0;color:#ffffff;font-size:20px;font-weight:600;">Tu pase de acceso</h1>
          </td></tr>
          <tr><td style="padding:28px 32px 8px;">
            <p style="margin:0 0 4px;color:#1d1a15;font-size:16px;">Hola ${escapeHtml(o.nombre)},</p>
            <p style="margin:0 0 16px;color:#4b4238;font-size:14px;line-height:1.5;">
              ${escapeHtml(o.anfitrion)} te invitó como ${o.categoriaLabel}${o.empresaLinea}. Muestra
              este código al X2 (el robot de recepción) cuando llegues.
            </p>
          </td></tr>
          <tr><td align="center" style="padding:8px 32px 24px;">
            <img src="cid:pase-qr" width="240" height="240" alt="Código QR de tu pase"
                 style="display:block;border-radius:12px;border:1px solid #e7e2d8;" />
          </td></tr>
          <tr><td style="padding:0 32px 8px;">
            <p style="margin:0 0 4px;color:#1d1a15;font-size:14px;"><strong>Punto de encuentro:</strong> ${escapeHtml(o.destinoNombre)}</p>
            <p style="margin:0 0 4px;color:#1d1a15;font-size:14px;"><strong>Vigencia:</strong> ${escapeHtml(o.rango)}</p>
            ${o.motivoLinea}
          </td></tr>
          <tr><td style="padding:16px 32px 28px;">
            <p style="margin:0;color:#8a8070;font-size:12px;line-height:1.5;">
              Este pase es personal e intransferible. Si no esperas esta invitación, ignora este correo.
            </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
  const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY");
  const RESEND_FROM = Deno.env.get("RESEND_FROM") ?? "N Club <onboarding@resend.dev>";

  if (!RESEND_API_KEY) {
    return json({ error: "sin_configurar", detalle: "Falta la variable RESEND_API_KEY." }, 500);
  }

  let cuerpo: unknown;
  try {
    cuerpo = await req.json();
  } catch {
    return json({ error: "json_invalido" }, 400);
  }
  if (!isBody(cuerpo)) return json({ error: "datos_invalidos" }, 400);

  // 1. Quién llama (el JWT del anfitrión que acaba de crear la invitación desde la app).
  const userClient = createClient(SUPABASE_URL, ANON_KEY, {
    global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
  });
  const { data: userData, error: userError } = await userClient.auth.getUser();
  if (userError || !userData?.user) return json({ error: "no_autenticado" }, 401);

  // 2. La visita y su responsable, con la clave de servicio (RLS no deja leer a nadie más).
  const admin = createClient(SUPABASE_URL, SERVICE_ROLE);
  const { data: visita } = await admin
    .from("visitas")
    .select("id, categoria, responsable_id")
    .eq("id", cuerpo.visitaId)
    .maybeSingle();
  if (!visita || visita.categoria !== cuerpo.categoria) {
    return json({ error: "visita_no_encontrada" }, 404);
  }
  const { data: responsable } = await admin
    .from("personas")
    .select("usuario_id")
    .eq("id", visita.responsable_id)
    .maybeSingle();
  if (!responsable || responsable.usuario_id !== userData.user.id) {
    return json({ error: "no_autorizado" }, 403);
  }

  // 3. El token que se va a mandar tiene que ser el mismo que quedó guardado (su hash) para esta
  //    visita: evita mandar un correo con un pase inventado.
  const tokenHash = await sha256Hex(cuerpo.token);
  const { data: credencial } = await admin
    .from("credenciales")
    .select("id")
    .eq("visita_id", cuerpo.visitaId)
    .eq("token_hash", tokenHash)
    .maybeSingle();
  if (!credencial) return json({ error: "token_no_coincide" }, 403);

  // 4. El pase (mismo formato que la app) y su QR.
  const pass = {
    v: 1, kind: "real", tipo: cuerpo.categoria, token: cuerpo.token, nombre: cuerpo.nombre.trim(),
    empresa: cuerpo.empresa, anfitrion: cuerpo.anfitrion, destino: cuerpo.destino,
    motivo: cuerpo.motivo, desde: cuerpo.desde, hasta: cuerpo.hasta, visitaId: cuerpo.visitaId,
  };
  const qrDataUrl: string = await QRCode.toDataURL(encodePassCode(pass), { margin: 1, width: 480 });
  const qrBase64 = qrDataUrl.split(",")[1] ?? "";

  const html = emailHtml({
    nombre: cuerpo.nombre.trim(),
    anfitrion: cuerpo.anfitrion,
    categoriaLabel: cuerpo.categoria === "externo" ? "trabajador externo" : "invitado",
    destinoNombre: cuerpo.destinoNombre,
    empresaLinea: cuerpo.empresa ? `, de ${cuerpo.empresa}` : "",
    motivoLinea: cuerpo.motivo
      ? `<p style="margin:0 0 4px;color:#4b4238;font-size:14px;">Motivo: ${escapeHtml(cuerpo.motivo)}</p>`
      : "",
    rango: formatRango(cuerpo.desde, cuerpo.hasta),
  });

  // 5. El envío (Resend). Si falla, se avisa a la app pero la invitación ya quedó creada: el
  //    anfitrión siempre puede compartir el pase manualmente.
  const resendResp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: RESEND_FROM,
      to: [cuerpo.email],
      subject: `Tu pase para N Club — ${cuerpo.destinoNombre}`,
      html,
      attachments: [{ filename: "pase-nclub.png", content: qrBase64, content_id: "pase-qr" }],
    }),
  });
  if (!resendResp.ok) {
    const detalle = await resendResp.text();
    console.error("Resend error", resendResp.status, detalle);
    return json({ error: "no_se_pudo_enviar", detalle }, 502);
  }
  const resendData = await resendResp.json();
  return json({ ok: true, id: resendData.id });
});
