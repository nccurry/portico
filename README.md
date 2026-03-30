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

```shell
mkdir -p .streamlit

TRANSACTIONS_URL="" # e.g. https://docs.google.com/spreadsheets/d/.../edit#gid=...
BALANCE_HISTORY_URL="" # e.g. https://docs.google.com/spreadsheets/d/.../edit#gid=...

cat <<EOF >> .streamlit/secrets.toml
[connections.transactions]
type = "gsheets"
spreadsheet = "${TRANSACTIONS_URL}"

[connections.balance_history]
type = "gsheets"
spreadsheet = "${BALANCE_HISTORY_URL}"
EOF
```

## Development with Task

This project uses [Task](https://taskfile.dev) as a task runner. Install it via your package manager (e.g. `winget install Task.Task`, `brew install go-task`, or `snap install task`).

Run `task --list` to see all available commands. Common tasks:

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

### Automatic Column Population with VLOOKUP

The Transactions sheet uses ARRAYFORMULA with VLOOKUP to automatically populate the `Group`, `Type`, and `Hide From Reports` columns based on the Category column.

**Prerequisites:**
- A `Categories` sheet with columns:
  - Column A: Category name (e.g., "Groceries", "Electric Bill")
  - Column B: Group (e.g., "Food", "Bills")
  - Column C: Type (e.g., "Expense", "Income")
  - Column D: Hide From Reports (e.g., "Hide" or blank)

**Formulas (place these in row 1 of each column):**

**Group column:**
```excel
={"Group";
   ARRAYFORMULA(
      IF(D2:D="", "",
         IFERROR(
            VLOOKUP(D2:D, Categories!$A$2:$B, 2, FALSE),
            "Uncategorized"
         )
      )
   )
}
```

**Type column:**
```excel
={"Type";
   ARRAYFORMULA(
      IF(D2:D="", "",
         IFERROR(
            VLOOKUP(D2:D, Categories!$A$2:$C, 3, FALSE),
            ""
         )
      )
   )
}
```

**Hide From Reports column:**
```excel
={"Hide From Reports";
   ARRAYFORMULA(
      IF(D2:D="", "",
         IFERROR(
            VLOOKUP(D2:D, Categories!$A$2:$D, 4, FALSE),
            ""
         )
      )
   )
}
```

**How it works:**
1. The formula starts in row 1 with a header (e.g., "Group")
2. `ARRAYFORMULA` applies the formula to all rows automatically
3. `IF(D2:D="", "", ...)` checks if the Category column (D) is empty; if so, leaves the cell blank
4. `VLOOKUP(D2:D, Categories!$A$2:$B, 2, FALSE)` looks up the category in column D against the Categories sheet and returns the corresponding value
5. `IFERROR(..., "Uncategorized")` provides a default value if the category isn't found in the lookup table

This approach ensures that when new transactions are added, their Group, Type, and Hide From Reports values are automatically populated based on the Category.

