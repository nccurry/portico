import os
from spreadsheet import TransactionsSpreadsheet

transaction_spreadsheet = TransactionsSpreadsheet(url=os.environ.get("TRANSACTIONS_SPREADSHEET_URL"))

