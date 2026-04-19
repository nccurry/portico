# Synthetic rows injected into fixtures

These rows were not present in the source xlsx with the required pattern shape; the generator added them deterministically.
Identifying tuple = (Date | Amount | Description | Account).

## transactions.csv

### Page 4 duplicate-pair seed #1
- 02/07/2026 | -$45.99 | duplicate pair seed 1 | Checking-B
- 02/07/2026 | -$45.99 | duplicate pair seed 1 | Checking-B

### Page 4 duplicate-pair seed #2
- 12/12/2025 | -$125.50 | duplicate pair seed 2 | Checking-B
- 12/12/2025 | -$125.50 | duplicate pair seed 2 | Checking-B

### Page 4 duplicate-pair seed #3
- 10/05/2025 | -$78.00 | duplicate pair seed 3 | Checking-B
- 10/05/2025 | -$78.00 | duplicate pair seed 3 | Checking-B

### Page 5 recurring monthly seed #1
- 10/17/2025 | -$15.99 | verum streamus 00001 | Credit-H
- 11/17/2025 | -$15.99 | verum streamus 00002 | Credit-H
- 12/17/2025 | -$15.99 | verum streamus 00003 | Credit-H
- 01/17/2026 | -$15.99 | verum streamus 00004 | Credit-H
- 02/17/2026 | -$15.99 | verum streamus 00005 | Credit-H
- 03/17/2026 | -$15.99 | verum streamus 00006 | Credit-H

### Page 5 recurring monthly seed #2
- 11/17/2025 | -$9.99 | nimbus cloudus 00001 | Credit-H
- 12/17/2025 | -$9.99 | nimbus cloudus 00002 | Credit-H
- 01/17/2026 | -$9.99 | nimbus cloudus 00003 | Credit-H
- 02/17/2026 | -$9.99 | nimbus cloudus 00004 | Credit-H
- 03/17/2026 | -$9.99 | nimbus cloudus 00005 | Credit-H

### Page 8 top-N tie seed
- 03/16/2026 | -$2,500.00 | magnum boxus 99000 | Credit-H
- 03/09/2026 | -$2,500.00 | magnum boxus 99001 | Credit-H

### Page 3 cross-year seed
- 03/17/2025 | -$87.65 | cross year staple | Checking-B
- 03/17/2026 | -$87.65 | cross year staple | Checking-B

## balance_history.csv

### Home zero-total-group seed
- 04/17/2026 | $0.00 | ZeroSum-A | Asset
