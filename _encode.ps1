$main = [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\Users\zhaox\Desktop\xiaozhi\main.py'), [System.Text.Encoding]::UTF8)
$html = [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\Users\zhaox\Desktop\xiaozhi\index.html'), [System.Text.Encoding]::UTF8)
$cfg = [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\Users\zhaox\Desktop\xiaozhi\config.json'), [System.Text.Encoding]::UTF8)

# Write base64 encoded files
[System.IO.File]::WriteAllText('C:\Users\zhaox\Desktop\xiaozhi\_main.b64', $main, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText('C:\Users\zhaox\Desktop\xiaozhi\_html.b64', $html, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText('C:\Users\zhaox\Desktop\xiaozhi\_cfg.b64', $cfg, [System.Text.UTF8Encoding]::new($false))

Write-Output "main_b64_len=$($main.Length)"
Write-Output "html_b64_len=$($html.Length)"
Write-Output "cfg_b64_len=$($cfg.Length)"
