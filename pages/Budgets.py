import os
from src.spreadsheet import TransactionsSpreadsheet

transaction_spreadsheet = TransactionsSpreadsheet(url=os.environ.get("TRANSACTIONS_SPREADSHEET_URL"))

