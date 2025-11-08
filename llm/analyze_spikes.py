import pandas as pd

df = pd.read_csv('example_data/Tiller Data - Transactions.csv')
df['Amount'] = df['Amount'].replace('[\$,]', '', regex=True).astype(float)
df['Month'] = pd.to_datetime(df['Month'], format='mixed', utc=True).dt.strftime('%Y-%m')

# Apply same filters as Savings Rate page
df = df[(df['Group'] != 'Transfer') & (~df['Category'].isin(['Transfer', 'RSU', 'ESPP', 'Tax Return Payment']))]

# Filter large expenses >$10k
df = df[(df['Type'] != 'Expense') | (df['Amount'].abs() <= 10000)]

spike_months = ['2024-02', '2024-09', '2024-11', '2025-01', '2025-03', '2025-05', '2025-09']

for month in spike_months:
    month_data = df[df['Month'] == month]
    income = month_data[month_data['Type'] == 'Income']
    expense = month_data[month_data['Type'] == 'Expense']
    
    print(f'=== {month} ===')
    print(f'Total Income: ${income["Amount"].sum():,.2f}')
    print(f'Total Expenses: ${expense["Amount"].sum():,.2f}')
    
    if len(income) > 0:
        print('\nTop Income:')
        print(income.nlargest(5, 'Amount')[['Category', 'Amount', 'Description']].to_string())
    
    if len(expense) > 0:
        print('\nTop Expenses (largest):')
        print(expense.nsmallest(5, 'Amount')[['Category', 'Amount', 'Description']].to_string())
    
    print('\n')

