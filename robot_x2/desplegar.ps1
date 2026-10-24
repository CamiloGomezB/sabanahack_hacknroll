# Copia el puente a la unidad de desarrollo del X2 Ultra (PC2) y revisa que allá esté todo listo.
# No instala nada en el robot. La contraseña la pide ssh en esta misma ventana; no se guarda en ningún lado.
#
#   .\desplegar.ps1 -Usuario <usuario>                 # por cable (portátil en 10.0.1.2/24)
#   .\desplegar.ps1 -Usuario <usuario> -PorWifi        # por la red WiFi del robot (salta por 192.168.88.88)
#
# Si Windows no deja correr scripts:  powershell -ExecutionPolicy Bypass -File .\desplegar.ps1 -Usuario <usuario>
param(
    [Parameter(Mandatory = $true)][string]$Usuario,
    [string]$Equipo = "10.0.1.41",
    [switch]$PorWifi,
    [string]$Salto = "192.168.88.88",
    [string]$UsuarioSalto = "",   # usuario del salto 192.168.88.88 si no es el mismo
    # Dentro de ~/aimdk: la única carpeta que ve el contenedor de desarrollo
    [string]$Carpeta = "aimdk/anfitrion_x2"
)
$ErrorActionPreference = "Stop"
if ($Equipo -eq "10.0.1.40") {
    throw "10.0.1.40 es la unidad de control de movimiento (PC1): AgiBot prohíbe tocarla. El puente va en PC2 (10.0.1.41)."
}

$aqui = $PSScriptRoot
$destino = "$Usuario@$Equipo"
$opciones = @("-o", "ConnectTimeout=10")
if (-not $UsuarioSalto) { $UsuarioSalto = $Usuario }
if ($PorWifi) { $opciones += @("-J", "$UsuarioSalto@$Salto") }

Write-Host "== Copiando el puente a ${destino}:~/$Carpeta"
& ssh @opciones $destino "mkdir -p ~/$Carpeta"
if ($LASTEXITCODE -ne 0) { throw "No se pudo entrar a $destino (¿cable o WiFi conectado, usuario correcto?)." }
& scp @opciones -r "$aqui\puente_x2.py" "$aqui\puente_voz.py" "$aqui\iniciar_puente.sh" "$aqui\contenedor" "${destino}:~/$Carpeta/"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron copiar los archivos." }

Write-Host "== Revisando el robot (sin arrancar nada)"
& ssh @opciones $destino "cd ~/$Carpeta && sed -i 's/\r$//' iniciar_puente.sh *.py contenedor/* && bash iniciar_puente.sh --revisar"
if ($LASTEXITCODE -ne 0) {
    Write-Host "La revisión encontró problemas: el puente NO está listo. Mira los FALLA de arriba."
    exit 1
}
$red = if ($PorWifi) { " -PorWifi -UsuarioSalto $UsuarioSalto" } else { "" }
Write-Host ""
Write-Host "Recepción fija (solo voz y caras, sin movimiento):  .\conectar_voz.ps1 -Usuario $Usuario$red"
Write-Host "  y en otra ventana:  cd ..\simulation ; python recepcion_fija.py --supabase --voz audio"
Write-Host "Con movimiento, con el robot quieto:  .\conectar_x2.ps1 -Usuario $Usuario$red"
Write-Host "  y en otra ventana:  python control_x2.py"
