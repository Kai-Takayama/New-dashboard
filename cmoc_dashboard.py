import yfinance as yf
import pandas as pd
import datetime
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 设置网页基础配置 (UI 优先加载)
st.set_page_config(page_title="洛阳钼业追踪面板", layout="wide")
st.title("📈 洛阳钼业量化追踪面板 (V4.1 云端稳定版)")

# 2. 精细化抓取逻辑 (增加容错和超时处理)
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_cloud_data():
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    tickers_map = {
        "DX-Y.NYB": "DXY",
        "^TNX": "US_10Y_Nominal",
        "HG=F": "COMEX_Copper_Lb",
        "GC=F": "COMEX_Gold",
        "603993.SS": "CMOC_Stock"
    }
    
    df_list = []
    for ticker, name in tickers_map.items():
        try:
            ticker_obj = yf.Ticker(ticker)
            data = ticker_obj.history(start=start_date, end=end_date)
            if not data.empty:
                series = data['Close']
                series.name = name
                df_list.append(series)
        except Exception:
            pass # 即使某个抓不到，也保证程序不崩溃
            
    if not df_list: return pd.DataFrame()
        
    df = pd.concat(df_list, axis=1)
    df.ffill(inplace=True)
    
    # 核心指标计算
    if 'COMEX_Copper_Lb' in df.columns and 'COMEX_Gold' in df.columns:
        df['Copper_Gold_Ratio'] = df['COMEX_Copper_Lb'] / df['COMEX_Gold']
    if 'COMEX_Copper_Lb' in df.columns:
        df['COMEX_Copper_Ton'] = df['COMEX_Copper_Lb'] * 2204.62
    return df

# 3. 渲染逻辑
st.info("💡 正在从全球服务器同步金融数据... 首次加载约需 15-30 秒。")

with st.spinner('正在与雅虎财经建立安全连接...'):
    df = fetch_cloud_data()

if df.empty or len(df) < 2:
    st.error("🚨 暂时无法获取数据，请稍后刷新。")
else:
    st.subheader("一、 核心资产与产业监控")
    col1, col2, col3 = st.columns(3)
    
    def get_val(col, offset=-1): return df[col].dropna().iloc[offset] if col in df else 0
    latest_cmoc = get_val('CMOC_Stock'); prev_cmoc = get_val('CMOC_Stock', -2)
    latest_copper = get_val('COMEX_Copper_Ton'); prev_copper = get_val('COMEX_Copper_Ton', -2)
    latest_ratio = get_val('Copper_Gold_Ratio'); prev_ratio = get_val('Copper_Gold_Ratio', -2)

    col1.metric("洛阳钼业 (A股)", f"{latest_cmoc:.2f}", f"{latest_cmoc - prev_cmoc:.2f}")
    col2.metric("期铜 (美元/吨)", f"{latest_copper:.0f}", f"{latest_copper - prev_copper:.0f}")
    col3.metric("铜金比", f"{latest_ratio:.5f}", f"{latest_ratio - prev_ratio:.5f}")

    st.divider()
    st.subheader("二、 核心博弈走势 (交互版)")
    
    if 'CMOC_Stock' in df and 'Copper_Gold_Ratio' in df:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df.index, y=df['CMOC_Stock'], name="股价 (L)", line=dict(color="#FF0000")), secondary_y=False)
        fig.add_trace(go.Scatter(x=df.index, y=df['Copper_Gold_Ratio'], name="铜金比 (R)", line=dict(color="#FFA500", dash='dot')), secondary_y=True)
        fig.update_layout(hovermode="x unified", height=500, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
