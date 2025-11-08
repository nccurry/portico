import pandas as pd

df = pd.read_excel('example_data/Tiller Data.xlsx', sheet_name='Transactions')
df_recent = df[(df['Month'].astype(str) >= '2024-01')]

print('=== Category=Transfer with Group!=Transfer ===')
bad = df_recent[(df_recent['Category'] == 'Transfer') & (df_recent['Group'] != 'Transfer')]
print(f'Found {len(bad)} miscategorized transfers')

if not bad.empty:
    print(bad[['Date', 'Category', 'Amount', 'Group', 'Type']].head(20).to_string())
else:
    print('✓ All transfers are properly categorized!')

print('\n\n=== Checking for outlier categories ===')
proper = df_recent[(df_recent['Group'] != 'Transfer')]
print(f'RSU transactions: {len(proper[proper["Category"] == "RSU"])}')
print(f'ESPP transactions: {len(proper[proper["Category"] == "ESPP"])}')
print(f'Tax Return Payment: {len(proper[proper["Category"] == "Tax Return Payment"])}')
print(f'Home Improvements: {len(proper[proper["Category"] == "Home Improvements"])}')

if len(proper[proper["Category"] == "RSU"]) > 0:
    print('\n=== Sample RSU transactions ===')
    print(proper[proper["Category"] == "RSU"][['Date', 'Amount', 'Group']].head(5).to_string())

