import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet


def prepare_year_comparison_data(monthly_amounts_df: pd.DataFrame) -> pd.DataFrame:
    """Transform monthly data into year-over-year comparison format.
    
    Input: DataFrame with Month index (YYYY-MM format) and Amount column
    Output: DataFrame with Month (1-12) and separate columns per year
    """
    if monthly_amounts_df.empty:
        return pd.DataFrame()
    
    df = monthly_amounts_df.copy()
    df = df.reset_index()
    
    # Extract year and month number from Month column
    df['Year'] = pd.to_datetime(df['Month']).dt.year
    df['Month'] = pd.to_datetime(df['Month']).dt.month
    
    # Pivot: rows=month number (1-12), columns=year, values=amount
    pivoted = df.pivot(index='Month', columns='Year', values='Amount')
    pivoted = pivoted.fillna(0)
    
    return pivoted


def create_year_comparison_chart(pivoted_df: pd.DataFrame, category: str) -> alt.Chart:
    """Create an Altair chart showing year-over-year comparison.
    
    Current year is shown in green, previous years in shades of gray.
    """
    if pivoted_df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No data available"))
    
    current_year = datetime.now().year
    
    # Reshape data for Altair (need long format)
    df_long = pivoted_df.reset_index()
    df_long = df_long.melt(id_vars='Month', var_name='Year', value_name='Amount')
    df_long['Year'] = df_long['Year'].astype(str)
    
    # Create color mapping: current year = green, others = gray shades
    years = sorted(df_long['Year'].unique(), reverse=True)
    color_domain = years
    
    # Current year gets green, previous years get progressively lighter gray
    color_range = []
    for year in years:
        if int(year) == current_year:
            color_range.append('lightgreen')
        else:
            # Older years get progressively lighter gray
            years_ago = current_year - int(year)
            if years_ago == 1:
                color_range.append('darkgray')
            elif years_ago == 2:
                color_range.append('gray')
            else:
                color_range.append('lightgray')
    
    # For each year, trim leading and trailing zeros but keep middle zeros
    filtered_rows = []
    for year in df_long['Year'].unique():
        year_data = df_long[df_long['Year'] == year].copy()
        
        # Find first and last non-zero month for this year
        non_zero = year_data[year_data['Amount'] > 0]
        if not non_zero.empty:
            min_month = non_zero['Month'].min()
            max_month = non_zero['Month'].max()
            
            # Keep only data between first and last non-zero months (inclusive)
            year_data = year_data[
                (year_data['Month'] >= min_month) & 
                (year_data['Month'] <= max_month)
            ]
            filtered_rows.append(year_data)
    
    if filtered_rows:
        df_long = pd.concat(filtered_rows, ignore_index=True)
    else:
        df_long = pd.DataFrame()
    
    # Create the chart
    chart = alt.Chart(df_long).mark_line(point=True).encode(
        x=alt.X('Month:O', 
                axis=alt.Axis(title='Month', labelAngle=0),
                scale=alt.Scale(domain=list(range(1, 13)))),
        y=alt.Y('Amount:Q', 
                axis=alt.Axis(title='Amount ($)'),
                scale=alt.Scale(zero=True)),
        color=alt.Color('Year:N', 
                       scale=alt.Scale(domain=color_domain, range=color_range),
                       legend=alt.Legend(title='Year')),
        tooltip=[
            alt.Tooltip('Year:N', title='Year'),
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Amount:Q', title='Amount', format='$.2f')
        ]
    ).properties(
        height=300,
        title=f'{category} - Year over Year Comparison'
    )
    
    return chart


def display_transaction_table(transactions_df: pd.DataFrame, label: str) -> None:
    """Display an interactive dataframe table in an expander"""
    with st.expander(f"📊 View {label} Transactions ({len(transactions_df)} rows)"):
        if transactions_df.empty:
            st.info("No transactions found")
            return
        
        # Display interactive dataframe with sorting, filtering, search
        st.dataframe(
            transactions_df,
            width='stretch',
            height=400,
            hide_index=True,
            column_config={
                "Amount": st.column_config.NumberColumn(
                    "Amount",
                    format="$%.2f"
                ),
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="YYYY-MM-DD"
                )
            }
        )


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    categories = [
        "Electric Bill",
        "Gas Bill",
        "Water Bill",
        "Phone Bill",
        "Internet Bill",
        "Automobile Fuel"
    ]

    for category in categories:
        monthly_amounts_df = transactions_spreadsheet.get_monthly_amounts_by_category(
            category=category,
            invert_amount=True
        )
        
        # Transform data for year-over-year comparison
        pivoted_df = prepare_year_comparison_data(monthly_amounts_df)
        
        st.subheader(category)
        col1, col2 = st.columns([1, 4])
        
        # Show pivoted data table (years as columns)
        col1.dataframe(pivoted_df)
        
        # Show year-over-year comparison chart
        chart = create_year_comparison_chart(pivoted_df, category)
        col2.altair_chart(chart, width='stretch')
        
        # Show expandable transaction table
        transactions_df = transactions_spreadsheet.get_transactions_by_category(category)
        display_transaction_table(transactions_df, category)


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = TransactionsSpreadsheet()
    balance_history_spreadsheet = BalanceHistorySpreadsheet()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
