import pandas as pd

df = pd.read_csv('example_data/Tiller Data - Transactions.csv')
groups = df['Group'].unique()
groups = [g for g in groups if pd.notna(g) and str(g).strip() != '']

print('All Groups:')
for g in sorted(groups):
    print(f'  {g}')

