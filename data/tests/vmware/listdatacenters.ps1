Add-PSSnapIn vm*

$vcenter = $args[0]
$vuser = $args[1]
$vpassword = $args[2]

Connect-ViServer -Server $vcenter -User $vuser -Password $vpassword

Get-DataCenter | Select-Object Name | Export-CSV c:\vmware\dc.csv -notype
