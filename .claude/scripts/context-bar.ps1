# Color theme: gray, orange, blue, teal, green, lavender, rose, gold, slate, cyan
$COLOR = "blue"

# Color codes
$C_RESET = "`e[0m"
$C_GRAY = "`e[38;5;245m"  # explicit gray for default text
$C_BAR_EMPTY = "`e[38;5;238m"

switch ($COLOR) {
    "orange"   { $C_ACCENT = "`e[38;5;173m" }
    "blue"     { $C_ACCENT = "`e[38;5;74m" }
    "teal"     { $C_ACCENT = "`e[38;5;66m" }
    "green"    { $C_ACCENT = "`e[38;5;71m" }
    "lavender" { $C_ACCENT = "`e[38;5;139m" }
    "rose"     { $C_ACCENT = "`e[38;5;132m" }
    "gold"     { $C_ACCENT = "`e[38;5;136m" }
    "slate"    { $C_ACCENT = "`e[38;5;60m" }
    "cyan"     { $C_ACCENT = "`e[38;5;37m" }
    default    { $C_ACCENT = $C_GRAY }  # gray: all same color
}

# Read JSON input from stdin
$input_data = [Console]::In.ReadToEnd() | ConvertFrom-Json

# Extract model, directory, and cwd
$model = if ($input_data.model.display_name) { $input_data.model.display_name }
         elseif ($input_data.model.id) { $input_data.model.id }
         else { "?" }

$cwd = $input_data.cwd
$dir = if ($cwd) { Split-Path $cwd -Leaf } else { "?" }

# Get git branch, uncommitted file count, and sync status
$branch = ""
$git_status = ""

if ($cwd -and (Test-Path $cwd)) {
    $branch = git -C $cwd branch --show-current 2>$null

    if ($branch) {
        # Count uncommitted files
        $status_output = git -C $cwd --no-optional-locks status --porcelain -uall 2>$null
        $file_count = if ($status_output) { ($status_output | Measure-Object -Line).Lines } else { 0 }

        # Check sync status with upstream
        $sync_status = ""
        $upstream = git -C $cwd rev-parse --abbrev-ref '@{upstream}' 2>$null

        if ($upstream) {
            # Get last fetch time
            $fetch_head = Join-Path $cwd ".git\FETCH_HEAD"
            $fetch_ago = ""

            if (Test-Path $fetch_head) {
                $fetch_time = (Get-Item $fetch_head).LastWriteTime
                $diff = (Get-Date) - $fetch_time
                $diff_seconds = [int]$diff.TotalSeconds

                if ($diff_seconds -lt 60) {
                    $fetch_ago = "<1m ago"
                } elseif ($diff_seconds -lt 3600) {
                    $fetch_ago = "$([int]($diff_seconds / 60))m ago"
                } elseif ($diff_seconds -lt 86400) {
                    $fetch_ago = "$([int]($diff_seconds / 3600))h ago"
                } else {
                    $fetch_ago = "$([int]($diff_seconds / 86400))d ago"
                }
            }

            $counts = git -C $cwd rev-list --left-right --count "HEAD...@{upstream}" 2>$null
            if ($counts) {
                $ahead, $behind = $counts -split "`t"
                $ahead = [int]$ahead
                $behind = [int]$behind

                if ($ahead -eq 0 -and $behind -eq 0) {
                    if ($fetch_ago) {
                        $sync_status = "synced $fetch_ago"
                    } else {
                        $sync_status = "synced"
                    }
                } elseif ($ahead -gt 0 -and $behind -eq 0) {
                    $sync_status = "$ahead ahead"
                } elseif ($ahead -eq 0 -and $behind -gt 0) {
                    $sync_status = "$behind behind"
                } else {
                    $sync_status = "$ahead ahead, $behind behind"
                }
            }
        } else {
            $sync_status = "no upstream"
        }

        # Build git status string
        if ($file_count -eq 0) {
            $git_status = "(0 files uncommitted, $sync_status)"
        } elseif ($file_count -eq 1) {
            # Show the actual filename when only one file is uncommitted
            $single_file = (git -C $cwd --no-optional-locks status --porcelain -uall 2>$null | Select-Object -First 1).Substring(3)
            $git_status = "($single_file uncommitted, $sync_status)"
        } else {
            $git_status = "($file_count files uncommitted, $sync_status)"
        }
    }
}

# Get transcript path for context calculation
$transcript_path = $input_data.transcript_path

# Get context window size from JSON
$max_context = if ($input_data.context_window.context_window_size) { $input_data.context_window.context_window_size } else { 200000 }
$max_k = [int]($max_context / 1000)

# Calculate context bar from transcript
$baseline = 20000
$bar_width = 10

if ($transcript_path -and (Test-Path $transcript_path)) {
    # Parse transcript JSON - it's a JSON Lines file, not a JSON array
    $lines = Get-Content $transcript_path
    $transcript = $lines | ForEach-Object { $_ | ConvertFrom-Json }
    $context_length = 0

    # Find the last message with usage data that's not a sidechain or API error
    $last_usage = $transcript | Where-Object {
        $_.message.usage -and
        $_.isSidechain -ne $true -and
        $_.isApiErrorMessage -ne $true
    } | Select-Object -Last 1

    if ($last_usage) {
        $usage = $last_usage.message.usage
        $input_tokens = if ($usage.input_tokens) { $usage.input_tokens } else { 0 }
        $cache_read = if ($usage.cache_read_input_tokens) { $usage.cache_read_input_tokens } else { 0 }
        $cache_creation = if ($usage.cache_creation_input_tokens) { $usage.cache_creation_input_tokens } else { 0 }
        $context_length = $input_tokens + $cache_read + $cache_creation
    }

    if ($context_length -gt 0) {
        $pct = [int]($context_length * 100 / $max_context)
        $pct_prefix = ""
    } else {
        # At conversation start, baseline is already loaded
        $pct = [int]($baseline * 100 / $max_context)
        $pct_prefix = "~"
    }
} else {
    # Transcript not available yet - show baseline estimate
    $pct = [int]($baseline * 100 / $max_context)
    $pct_prefix = "~"
}

if ($pct -gt 100) { $pct = 100 }

# Build context bar
$bar = ""
for ($i = 0; $i -lt $bar_width; $i++) {
    $bar_start = $i * 10
    $progress = $pct - $bar_start

    if ($progress -ge 8) {
        $bar += "${C_ACCENT}█${C_RESET}"
    } elseif ($progress -ge 3) {
        $bar += "${C_ACCENT}▄${C_RESET}"
    } else {
        $bar += "${C_BAR_EMPTY}░${C_RESET}"
    }
}

$ctx = "$bar ${C_GRAY}${pct_prefix}${pct}% of ${max_k}k tokens"

# Build output: Model | Dir | Branch (uncommitted) | Context
$output = "${C_ACCENT}${model}${C_GRAY} | ${dir}"
if ($branch) {
    $output += " | ${C_ACCENT}${branch}${C_GRAY} ${git_status}"
}
$output += " | ${ctx}${C_RESET}"

Write-Host $output

# Get user's last message (text only, not tool results, skip unhelpful messages)
if ($transcript_path -and (Test-Path $transcript_path)) {
    # Calculate visible length (without ANSI codes)
    $plain_output = "${model} | ${dir}"
    if ($branch) {
        $plain_output += " | ${branch} ${git_status}"
    }
    $plain_output += " | xxxxxxxxxx ${pct}% of ${max_k}k tokens"
    $max_len = $plain_output.Length

    # Get last user message - transcript is JSON Lines format
    $lines = Get-Content $transcript_path
    $transcript = $lines | ForEach-Object { $_ | ConvertFrom-Json }
    $last_user_msg = ""

    $user_messages = $transcript | Where-Object { $_.type -eq "user" } | ForEach-Object {
        $content = $_.message.content
        $text = ""

        if ($content -is [string]) {
            $text = $content
        } elseif ($content -is [array]) {
            $text = ($content | Where-Object { $_.type -eq "text" } | ForEach-Object { $_.text }) -join " "
        }

        # Clean up whitespace
        $text = $text -replace "`n", " " -replace "\s+", " "

        # Skip unhelpful messages
        if ($text -and
            -not $text.StartsWith("[Request interrupted") -and
            -not $text.StartsWith("[Request cancelled")) {
            $text
        }
    }

    if ($user_messages) {
        $last_user_msg = $user_messages | Select-Object -Last 1
    }

    if ($last_user_msg) {
        if ($last_user_msg.Length -gt $max_len) {
            Write-Host "${C_GRAY}> $($last_user_msg.Substring(0, $max_len - 3))...${C_RESET}"
        } else {
            Write-Host "${C_GRAY}> $last_user_msg${C_RESET}"
        }
    }
}
