function Invoke-AsCurrentUser {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param (
        [Parameter(Mandatory = $true, Position = 0)]
        [scriptblock]
        $ScriptBlock,

        [Parameter(Mandatory = $false, ValueFromPipeline = $true)]
        $InputObject,

        [Parameter(Mandatory = $false)]
        [switch]$NoWait,

        [Parameter(Mandatory = $false)]
        [switch]$UseWindowsPowerShell,

        [Parameter(Mandatory = $false)]
        [switch]$UseMicrosoftPowerShell,

        [Parameter(Mandatory = $false)]
        [switch]$NonElevatedSession,

        [Parameter(Mandatory = $false)]
        [switch]$Visible,

        [Parameter(Mandatory = $false)]
        [switch]$CacheToDisk,

        [Parameter(Mandatory = $false)]
        [switch]$CaptureOutput,

        [Parameter(Mandatory = $false)]
        [switch]$Breakaway,

        [switch]$ExpandStringVariables
    )

    begin {
        # If -InputObject is bound, we prepare to receive pipeline input.
        if ($PSBoundParameters.ContainsKey('InputObject')) {
            $private:pipelineInput = @()
        }
    }

    process {
        # Collect objects from the pipeline.
        if ($null -ne $private:pipelineInput) {
            $private:pipelineInput += $InputObject
        }
    }

    end {
        if (!("RunAsUser.ProcessExtensions" -as [type])) {
            Add-Type -TypeDefinition $script:source -Language CSharp
        }

        $privs = [RunAsUser.ProcessExtensions]::GetTokenPrivileges()['SeDelegateSessionUserImpersonatePrivilege']
        if (-not $privs -or ($privs -band [RunAsUser.PrivilegeAttributes]::Disabled)) {
            Write-Error -Message "Not running with correct privilege. You must run this script as system or have the SeDelegateSessionUserImpersonatePrivilege token."
            return
        }

        # Temporary files for pipeline data marshalling
        $inputDataPath = $null
        $outputDataPath = $null
        $tempScriptPath = $null
        $cleanupPaths = [System.Collections.Generic.List[string]]::new()

        try {
            $finalScriptBlock = $ScriptBlock
            $forceCacheToDisk = $false

            # If there is pipeline input, we must use a file-based approach.
            if ($null -ne $private:pipelineInput) {
                $forceCacheToDisk = $true
                $inputDataPath = [System.IO.Path]::GetTempFileName()
                $cleanupPaths.Add($inputDataPath)
                
                # Serialize pipeline objects to a temp file to pass them to the new process.
                $private:pipelineInput | Export-Clixml -Path $inputDataPath

                $userScript = $ScriptBlock.ToString()

                $wrapperScript = @"
`$pipelineInput = Import-Clixml -Path '$inputDataPath'
`$scriptBlock = {
$userScript
}
`$pipelineInput | & `$scriptBlock
"@
                # If output is captured, serialize it to another temp file.
                if ($CaptureOutput) {
                    $outputDataPath = [System.IO.Path]::GetTempFileName()
                    $cleanupPaths.Add($outputDataPath)
                    $wrapperScript = "($wrapperScript) | Export-Clixml -Path '$outputDataPath' -Depth 5"
                }
                
                $finalScriptBlock = [scriptblock]::Create($wrapperScript)
            }

            if ($ExpandStringVariables) {
                $finalScriptBlock = $ExecutionContext.InvokeCommand.ExpandString($finalScriptBlock)
            }

            $useCacheToDisk = $CacheToDisk -or $forceCacheToDisk
            $pwshcommand = ''

            if ($useCacheToDisk) {
                $tempScriptPath = "$($ENV:TEMP)\$(New-Guid).ps1"
                $cleanupPaths.Add($tempScriptPath)
                $null = New-Item -Path $tempScriptPath -Value $finalScriptBlock -Force
                $pwshcommand = "-ExecutionPolicy Bypass -Window Normal -File `"$tempScriptPath`""
            }
            else {
                $encodedcommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($finalScriptBlock.ToString()))
                $pwshcommand = "-ExecutionPolicy Bypass -Window Normal -EncodedCommand $($encodedcommand)"
                
                $OSLevel = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentVersion
                if ($OSLevel -lt 6.2) { $MaxLength = 8190 } else { $MaxLength = 32767 }
                if ($encodedcommand.length -gt $MaxLength) {
                    Write-Error -Message "The encoded script is longer than the command line parameter limit. Please execute the script with the -CacheToDisk option."
                    return
                }
            }

            if ($UseMicrosoftPowerShell -and -not (Test-Path -Path "$env:ProgramFiles\PowerShell\7\pwsh.exe")) {
                Write-Error -Message "Not able to find Microsoft PowerShell v7 (pwsh.exe). Ensure that it is installed on this system"
                return
            }

            # Use the same PowerShell executable as the one that invoked the function, Unless -UseWindowsPowerShell or -UseMicrosoftPowerShell is defined.
            $pwshPath = if ($UseWindowsPowerShell) { "$($ENV:windir)\system32\WindowsPowerShell\v1.0\powershell.exe" }
            elseif ($UseMicrosoftPowerShell) { "$($env:ProgramFiles)\PowerShell\7\pwsh.exe" }
            else { (Get-Process -Id $pid).Path }

            if ($NoWait) { $ProcWaitTime = 1 } else { $ProcWaitTime = -1 }
            if ($NonElevatedSession) { $RunAsAdmin = $false } else { $RunAsAdmin = $true }
            
            # When capturing output with pipeline, the C# method should not capture it, we do it ourselves.
            $nativeCaptureOutput = $CaptureOutput -and ($null -eq $private:pipelineInput)

            $processOutput = [RunAsUser.ProcessExtensions]::StartProcessAsCurrentUser(
                $pwshPath, "`"$pwshPath`" $pwshcommand",
                (Split-Path $pwshPath -Parent), $Visible, $ProcWaitTime, $RunAsAdmin, $nativeCaptureOutput, $Breakaway )

            if ($CaptureOutput) {
                if ($outputDataPath -and (Test-Path $outputDataPath) -and (Get-Item $outputDataPath).Length -gt 0) {
                    # Deserialize the result from the temp file and write to pipeline.
                    Import-Clixml -Path $outputDataPath | Write-Output
                }
                elseif ($nativeCaptureOutput) {
                    # Legacy behavior for non-pipeline output capture.
                    Write-Output $processOutput
                }
            }
        }
        catch {
            Write-Error -Message "Could not execute as currently logged on user: $($_.Exception.Message)" -Exception $_.Exception
        }
        finally {
            # Clean up all temporary files.
            foreach ($path in $cleanupPaths) {
                if (Test-Path $path) {
                    Remove-Item $path -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }
}
