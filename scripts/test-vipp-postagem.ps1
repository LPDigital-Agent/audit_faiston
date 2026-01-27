# test-vipp-postagem.ps1 - Test VIPP PostarObjeto API
# Run: .\scripts\test-vipp-postagem.ps1

# Faiston VIPP Credentials (Profile 9363)
$VIPP_USER = "onbiws"
$VIPP_TOKEN = "112233"
$VIPP_PERFIL = "9363"

Write-Host ""
Write-Host "========================================"
Write-Host "  VIPP PostarObjeto API Test"
Write-Host "========================================"
Write-Host ""

Write-Host "[1/2] Building request..." -ForegroundColor Yellow

$body = @{
    PerfilVipp = @{
        Usuario = $VIPP_USER
        Token = $VIPP_TOKEN
        IdPerfil = $VIPP_PERFIL
    }
    ContratoEct = @{
        NrContrato = ""
        CodigoAdministrativo = ""
        NrCartao = ""
    }
    Destinatario = @{
        Nome = "Teste Faiston NEXO"
        Endereco = "Av Paulista"
        Numero = "1000"
        Complemento = ""
        Bairro = "Bela Vista"
        Cidade = "Sao Paulo"
        UF = "SP"
        Cep = "01310100"
    }
    Volumes = @(
        @{
            Peso = "500"
            Altura = "10"
            Largura = "20"
            Comprimento = "30"
        }
    )
} | ConvertTo-Json -Depth 4

Write-Host "      [OK] Request built" -ForegroundColor Green

Write-Host "[2/2] Calling VIPP API..." -ForegroundColor Yellow

$url = "http://vpsrv.visualset.com.br/api/v1/middleware/PostarObjeto"

try {
    $response = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $body -TimeoutSec 30

    Write-Host "      [OK] Response received!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  POSTAGEM RESULT"
    Write-Host "========================================"

    Write-Host ""
    Write-Host "  STATUS: $($response.StatusPostagem)" -ForegroundColor $(if ($response.StatusPostagem -eq "Valida") { "Green" } else { "Red" })
    Write-Host ""

    # Volume details
    $vol = $response.Volumes[0]
    Write-Host "  --- ETIQUETA ---" -ForegroundColor Cyan
    Write-Host "  Tracking:        $($vol.Etiqueta)" -ForegroundColor White

    Write-Host ""
    Write-Host "  --- CUSTOS ---" -ForegroundColor Cyan
    Write-Host "  Tarifa Base:     R$ $($vol.ValorTarifa)" -ForegroundColor White
    Write-Host "  Adicionais:      R$ $($vol.ValorAdicionais)" -ForegroundColor White
    Write-Host "  Total Postagem:  R$ $($vol.ValorPostagem)" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "  --- ENTREGA ---" -ForegroundColor Cyan
    Write-Host "  Prazo:           $($vol.DiasUteisPrazo) dias uteis" -ForegroundColor White
    Write-Host "  Entrega Sabado:  $(if ($vol.StEntregaSabado -eq '1') { 'Sim' } else { 'Nao' })" -ForegroundColor White
    Write-Host "  Entrega Domic.:  $(if ($vol.StEntregaDomiciliar -eq '1') { 'Sim' } else { 'Nao' })" -ForegroundColor White

    Write-Host ""
    Write-Host "  --- VOLUME ---" -ForegroundColor Cyan
    Write-Host "  Peso:            $($vol.Peso) g" -ForegroundColor White
    Write-Host "  Dimensoes:       $($vol.Comprimento)x$($vol.Largura)x$($vol.Altura) cm" -ForegroundColor White

    # Servico
    if ($response.Servico.ServicoECT) {
        Write-Host ""
        Write-Host "  --- SERVICO ---" -ForegroundColor Cyan
        Write-Host "  Codigo ECT:      $($response.Servico.ServicoECT)" -ForegroundColor White
    }

    # Contrato
    if ($response.ContratoEct.NrContrato) {
        Write-Host ""
        Write-Host "  --- CONTRATO ---" -ForegroundColor Cyan
        Write-Host "  Nr Contrato:     $($response.ContratoEct.NrContrato)" -ForegroundColor White
        Write-Host "  Nr Cartao:       $($response.ContratoEct.NrCartao)" -ForegroundColor White
    }

    # Destinatario
    Write-Host ""
    Write-Host "  --- DESTINATARIO ---" -ForegroundColor Cyan
    Write-Host "  Nome:            $($response.Destinatario.Nome)" -ForegroundColor White
    Write-Host "  Endereco:        $($response.Destinatario.Endereco), $($response.Destinatario.Numero)" -ForegroundColor White
    Write-Host "  Cidade/UF:       $($response.Destinatario.Cidade)/$($response.Destinatario.UF)" -ForegroundColor White
    Write-Host "  CEP:             $($response.Destinatario.Cep)" -ForegroundColor White

    Write-Host ""
    Write-Host "========================================"
    Write-Host "  SUCCESS - Postagem created!" -ForegroundColor Green
    Write-Host "========================================"
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $errorBody = $_.ErrorDetails.Message

    Write-Host ""
    Write-Host "========================================"
    Write-Host "  VIPP API RESPONSE"
    Write-Host "========================================"
    Write-Host ""

    if ($errorBody) {
        try {
            $errorJson = $errorBody | ConvertFrom-Json

            if ($errorJson.ListaErros -and $errorJson.ListaErros.Count -gt 0) {
                Write-Host "  [OK] API Endpoint: REACHABLE" -ForegroundColor Green
                Write-Host "  [OK] Request Format: VALID JSON" -ForegroundColor Green
                Write-Host ""
                Write-Host "  Validation Errors:" -ForegroundColor Yellow
                foreach ($err in $errorJson.ListaErros) {
                    Write-Host "    - $($err.Campo): $($err.Descricao)" -ForegroundColor Gray
                }
                Write-Host ""
                Write-Host "========================================"
                Write-Host "  PARTIAL SUCCESS" -ForegroundColor Yellow
                Write-Host "  API is working, needs valid credentials"
                Write-Host "========================================"
            } else {
                Write-Host "  Error Response:" -ForegroundColor Red
                $errorJson | ConvertTo-Json -Depth 3
            }
        }
        catch {
            Write-Host "  Raw Error: $errorBody" -ForegroundColor Red
        }
    } else {
        Write-Host "  [FAIL] HTTP $statusCode" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
