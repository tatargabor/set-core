#!/usr/bin/env bash
# Unit test helpers for set-core
# Usage: source this file, define test_* functions, call run_tests at end

_TEST_PASS=0
_TEST_FAIL=0

# Colors (disable if not a terminal)
if [[ -t 1 ]]; then
    _GREEN='\033[0;32m'
    _RED='\033[0;31m'
    _RESET='\033[0m'
else
    _GREEN='' _RED='' _RESET=''
fi

assert_equals() {
    local expected="$1" actual="$2" msg="${3:-assert_equals}"
    if [[ "$expected" == "$actual" ]]; then
        return 0
    else
        echo -e "    ${_RED}FAIL${_RESET}: $msg"
        echo "      expected: '$expected'"
        echo "      actual:   '$actual'"
        return 1
    fi
}

assert_contains() {
    local haystack="$1" needle="$2" msg="${3:-assert_contains}"
    if [[ "$haystack" == *"$needle"* ]]; then
        return 0
    else
        echo -e "    ${_RED}FAIL${_RESET}: $msg"
        echo "      haystack: '${haystack:0:200}'"
        echo "      needle:   '$needle'"
        return 1
    fi
}

assert_not_contains() {
    local haystack="$1" needle="$2" msg="${3:-assert_not_contains}"
    if [[ "$haystack" != *"$needle"* ]]; then
        return 0
    else
        echo -e "    ${_RED}FAIL${_RESET}: $msg"
        echo "      should not contain: '$needle'"
        return 1
    fi
}

assert_exit_code() {
    local expected="$1" msg="${2:-assert_exit_code}"
    shift 2
    local actual
    set +e
    "$@" >/dev/null 2>&1
    actual=$?
    set -e
    if [[ "$expected" == "$actual" ]]; then
        return 0
    else
        echo -e "    ${_RED}FAIL${_RESET}: $msg"
        echo "      expected exit: $expected"
        echo "      actual exit:   $actual"
        echo "      command: $*"
        return 1
    fi
}

assert_file_exists() {
    local path="$1" msg="${2:-assert_file_exists}"
    if [[ -f "$path" ]]; then
        return 0
    else
        echo -e "    ${_RED}FAIL${_RESET}: $msg"
        echo "      path: '$path' does not exist"
        return 1
    fi
}

# Run all test_* functions defined in the test file
run_tests() {
    local test_funcs
    test_funcs=$(declare -F | awk '{print $3}' | grep '^test_' | sort || true)

    if [[ -z "$test_funcs" ]]; then
        echo "No test_* functions found"
        return 1
    fi

    local file_name="${BASH_SOURCE[1]##*/}"
    echo "=== $file_name ==="

    while IFS= read -r func; do
        set +e
        output=$("$func" 2>&1)
        local rc=$?
        set -e
        if [[ $rc -eq 0 ]]; then
            (( _TEST_PASS++ )) || true
            echo -e "  ${_GREEN}ok${_RESET}  $func"
        else
            (( _TEST_FAIL++ )) || true
            echo -e "  ${_RED}FAIL${_RESET}  $func"
            [[ -n "$output" ]] && echo "$output"
        fi
    done <<< "$test_funcs"

    echo ""
    echo "Results: $_TEST_PASS passed, $_TEST_FAIL failed"

    [[ $_TEST_FAIL -eq 0 ]]
}
