import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Configuration and Title ---
st.set_page_config(
    layout="wide", 
    page_title="Live Indian Stock Market Dashboard", 
    initial_sidebar_state="expanded"
)

# List of major Indian tickers (NSE Nifty 50 components)
# We add '.NS' suffix for NSE tickers
MAJOR_INDIAN_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", 
    "LT.NS", "KOTAKBANK.NS", "HINDUNILVR.NS", "BHARTIARTL.NS", "AXISBANK.NS", 
    "SBIN.NS", "BAJFINANCE.NS"
]

@st.cache_data(ttl=60)
def fetch_data(tickers, period="1y", interval="1d"):
    """
    Fetches historical data and latest quotes for a list of tickers.
    Returns a tuple: (historical_data_df, quotes_dict)
    """
    if not tickers:
        return pd.DataFrame(), {}

    try:
        # 1. Fetch Historical Data (used for plotting)
        # Using yf.download to get history for multiple tickers efficiently
        historical_data = yf.download(tickers, period=period, interval=interval, progress=False)
        
        # 2. Fetch Latest Quotes (used for metrics)
        latest_quotes = {}
        for ticker_symbol in tickers:
            try:
                # Use Ticker for detailed, latest info
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info
                
                price = info.get('currentPrice')
                prev_close = info.get('previousClose')
                
                if price and prev_close:
                    change = price - prev_close
                    percent_change = (change / prev_close) * 100
                    latest_quotes[ticker_symbol] = {
                        "Price": price,
                        "Change": change,
                        "PercentChange": percent_change,
                        "Name": info.get('longName', ticker_symbol),
                        "Volume": info.get('volume'),
                        "MarketCap": info.get('marketCap')
                    }
            except Exception:
                # Silently skip if one ticker fails to fetch info
                continue 
                
        # The history data is extracted to the 'Close' column only for line charts
        return historical_data.get('Close', pd.DataFrame()), latest_quotes
        
    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        return pd.DataFrame(), {}

# --- Streamlit UI Setup ---

st.title("🇮🇳 Indian Stock Market Dashboard")
st.markdown("Monitor major NSE stock metrics and historical price movements.")

# --- Sidebar for Selection ---
with st.sidebar:
    st.header("Stock Selection")
    
    # Multiselect for pre-defined tickers
    selected_tickers = st.multiselect(
        "Select Major Stocks",
        options=MAJOR_INDIAN_TICKERS,
        default=MAJOR_INDIAN_TICKERS[:3] # Default selection
    )

    # Optional user input for additional tickers
    user_input_tickers = st.text_input(
        "Add Custom Tickers (Comma separated, e.g., TITAN.NS, WIPRO.NS)"
    ).upper()
    
    # Combine selected and custom tickers
    custom_list = [t.strip() for t in user_input_tickers.split(',') if t.strip()]
    final_tickers = list(set(selected_tickers + custom_list)) # Use set to remove duplicates

    # Data fetching parameters
    st.subheader("Chart Options")
    chart_period = st.selectbox("Historical Period", options=["1y", "6mo", "3mo", "1mo", "5d"], index=0)
    
    refresh_button = st.button("🔄 Fetch & Refresh Data", type="primary")

# --- Main Content Area ---
if not final_tickers:
    st.info("Please select at least one stock ticker from the sidebar to view data.")
else:
    if refresh_button or 'initial_run' not in st.session_state:
        st.session_state['initial_run'] = True
        with st.spinner(f"Loading data for {len(final_tickers)} stocks..."):
            history_df, quotes_dict = fetch_data(final_tickers, period=chart_period)
            st.session_state['history_df'] = history_df
            st.session_state['quotes_dict'] = quotes_dict
            st.session_state['last_update'] = datetime.now().strftime("%H:%M:%S IST")

    # Retrieve data from session state
    history_df = st.session_state.get('history_df', pd.DataFrame())
    quotes_dict = st.session_state.get('quotes_dict', {})
    last_update = st.session_state.get('last_update', 'N/A')

    st.subheader(f"Current Market Metrics")
    st.caption(f"Last updated: {last_update} (Data is typically delayed by 15-20 minutes)")
    
    # --- 1. Display Metrics ---
    # Create columns dynamically for metrics (max 4 per row for readability)
    cols = st.columns(min(len(quotes_dict), 4) or 1) 

    metrics_displayed = 0
    for i, ticker in enumerate(final_tickers):
        if ticker in quotes_dict:
            data = quotes_dict[ticker]
            # Determine color for the delta metric
            delta_color = "inverse" if data['Change'] < 0 else "normal"
            
            with cols[metrics_displayed % 4]: # Cycle through the columns
                # Display name above metric for clarity
                st.markdown(f"**{data['Name'].split(' ')[0]}**")
                
                st.metric(
                    label=f"Price ({ticker.split('.')[0]})",
                    value=f"₹{data['Price']:,.2f}",
                    delta=f"{data['Change']:+.2f} ({data['PercentChange']:+.2f}%)",
                    delta_color=delta_color
                )
            metrics_displayed += 1
        # else:
            # We skip warnings here to keep the metric columns clean, 
            # as the missing stock could be custom input
            
    # Display missing ticker warnings at the bottom
    missing_tickers = [t for t in final_tickers if t not in quotes_dict]
    if missing_tickers:
        st.warning(f"Could not retrieve data for: {', '.join(missing_tickers)}. Check ticker spelling.")


    st.markdown("---")
    
    # --- 2. Display Historical Chart ---
    if not history_df.empty and history_df.shape[0] > 1: # Need more than 1 row to plot
        st.subheader(f"{chart_period} Price History")
        
        # Prepare data for Plotly (unstack/melt to long format if needed)
        
        # Handle single ticker case where history_df might be a Series
        if isinstance(history_df, pd.Series):
             chart_df = history_df.to_frame()
        else:
             chart_df = history_df
             
        # Plotly Line Chart
        chart_data = chart_df.melt(
            ignore_index=False, 
            var_name='Ticker', 
            value_name='Close Price'
        ).reset_index()
        chart_data.columns = ['Date', 'Ticker', 'Close Price']

        fig = px.line(
            chart_data, 
            x='Date', 
            y='Close Price', 
            color='Ticker', 
            title=f"Closing Prices Over Last {chart_period}",
            labels={'Close Price': 'Close Price (INR)', 'Date': 'Trading Day'}
        )
        
        fig.update_layout(hovermode="x unified", legend_title_text='Stocks')
        fig.update_traces(hovertemplate="%{y:,.2f}<extra></extra>")
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select a few tickers and click 'Fetch & Refresh Data' to see the historical price chart.")
