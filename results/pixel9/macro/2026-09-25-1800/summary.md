### A. Macrobenchmark TraceSectionMetric (ms per timed sample; median of 5 iterations)

| Case (ops) | NS | RN | RN Δ | PHP pdo | PHP pdo Δ | PHP pdo+Laravel | PHP pdo+Laravel Δ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| schema_create_drop (30) | 17.868 | 42.667 | +138.8% | 11.000 | -38.4% | 12.763 | -28.6% |
| insert_autocommit (400) | 53.635 | 146.306 | +172.8% | 39.653 | -26.1% | 52.930 | -1.3% |
| insert_transaction (400) | 4.844 | 210.568 | +4,247.1% | 2.063 | -57.4% | 5.467 | +12.9% |
| point_select (400) | 14.116 | 274.404 | +1,844.0% | 2.703 | -80.8% | 4.911 | -65.2% |
| indexed_filter (100) | 6.463 | 102.565 | +1,487.0% | 2.111 | -67.3% | 2.426 | -62.5% |
| range_scan (100) | 5.028 | 108.475 | +2,057.4% | 1.275 | -74.6% | 2.184 | -56.6% |
| full_scan_aggregate (40) | 6.741 | 52.856 | +684.1% | 2.586 | -61.6% | 2.869 | -57.4% |
| order_limit (100) | 6.199 | 102.247 | +1,549.4% | 1.071 | -82.7% | 2.097 | -66.2% |
| join_aggregate (100) | 4.260 | 80.811 | +1,796.9% | 1.086 | -74.5% | 1.951 | -54.2% |
| like_search (50) | 18.212 | 124.869 | +585.6% | 6.579 | -63.9% | 7.162 | -60.7% |
| json_extract (100) | 142.189 | 548.689 | +285.9% | 60.687 | -57.3% | 62.442 | -56.1% |
| update_by_pk (400) | 51.704 | 136.059 | +163.2% | 25.885 | -49.9% | 28.974 | -44.0% |
| delete_by_pk (200) | 25.318 | 75.741 | +199.2% | 12.675 | -49.9% | 14.677 | -42.0% |
| upsert (400) | 51.931 | 162.826 | +213.5% | 28.077 | -45.9% | 30.741 | -40.8% |
| transaction_rollback (50) | 4.868 | 67.622 | +1,289.1% | 0.868 | -82.2% | 1.966 | -59.6% |
| blob_insert_length (100) | 23.067 | 126.811 | +449.8% | 9.202 | -60.1% | 11.395 | -50.6% |
| index_create (1) | 0.663 | 1.428 | +115.2% | 0.452 | -31.9% | 0.474 | -28.6% |
| **Sum of 17 cases** | **440.044** | **2,374.601** | +439.6% | **208.367** | -52.6% | **246.245** | -44.0% |
| *Cold start timeToInitialDisplay* | 426.888 | 194.020 | -54.6% | 281.999 | -33.9% | 274.035 | -35.8% |
| *Cold start timeToFullDisplay* | n/a | n/a |  | 1,067.730 |  | 1,085.056 |  |

### B. In-app timers from the same iterations (median of 5 samples per run; median over runs)

| Case (ops) | NS | RN | RN Δ | PHP pdo | PHP pdo Δ | PHP pdo+Laravel | PHP pdo+Laravel Δ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| schema_create_drop (30) | 17.349 | 44.806 | +158.3% | 10.429 | -39.9% | 12.394 | -28.6% |
| insert_autocommit (400) | 52.600 | 147.412 | +180.3% | 39.442 | -25.0% | 51.424 | -2.2% |
| insert_transaction (400) | 4.393 | 206.893 | +4,609.6% | 1.980 | -54.9% | 5.097 | +16.0% |
| point_select (400) | 14.305 | 272.208 | +1,802.9% | 2.583 | -81.9% | 4.826 | -66.3% |
| indexed_filter (100) | 6.390 | 100.593 | +1,474.2% | 1.681 | -73.7% | 2.377 | -62.8% |
| range_scan (100) | 5.322 | 107.904 | +1,927.5% | 1.225 | -77.0% | 2.135 | -59.9% |
| full_scan_aggregate (40) | 5.358 | 55.173 | +929.7% | 2.528 | -52.8% | 2.740 | -48.9% |
| order_limit (100) | 5.930 | 102.339 | +1,625.8% | 1.041 | -82.4% | 2.079 | -64.9% |
| join_aggregate (100) | 4.121 | 79.735 | +1,834.9% | 1.063 | -74.2% | 1.924 | -53.3% |
| like_search (50) | 18.225 | 129.161 | +608.7% | 6.510 | -64.3% | 7.074 | -61.2% |
| json_extract (100) | 137.318 | 599.928 | +336.9% | 60.771 | -55.7% | 62.250 | -54.7% |
| update_by_pk (400) | 50.498 | 131.852 | +161.1% | 25.490 | -49.5% | 28.873 | -42.8% |
| delete_by_pk (200) | 25.040 | 67.508 | +169.6% | 12.776 | -49.0% | 14.482 | -42.2% |
| upsert (400) | 51.821 | 160.696 | +210.1% | 27.878 | -46.2% | 30.761 | -40.6% |
| transaction_rollback (50) | 4.862 | 69.158 | +1,322.4% | 0.814 | -83.3% | 1.896 | -61.0% |
| blob_insert_length (100) | 23.874 | 134.431 | +463.1% | 9.085 | -61.9% | 11.031 | -53.8% |
| index_create (1) | 0.627 | 1.008 | +60.8% | 0.405 | -35.4% | 0.425 | -32.2% |
| **Sum of 17 cases** | **429.043** | **2,415.605** | +463.0% | **205.431** | -52.1% | **243.683** | -43.2% |

### C. Per-call cost (trace median ÷ ops, ms per SQL call)

| Case | NS | RN | PHP pdo | PHP pdo+Laravel |
| --- | ---: | ---: | ---: | ---: |
| point_select | 0.0353 | 0.6860 | 0.0068 | 0.0123 |
| insert_transaction | 0.0121 | 0.5264 | 0.0052 | 0.0137 |
| insert_autocommit | 0.1341 | 0.3658 | 0.0991 | 0.1323 |
| update_by_pk | 0.1293 | 0.3401 | 0.0647 | 0.0724 |
| indexed_filter | 0.0646 | 1.0257 | 0.0211 | 0.0243 |
| transaction_rollback | 0.0974 | 1.3524 | 0.0174 | 0.0393 |
| json_extract | 1.4219 | 5.4869 | 0.6069 | 0.6244 |

### D. Run-to-run spread (sum of the 17 per-case values, per iteration)

| App/mode | iterations | trace sum per iteration (ms) | spread (max-min)/median | CV | in-app sum per iteration (ms) | worst case CV (trace) |
| --- | ---: | --- | ---: | ---: | --- | --- |
| NativeScript (release) | 5 | 390.6, 458.7, 417.9, 440.0, 546.7 | 35.5% | 11.8% | 378.1, 437.6, 407.5, 429.0, 497.5 | json_extract 29% |
| React Native (release) | 5 | 2,361.7, 2,380.7, 2,374.6, 2,586.4, 2,306.2 | 11.8% | 4.0% | 2,415.6, 2,422.7, 2,368.0, 2,571.8, 2,336.3 | insert_autocommit 21% |
| NativePHP PHP loop · pdo_sqlite · raw PDO | 5 | 206.5, 207.1, 236.7, 210.8, 208.4 | 14.5% | 5.4% | 205.4, 205.1, 234.8, 206.8, 204.7 | transaction_rollback 30% |
| NativePHP PHP loop · pdo_sqlite · Laravel DB | 5 | 254.2, 264.6, 245.6, 246.2, 245.1 | 8.0% | 3.0% | 247.9, 256.5, 243.0, 243.7, 239.8 | blob_insert_length 34% |

### E. Reported SQLite metadata

| App/mode | driver | SQLite | journal_mode | synchronous | integrity_check | extra |
| --- | --- | --- | --- | --- | --- | --- |
| NativeScript (release) | @edusperoni/nativescript-sqlite | 3.53.1 | wal | 2 | ok (5/5) |  |
| React Native (release) | react-native-nitro-sqlite | 3.49.0 | wal | 2 | ok (5/5) |  |
| NativePHP PHP loop · pdo_sqlite · raw PDO | pdo_sqlite via raw handle (PHP loop) | 3.44.2 | wal | 2 | ok (5/5) | handle_class=Pdo\Sqlite, connection_driver=sqlite, database_file=database.sqlite, nativephp_mobile=4.5.2, php=8.4.25 |
| NativePHP PHP loop · pdo_sqlite · Laravel DB | pdo_sqlite via Laravel DB connection (PHP loop) | 3.44.2 | wal | 2 | ok (5/5) | handle_class=Pdo\Sqlite, connection_driver=sqlite, database_file=database.sqlite, nativephp_mobile=4.5.2, php=8.4.25 |

Macrobenchmark context: Pixel 9 (tokay), google/tokay/tokay:17/CP2A.260705.006/15641320:user/release-keys, cpuCoreCount=8, cpuLocked=False, cpuMaxFreqHz=3105000000, sustainedPerformanceMode=False.
