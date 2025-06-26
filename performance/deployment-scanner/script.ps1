$PROFS = (Select-String -Path "$HOME\.aws\config" -Pattern "profile ").length
$CON=0
while ( $CON -lt $PROFS ) {
    $PROFILES = (Select-String -Path "$HOME\.aws\config" -Pattern "profile ")[$CON] |  ForEach-Object{([string]$_).Split("[")[1]} | ForEach-Object{([string]$_).Split("]")[0]} | ForEach-Object{([string]$_).Split(" ")[1]}
               Write-Output $PROFILES
    aws s3 ls --profile $PROFILES
    $CON = $CON + 1
}