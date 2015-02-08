$ErrorActionPreference = "Stop"

$sha1 = "65c29b06eb665ce202676332e8129ac48d613c61"

$path = "dist\v-magine\v-magine.exe"

& signtool.exe sign /sha1 $sha1 /t http://timestamp.verisign.com/scripts/timstamp.dll /v $path
if ($LastExitCode) { throw "signtool failed" }
