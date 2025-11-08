import pandas as pd

df = pd.read_csv('example_data/Tiller Data - Transactions.csv')
df_oct = df[df['Month'] == '2025-10']

print('=== OCTOBER 2025 (ALL Transactions) ===')
print(f'Total: {len(df_oct)} transactions\n')

print('By Group:')
print(df_oct.groupby('Group').size())

print('\n\nBy Category (top 10):')
print(df_oct.groupby('Category').size().sort_values(ascending=False).head(10))

print('\n\nBy Type:')
print(df_oct.groupby('Type').size())

# After excluding Transfer group
df_filtered = df_oct[df_oct['Group'] != 'Transfer']
df_filtered = df_filtered[~df_filtered['Category'].isin(['Transfer', 'RSU', 'ESPP', 'Tax Return Payment'])]

print(f'\n\n=== After Filters (Group!=Transfer, excluding Transfer/RSU/ESPP/Tax) ===')
print(f'Remaining: {len(df_filtered)} transactions')

if len(df_filtered) > 0:
    print('\nIncome:')
    income = df_filtered[df_filtered['Type'] == 'Income']
    print(f'Total: ${income["Amount"].sum():,.2f}')
    print(income[['Date', 'Category', 'Amount', 'Description']].to_string())
    
    print('\n\nExpenses (largest):')
    expense = df_filtered[df_filtered['Type'] == 'Expense'].sort_values('Amount').head(15)
    print(f'Total: ${df_filtered[df_filtered["Type"] == "Expense"]["Amount"].sum():,.2f}')
    print(expense[['Date', 'Category', 'Amount', 'Description']].to_string())

