# Synthetic rows injected into fixtures

All committed fixture data is synthetic. It spans May 1992 through April 1995.
Run `uv run --locked --dev python scripts/generate_demo_data.py` to regenerate
the date-based CSV files. The demo reference date is in `config/defaults.toml`.
These rows add specific test patterns to the base synthetic data.
Identifying tuple = (Date | Amount | Description | Account).

## transactions.csv

### Data Health duplicate-pair seed #1
- 02/07/1995 | -$45.99 | duplicate pair seed 1 | Checking-B
- 02/07/1995 | -$45.99 | duplicate pair seed 1 | Checking-B

### Data Health duplicate-pair seed #2
- 12/12/1994 | -$125.50 | duplicate pair seed 2 | Checking-B
- 12/12/1994 | -$125.50 | duplicate pair seed 2 | Checking-B

### Data Health duplicate-pair seed #3
- 10/05/1994 | -$78.00 | duplicate pair seed 3 | Checking-B
- 10/05/1994 | -$78.00 | duplicate pair seed 3 | Checking-B

### Page 5 recurring monthly seed #1
- 11/17/1994 | -$15.99 | verum streamus 00001 | Credit-H
- 12/17/1994 | -$15.99 | verum streamus 00002 | Credit-H
- 01/17/1995 | -$15.99 | verum streamus 00003 | Credit-H
- 02/17/1995 | -$15.99 | verum streamus 00004 | Credit-H
- 03/17/1995 | -$15.99 | verum streamus 00005 | Credit-H
- 04/17/1995 | -$15.99 | verum streamus 00006 | Credit-H

### Page 5 recurring monthly seed #2
- 12/17/1994 | -$9.99 | nimbus cloudus 00001 | Credit-H
- 01/17/1995 | -$9.99 | nimbus cloudus 00002 | Credit-H
- 02/17/1995 | -$9.99 | nimbus cloudus 00003 | Credit-H
- 03/17/1995 | -$9.99 | nimbus cloudus 00004 | Credit-H
- 04/17/1995 | -$9.99 | nimbus cloudus 00005 | Credit-H

### Page 8 top-N tie seed
- 03/16/1995 | -$2,500.00 | magnum boxus 99000 | Credit-H
- 03/09/1995 | -$2,500.00 | magnum boxus 99001 | Credit-H

### Page 3 cross-year seed
- 03/17/1994 | -$87.65 | cross year staple | Checking-B
- 03/17/1995 | -$87.65 | cross year staple | Checking-B

## balance_history.csv

### Home zero-total-group seed
- 04/20/1995 | $0.00 | ZeroSum-A | Asset
