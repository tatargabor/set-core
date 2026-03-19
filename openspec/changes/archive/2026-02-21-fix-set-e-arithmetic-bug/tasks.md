## 1. Fix arithmetic bug in wt-hook-memory

- [x] 1.1 Add `|| true` to `(( conv_count++ ))` on line 1118
- [x] 1.2 Add `|| true` to `(( cheat_count++ ))` on line 1123
- [x] 1.3 Add `|| true` to `(( count++ ))` on line 1130

## 2. Verify fix

- [x] 2.1 Run reproduction test: `bash -e -c 'count=0; (( count++ )) || true; echo "OK count=$count"'` succeeds
- [x] 2.2 Run full _stop_migrate_staged simulation against reddit's stuck staged file to confirm it processes without crashing

## 3. Clean up stuck state

- [x] 3.1 Remove the stuck staged file from reddit project (`.set-core/.staged-extract-b638eef0*`)
