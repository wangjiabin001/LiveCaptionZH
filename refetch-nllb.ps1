param([string]$Url, [string]$Out, [long]$Expect, [int]$Rounds = 90)
for ($try = 1; $try -le 3; $try++) {
  Write-Host ("=== attempt " + $try + " ===")
  if ($try -gt 1) { if (Test-Path $Out) { Remove-Item -LiteralPath $Out -Force } }
  for ($i = 1; $i -le $Rounds; $i++) {
    $cur = 0; if (Test-Path $Out) { $cur = (Get-Item $Out).Length }
    if ($cur -ge $Expect) { break }
    Write-Host ("  round " + $i + "  " + [math]::Round($cur/1MB) + "/" + [math]::Round($Expect/1MB) + " MB")
    curl.exe -L -C - -s -o $Out --max-time 240 --speed-time 20 --speed-limit 30720 --retry 2 "$Url"
  }
  $cur = 0; if (Test-Path $Out) { $cur = (Get-Item $Out).Length }
  if ($cur -ge $Expect) {
    Write-Host "  size ok, validating model ..."
    $ok = & "D:\LiveCaptionZH\.venv\Scripts\python.exe" -c "import ctranslate2; ctranslate2.Translator(r'D:\LiveCaptionZH\nllb-200-distilled-600M-ctranslate2'); print('VALID')" 2>&1
    if ($ok -match 'VALID') { Write-Host "  OK model is valid"; exit 0 }
    Write-Host ("  INVALID: " + $ok)
  } else {
    Write-Host ("  incomplete " + [math]::Round($cur/1MB) + " MB")
  }
}
Write-Host "failed after retries"
exit 1