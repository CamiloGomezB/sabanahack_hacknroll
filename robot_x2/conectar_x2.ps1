# Todo desde este portátil, en una sola ventana: entra a PC2, revisa el robot, arranca el puente y abre
# el túnel del puerto 8765. Deja esta ventana abierta mientras manejas el robot.
# Ctrl+C aquí (o cerrar la ventana, o que se caiga la conexión) detiene el robot y cierra el puente.
#
#   .\conectar_x2.ps1 -Usuario <usuario>             # por cable
#   .\conectar_x2.ps1 -Usuario <usuario> -PorWifi    # por la WiFi del robot
#
# Antes, una vez: .\desplegar.ps1 -Usuario <usuario>.  Después, en otra ventana: python control_x2.py
param(
    [Parameter(Mandatory = $true)][string]$Usuario,
    [string]$Equipo = "10.0.1.41",
    [switch]$PorWifi,
    [string]$Salto = "192.168.88.88",
    [string]$UsuarioSalto = "",   # usuario del salto 192.168.88.88 si no es el mismo
    # Dentro de ~/aimdk: la única carpeta que ve el contenedor de desarrollo
    [string]$Carpeta = "aimdk/anfitrion_x2",
    [int]$Puerto = 8765
)
$ErrorActionPreference = "Stop"
if ($Equipo -eq "10.0.1.40") {
    throw "10.0.1.40 es la unidad de control de movimiento (PC1). El puente va en PC2 (10.0.1.41)."
}
# -t: terminal en el robot, para que Ctrl+C llegue al puente y lo cierre bien
$opciones = @("-t", "-L", "${Puerto}:127.0.0.1:$Puerto", "-o", "ExitOnForwardFailure=yes",
              "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=2", "-o", "ServerAliveCountMax=3")
if (-not $UsuarioSalto) { $UsuarioSalto = $Usuario }
if ($PorWifi) { $opciones += @("-J", "$UsuarioSalto@$Salto") }

Write-Host "== Entrando a $Usuario@$Equipo y arrancando el puente (robot quieto, nadie a menos de 1 m)"
& ssh @opciones "$Usuario@$Equipo" "cd ~/$Carpeta && bash iniciar_puente.sh --puerto $Puerto"
Write-Host "== Puente cerrado y túnel cerrado."
