Param(
  [string]$SignX509Thumbprint
)
$ErrorActionPreference = "Stop"

$ENV:PATH += ";C:\Python27-v-magine;C:\Python27-v-magine\Scripts;"
$ENV:PATH += ";${ENV:ProgramFiles}\7-Zip"
$ENV:PATH += ";${ENV:ProgramFiles}\Git\bin"
$ENV:PATH += ";${ENV:ProgramFiles(x86)}\Windows Kits\8.1\bin\x64"
$ENV:PATH += ";C:\Qt\Qt5.4.0\5.4\msvc2013\bin"

# $version = $(& git.exe name-rev --name-only --tags HEAD)
# $zipPath = "v-magine_$($version -replace "\.","_").zip"
$zipPath = "v-magine.zip"

cd $PSScriptRoot

if (Test-Path "dist\v-magine") {
    del -Recurse -Force "dist\v-magine"
}

& pyinstaller.exe --noconfirm --log-level=WARN --onedir v-magine.spec
if ($LastExitCode) { throw "pyinstaller failed" }

& xcopy.exe /S /E /Y www dist\v-magine\www\
if ($LastExitCode) { throw "xcopy failed" }

& xcopy.exe /S /E /Y pxe dist\v-magine\pxe\
if ($LastExitCode) { throw "xcopy failed" }

& xcopy.exe /S /E /Y resources dist\v-magine\resources\
if ($LastExitCode) { throw "xcopy failed" }

& xcopy.exe /S /E /Y bin dist\v-magine\bin\
if ($LastExitCode) { throw "xcopy failed" }

del "dist\v-magine\*d.dll"
del -Recurse -Force "dist\v-magine\qml"

if ($SignX509Thumbprint -ne "")
{
    $path = "dist\v-magine\v-magine.exe"
    & signtool.exe sign /sha1 $SignX509Thumbprint /t http://timestamp.verisign.com/scripts/timstamp.dll /v $path
    if ($LastExitCode) { throw "signtool failed" }
}

pushd dist
try
{
    if (Test-Path "$zipPath") {
        del "$zipPath"
    }

    & 7z.exe a "$zipPath" v-magine
    if ($LastExitCode) { throw "7z failed" }
}
finally
{
    popd
}

echo "dist\${zipPath}"
