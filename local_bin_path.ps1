$value = Get-ItemProperty -Path HKCU:\Environment -Name Path
if (! ($value.Path.contains( $env:USERPROFILE + "\.local\bin"))) {
    $newpath = $value.Path += ";%USERPROFILE%\.local\bin"
    Set-ItemProperty -Path HKCU:\Environment -Name Path -Value $newpath
}