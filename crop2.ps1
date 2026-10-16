Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile("D:\LiveCaptionZH\screen.png")
$rect = New-Object System.Drawing.Rectangle 0, 820, 1920, 260
$crop = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height
$g = [System.Drawing.Graphics]::FromImage($crop)
$g.DrawImage($src, (New-Object System.Drawing.Rectangle 0,0,$rect.Width,$rect.Height), $rect, [System.Drawing.GraphicsUnit]::Pixel)
$crop.Save("D:\LiveCaptionZH\overlay-test.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $src.Dispose(); $crop.Dispose()
Write-Output "cropped"