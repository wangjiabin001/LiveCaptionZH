Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile("D:\LiveCaptionZH\screen.png")
$rect = New-Object System.Drawing.Rectangle 150, 860, 1620, 150
$crop = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height
$g = [System.Drawing.Graphics]::FromImage($crop)
$g.DrawImage($src, (New-Object System.Drawing.Rectangle 0,0,$rect.Width,$rect.Height), $rect, [System.Drawing.GraphicsUnit]::Pixel)
$big = New-Object System.Drawing.Bitmap ($rect.Width), ($rect.Height*2)
$g2 = [System.Drawing.Graphics]::FromImage($big)
$g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g2.DrawImage($crop, 0, 0, $big.Width, $big.Height)
$big.Save("D:\LiveCaptionZH\screen-bottom.png", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $g2.Dispose(); $src.Dispose(); $crop.Dispose(); $big.Dispose()
Write-Output "cropped"