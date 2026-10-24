# Panel web de recepción

Recepción es el **punto físico de atención humana** del lobby: ahí llega quien el robot no pudo
identificar o cuyo QR no sirve. Esta página es la herramienta del **operador** en ese punto, no un
paso que haga la persona que llega.

Lo que debe mostrar (todo existe ya en Supabase):

- Los casos pendientes de revisión con su motivo y evidencia (`eventos`), y la corrección con
  motivo (`corregir_evento`).
- Los avisos de llegada sin respuesta (`avisos` con estado `sin_respuesta`) para contactar al
  anfitrión o responsable.

Solo pueden usarla personas con `rol` operador o admin (las políticas RLS ya lo exigen).

Pendiente: construir o importar la página.
