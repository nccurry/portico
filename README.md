# Tiller Streamlit

## Setup

### Install prerequisites

```shell
# Install prerequisites
sudo apt update 
sudo apt upgrade
sudo apt install -y \
  python3 \
  python3-pip

# Create /activate .venv directory
python3 -m venv .venv
source .venv/bin/activate

# Install python packages
pip install --upgrade pip
pip3 install -r requirements.txt
```

### Configure Streamlit

The app reads four sheets from your Tiller spreadsheet: Transactions, Balance History, Categories, and Accounts. Each needs its own connection with the appropriate `gid` parameter.

```shell
mkdir -p .streamlit

SPREADSHEET_ID="" # e.g. 1xJ7CTtL3cKBmNYayrDMim13keuqnDWrD312UIu6ZAjE
TRANSACTIONS_GID="" # gid from the Transactions sheet tab URL
BALANCE_HISTORY_GID="" # gid from the Balance History sheet tab URL
CATEGORIES_GID="" # gid from the Categories sheet tab URL
ACCOUNTS_GID="" # gid from the Accounts sheet tab URL

cat <<EOF >> .streamlit/secrets.toml
[connections.transactions]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${TRANSACTIONS_GID}"

[connections.balance_history]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${BALANCE_HISTORY_GID}"

[connections.categories]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${CATEGORIES_GID}"

[connections.accounts]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${ACCOUNTS_GID}"
EOF
```

## Development with Task

This project uses [Task](https://taskfile.dev) as a task runner. Run `task --list` to see all available commands.

| Command | Description |
|---------|-------------|
| `task setup` | Set up the development environment (auto-detects platform) |
| `task test` | Run all tests |
| `task test:verbose` | Run tests with verbose output |
| `task test:file -- test_spreadsheet.py` | Run tests for a specific file |
| `task test:match -- test_filter` | Run tests matching a pattern |
| `task test:coverage` | Run tests with coverage report |
| `task lint` | Check code with ruff |
| `task lint:fix` | Auto-fix lint issues |
| `task run` | Run the Streamlit app |
| `task pkg:check` | Check for outdated packages |
| `task pkg:update` | Update all packages |

## Create PyCharm Configuration

Configure PyCharm to run the following command: 

* Script: ../tiller-streamlit/.venv/Scripts/streamlit.exe
* Script Parameters: run Home.py

Based on [Run streamlit from PyCharm](https://discuss.streamlit.io/t/run-streamlit-from-pycharm/21624).

## Google Sheets Setup

The app reads the `Categories` and `Accounts` sheets and joins them in Python to populate derived columns. This means you don't need VLOOKUP formulas in your Google Sheet — just maintain the Categories and Accounts sheets as normal through Tiller.

- **Transactions** are joined with **Categories** on `Category` to populate `Group`, `Type`, and `Hide From Reports`
- **Balance History** is joined with **Accounts** using a composite key (`Account - Account # (last 4 of Account ID)`) to populate `Group` and `Hide`

