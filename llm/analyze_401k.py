import pandas as pd

df = pd.read_csv('example_data/Tiller Data - Transactions.csv')
df['Amount'] = df['Amount'].replace('[\$,]', '', regex=True).astype(float)
df['Month'] = pd.to_datetime(df['Month'], format='mixed', utc=True).dt.strftime('%Y-%m')

df_401k = df[df['Category'] == '401k']
df_2024_2025 = df_401k[(df_401k['Month'] >= '2024-01') & (df_401k['Month'] < '2025-11')]

print('=== 401k TRANSACTIONS (2024-2025) ===')
print(f'Total 401k transactions: {len(df_2024_2025)}\n')

monthly = df_2024_2025.groupby('Month')['Amount'].sum().sort_index()

print('Monthly 401k amounts:')
for month, amount in monthly.items():
    print(f'{month}: ${amount:>10,.2f}')

print(f'\n\nAverage per month: ${monthly.mean():,.2f}')
print(f'Median per month: ${monthly.median():,.2f}')
print(f'Max month: ${monthly.max():,.2f}')
print(f'Min month: ${monthly.min():,.2f}')

print(f'\n\nMonths with large 401k activity (>$5k):')
outliers = monthly[monthly.abs() > 5000]
for month, amount in outliers.items():
    print(f'{month}: ${amount:,.2f}')
    # Show transactions for that month
    month_trans = df_2024_2025[df_2024_2025['Month'] == month]
    print(month_trans[['Date', 'Amount', 'Description']].to_string())
    print()

