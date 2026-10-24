# Recepción fija, todo desde este portátil: entra a PC2, revisa el robot, arranca el puente de voz y
# caras (puente_voz.py, sin movimiento) y abre el túnel del puerto 8766. Deja esta ventana abierta.
# Ctrl+C aquí (o cerrar la ventana) cierra el puente de voz. El robot no camina en ningún momento.
#
#   .\conectar_voz.ps1 -Usuario <usuario>             # por cable
#   .\conectar_voz.ps1 -Usuario <usuario> -PorWifi    # por la WiFi del robot
#
# Antes, una vez: .\desplegar.ps1 -Usuario <usuario>.
# Después, en otra ventana:  cd ..\simulation ; python recepcion_fija.py --supabase
param(
    [Parameter(Mandatory = $true)][string]$Usuario,
    [string]$Equipo = "10.0.1.41",
    [switch]$PorWifi,
    [string]$Salto = "192.168.88.88",
    [string]$UsuarioSalto = "",   # usuario del salto 192.168.88.88 si no es el mismo
    [string]$Carpeta = "aimdk/anfitrion_x2",
    [int]$Puerto = 8766
)
$ErrorActionPreference = "Stop"
if ($Equipo -eq "10.0.1.40") {
    throw "10.0.1.40 es la unidad de control de movimiento (PC1). El puente va en PC2 (10.0.1.41)."
}
$opciones = @("-t", "-L", "${Puerto}:127.0.0.1:$Puerto", "-o", "ExitOnForwardFailure=yes",
              "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=2", "-o", "ServerAliveCountMax=3")
if (-not $UsuarioSalto) { $UsuarioSalto = $Usuario }
if ($PorWifi) { $opciones += @("-J", "$UsuarioSalto@$Salto") }

Write-Host "== Entrando a $Usuario@$Equipo y arrancando el puente de voz y caras (sin movimiento)"
& ssh @opciones "$Usuario@$Equipo" "cd ~/$Carpeta && sed -i 's/\r$//' iniciar_puente.sh && bash iniciar_puente.sh --voz --puerto $Puerto"
Write-Host "== Puente de voz cerrado y túnel cerrado."
