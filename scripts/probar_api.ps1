param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Email = "admin@admin.com",
    [string]$Password = "Admin123",
    [int]$Year = 2025,
    [string]$Code = "B50",
    [string]$OutDir = "./out"
)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Login..."
$body = @{ email=$Email; password=$Password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$BaseUrl/login" -Method POST -ContentType "application/json" -Body $body
$token = $login.access_token
if (-not $token) { throw "No se recibió access_token" }
Write-Host "Token OK"

$headers = @{ Authorization = "Bearer $token" }

Write-Host "GET /years"
$years = Invoke-RestMethod -Uri "$BaseUrl/years" -Headers $headers

Write-Host "GET /diseases?limit=5"
$diseases = Invoke-RestMethod -Uri "$BaseUrl/diseases?limit=5&offset=0" -Headers $headers

Write-Host "GET /map?year=$Year&code=$Code"
$map = Invoke-RestMethod -Uri "$BaseUrl/map?year=$Year&code=$Code" -Headers $headers

Write-Host "GET /top?year=$Year&code=$Code&metric=tia"
$top = Invoke-RestMethod -Uri "$BaseUrl/top?year=$Year&code=$Code&metric=tia&limit=5" -Headers $headers

Write-Host "GET /export?year=$Year&code=$Code&format=csv"
$csv = Invoke-RestMethod -Uri "$BaseUrl/export?year=$Year&code=$Code&format=csv" -Headers $headers

$bundle = [ordered]@{
    meta = [ordered]@{
        year = $Year
        code = $Code
        base_url = $BaseUrl
    }
    years = $years
    diseases = $diseases
    map = $map
    top = $top
    export_csv = $csv
}

$bundle | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutDir "resultado.json") -Encoding utf8

Write-Host "\nResumen:"
Write-Host "- Años:" ($years -join ", ")
Write-Host "- Diseases (first 5):" ($diseases | ForEach-Object { "$($_.code) - $($_.name)" } | Sort-Object | Out-String)
Write-Host "- Map features:" $map.features.Count
Write-Host "- Top count:" $top.Count
Write-Host "- CSV length:" $csv.Length

Write-Host "Logout..."
Invoke-RestMethod -Uri "$BaseUrl/logout" -Method POST -Headers $headers | Out-Host
Write-Host "Done. Archivo guardado en $OutDir\resultado.json"
