#!/usr/bin/env bash
# Format Claude stream-json output for readability
# Usage: ralph-format.sh [--verbose]

VERBOSE=false
[[ "$1" == "--verbose" || "$1" == "-v" ]] && VERBOSE=true

# Colors
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
BLUE='\033[34m'
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
MAGENTA='\033[35m'
GRAY='\033[90m'
WHITE='\033[97m'

# Pricing (USD per 1M tokens) — update when model changes
# Source: https://www.anthropic.com/pricing (claude-sonnet-4-6 / Sonnet-class)
PRICE_INPUT=3.00
PRICE_OUTPUT=15.00
PRICE_CACHE_READ=0.30
PRICE_CACHE_CREATE=3.75

# Track tokens for summary
total_input=0
total_output=0
total_cache_read=0
total_cache_create=0

format_number() {
    printf "%'d" "$1" 2>/dev/null || echo "$1"
}

print_wrapped() {
    local prefix="$1"
    local text="$2"
    local max_width=100

    # Print with prefix, wrapping long lines
    echo "$text" | fold -s -w $max_width | while IFS= read -r line; do
        echo -e "${prefix}${line}"
    done
}

while IFS= read -r line; do
    [[ -z "$line" ]] && continue

    type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)
    [[ -z "$type" ]] && continue

    case "$type" in
        assistant)
            # Extract token usage
            input_tokens=$(echo "$line" | jq -r '.message.usage.input_tokens // 0' 2>/dev/null)
            output_tokens=$(echo "$line" | jq -r '.message.usage.output_tokens // 0' 2>/dev/null)
            cache_read=$(echo "$line" | jq -r '.message.usage.cache_read_input_tokens // 0' 2>/dev/null)
            cache_create=$(echo "$line" | jq -r '.message.usage.cache_creation_input_tokens // 0' 2>/dev/null)

            # Accumulate
            total_input=$((total_input + input_tokens))
            total_output=$((total_output + output_tokens))
            total_cache_read=$((total_cache_read + cache_read))
            total_cache_create=$((total_cache_create + cache_create))

            # Get content array
            content=$(echo "$line" | jq -c '.message.content[]?' 2>/dev/null)
            while IFS= read -r item; do
                [[ -z "$item" ]] && continue
                item_type=$(echo "$item" | jq -r '.type' 2>/dev/null)

                case "$item_type" in
                    thinking)
                        if $VERBOSE; then
                            thinking=$(echo "$item" | jq -r '.thinking' 2>/dev/null)
                            echo -e "${DIM}${CYAN}🧠 Thinking...${RESET}"
                            print_wrapped "${DIM}${GRAY}   │ ${RESET}${DIM}" "$thinking"
                        fi
                        ;;
                    text)
                        text=$(echo "$item" | jq -r '.text' 2>/dev/null)
                        echo -e "${BLUE}💭${RESET} ${text}"
                        ;;
                    tool_use)
                        name=$(echo "$item" | jq -r '.name' 2>/dev/null)
                        desc=$(echo "$item" | jq -r '.input.description // empty' 2>/dev/null)

                        # Tool-specific display
                        case "$name" in
                            Bash)
                                cmd=$(echo "$item" | jq -r '.input.command // empty' 2>/dev/null)
                                if $VERBOSE; then
                                    echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${desc}${RESET}"
                                    print_wrapped "${GRAY}   │ ${RESET}${DIM}" "$cmd"
                                else
                                    # Truncate command for normal mode
                                    [[ ${#cmd} -gt 60 ]] && cmd="${cmd:0:57}..."
                                    echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${cmd}${RESET}"
                                fi
                                ;;
                            Read|Write|Edit)
                                file=$(echo "$item" | jq -r '.input.file_path // empty' 2>/dev/null)
                                echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${file}${RESET}"
                                if $VERBOSE && [[ "$name" == "Edit" ]]; then
                                    old=$(echo "$item" | jq -r '.input.old_string // empty' 2>/dev/null | head -1)
                                    [[ -n "$old" ]] && echo -e "${GRAY}   │ ${DIM}old: ${old:0:60}...${RESET}"
                                fi
                                ;;
                            Grep|Glob)
                                pattern=$(echo "$item" | jq -r '.input.pattern // empty' 2>/dev/null)
                                path=$(echo "$item" | jq -r '.input.path // "." ' 2>/dev/null)
                                echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${pattern} ${DIM}in ${path}${RESET}"
                                ;;
                            Task)
                                task_desc=$(echo "$item" | jq -r '.input.description // empty' 2>/dev/null)
                                agent=$(echo "$item" | jq -r '.input.subagent_type // empty' 2>/dev/null)
                                echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${CYAN}[${agent}]${RESET} ${GRAY}${task_desc}${RESET}"
                                ;;
                            WebSearch|WebFetch)
                                query=$(echo "$item" | jq -r '.input.query // .input.url // empty' 2>/dev/null)
                                echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${query}${RESET}"
                                ;;
                            TodoWrite)
                                echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET}"
                                if $VERBOSE; then
                                    todos=$(echo "$item" | jq -r '.input.todos[]? | "   │ [\(.status)] \(.content)"' 2>/dev/null)
                                    [[ -n "$todos" ]] && echo -e "${GRAY}${todos}${RESET}"
                                fi
                                ;;
                            *)
                                # Generic tool display
                                if [[ -n "$desc" ]]; then
                                    echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET} ${GRAY}${desc}${RESET}"
                                else
                                    echo -e "${YELLOW}🔧 ${BOLD}${name}${RESET}"
                                fi
                                ;;
                        esac
                        ;;
                esac
            done <<< "$content"
            ;;

        user)
            content=$(echo "$line" | jq -c '.message.content[]?' 2>/dev/null)
            while IFS= read -r item; do
                [[ -z "$item" ]] && continue
                item_type=$(echo "$item" | jq -r '.type' 2>/dev/null)

                if [[ "$item_type" == "tool_result" ]]; then
                    is_error=$(echo "$item" | jq -r '.is_error // false' 2>/dev/null)
                    result=$(echo "$item" | jq -r '.content // empty' 2>/dev/null)

                    if [[ "$is_error" == "true" ]]; then
                        if $VERBOSE; then
                            echo -e "${MAGENTA}   ✗ ERROR:${RESET}"
                            print_wrapped "${GRAY}   │ ${RESET}${MAGENTA}" "$result"
                        else
                            first_line=$(echo "$result" | head -1)
                            [[ ${#first_line} -gt 80 ]] && first_line="${first_line:0:77}..."
                            echo -e "${GRAY}   └─${RESET} ${MAGENTA}✗ ${first_line}${RESET}"
                        fi
                    else
                        if $VERBOSE; then
                            # Show up to 10 lines in verbose
                            line_count=$(echo "$result" | wc -l)
                            if [[ $line_count -gt 10 ]]; then
                                echo "$result" | head -5 | while IFS= read -r l; do
                                    echo -e "${GRAY}   │ ${l:0:100}${RESET}"
                                done
                                echo -e "${GRAY}   │ ${DIM}... ($((line_count - 10)) more lines)${RESET}"
                                echo "$result" | tail -5 | while IFS= read -r l; do
                                    echo -e "${GRAY}   │ ${l:0:100}${RESET}"
                                done
                            else
                                echo "$result" | while IFS= read -r l; do
                                    echo -e "${GRAY}   │ ${l:0:100}${RESET}"
                                done
                            fi
                        else
                            first_line=$(echo "$result" | head -1)
                            [[ ${#first_line} -gt 80 ]] && first_line="${first_line:0:77}..."
                            echo -e "${GRAY}   └─ ${first_line}${RESET}"
                        fi
                    fi
                fi
            done <<< "$content"
            ;;

        result)
            echo ""
            echo -e "${GREEN}${BOLD}✓ Done${RESET}"
            ;;
    esac
done

# Show final cost summary whenever we processed tokens (always, not just verbose)
if [[ $total_output -gt 0 ]]; then
    echo ""
    # Total input = input_tokens + cache_read + cache_create (input_tokens can be 0 when cached)
    actual_input=$((total_input + total_cache_read + total_cache_create))
    cache_pct=0
    [[ $actual_input -gt 0 ]] && cache_pct=$((total_cache_read * 100 / actual_input))
    cost=$(awk -v inp="$total_input" -v out="$total_output" \
               -v cr="$total_cache_read" -v cc="$total_cache_create" \
               -v pi="$PRICE_INPUT" -v po="$PRICE_OUTPUT" \
               -v pcr="$PRICE_CACHE_READ" -v pcc="$PRICE_CACHE_CREATE" \
               'BEGIN { printf "%.4f", (inp/1e6)*pi + (out/1e6)*po + (cr/1e6)*pcr + (cc/1e6)*pcc }')
    echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    if $VERBOSE; then
        echo -e "${DIM}📊 Tokens: $(format_number $actual_input) input, $(format_number $total_output) output, ${cache_pct}% cache hit${RESET}"
    fi
    echo -e "${DIM}💰 Cost:   ~\$${cost} USD${RESET}"
fi
