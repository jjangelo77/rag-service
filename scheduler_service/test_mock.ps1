# --- Teste completo do mock ---

$mockPort = 8081
$mockLifeplannerId = "mock_lp_1"
$mockClienteCelular = "123456789"
$mockOrganizerEmail = "organizador@empresa.com"
$mockAttendeeEmail = "cliente@exemplo.com"

Write-Host "=== Teste de Mock iniciado na porta $mockPort ==="

# --- Teste 1: Consultando slots ---
Write-Host "`n--- Consultando slots ---"
$slotsBody = @{
    date = "2025-10-08"
} | ConvertTo-Json

$slots = Invoke-RestMethod -Uri "http://127.0.0.1:$mockPort/agendar/slots/" `
                           -Method POST `
                           -ContentType "application/json" `
                           -Body $slotsBody
Write-Host ($slots | ConvertTo-Json -Depth 5)

# --- Teste 2: Criando agendamento ---
Write-Host "`n--- Criando agendamento ---"
$createBody = @{
    id_lifeplanner = $mockLifeplannerId
    cliente_celular = $mockClienteCelular
    summary = "Agendamento de Teste"
    description = "Agendamento de teste usando mock"
    start_time = "2025-10-08T14:00:00-03:00"
    end_time = "2025-10-08T15:00:00-03:00"
    organizer_email = $mockOrganizerEmail
    attendee_emails = @($mockAttendeeEmail)
} | ConvertTo-Json

$create = Invoke-RestMethod -Uri "http://127.0.0.1:$mockPort/agendar/" `
                            -Method POST `
                            -ContentType "application/json" `
                            -Body $createBody
Write-Host ($create | ConvertTo-Json -Depth 5)

# --- Teste 3: Reagendar ---
Write-Host "`n--- Reagendando ---"
$rescheduleBody = @{
    id_lifeplanner = $mockLifeplannerId
    cliente_celular = $mockClienteCelular
    new_start_time = "2025-10-08T15:00:00-03:00"
    new_end_time = "2025-10-08T16:00:00-03:00"
} | ConvertTo-Json

$reschedule = Invoke-RestMethod -Uri "http://127.0.0.1:$mockPort/agendar/reagendar/" `
                                -Method POST `
                                -ContentType "application/json" `
                                -Body $rescheduleBody
Write-Host ($reschedule | ConvertTo-Json -Depth 5)

# --- Teste 4: Cancelar ---
Write-Host "`n--- Cancelando ---"
$cancelBody = @{
    id_lifeplanner = $mockLifeplannerId
    cliente_celular = $mockClienteCelular
} | ConvertTo-Json

$cancel = Invoke-RestMethod -Uri "http://127.0.0.1:$mockPort/agendar/cancelar/" `
                            -Method POST `
                            -ContentType "application/json" `
                            -Body $cancelBody
Write-Host ($cancel | ConvertTo-Json -Depth 5)

Write-Host "`n=== Teste completo finalizado ==="
