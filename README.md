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

## Create PyCharm Configuration

Configure PyCharm to run the following command: 

* Script: ../tiller-streamlit/.venv/Scripts/streamlit.exe
* Script Parameters: run Home.py

Based on [Run streamlit from PyCharm](https://discuss.streamlit.io/t/run-streamlit-from-pycharm/21624).

