import os
import datetime
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 强制走 Veee 代理通道 (请核对端口是否正确)
os.environ['http_proxy'] = 'http://127.0.0.1:15236'
os.environ['https_proxy'] = 'http://127.0.0.1:15236'

# 2. 设置网页基础配置
st.set_page_config(page_title="洛阳钼业追踪面板", layout="wide")
st.title("📈 洛阳钼业量化追踪面板 (V4.0 Plotly版)")

# 3. 精细化抓取与数据对齐
@st.cache_data(ttl=3600)
def fetch_and_align_data():
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    # 定义主要交易品种及其代码
    tickers_map = {
        "DX-Y.NYB": "DXY",
        "^TNX": "US_10Y_Nominal",
        "HG=F": "COMEX_Copper_Lb", # 美元/磅
        "GC=F": "COMEX_Gold",      # 美元/盎司
        "603993.SS": "CMOC_Stock"  # 洛阳钼业A股 (RMB)
    }
    
    df_list = []
    
    # 第1步：逐个抓取，确保最高容错率
    for ticker, name in tickers_map.items():
        try:
            data = yf.Ticker(ticker).history(start=start_date, end=end_date)
            if not data.empty:
                series = data['Close']
                series.name = name
                df_list.append(series)
        except Exception as e:
            print(f"抓取 {ticker} 失败: {e}")
            
    if not df_list: return pd.DataFrame()
        
    # 第2步：合并数据，强行使用 ffill 向前填充，彻底抹平不同市场的节假日时差
    df = pd.concat(df_list, axis=1)
    df.ffill(inplace=True)
    
    # 第3步：以洛阳钼业（A股）的交易日为基准时间戳进行对齐，清理掉不需要的日期
    if 'CMOC_Stock' in df.columns:
        stock_days_index = yf.Ticker("603993.SS").history(start=start_date, end=end_date).index
        df = df.reindex(stock_days_index)
        
    # 第4步：计算衍生量化指标与单位换算
    # 计算量化前瞻指标：铜金比 (lb/oz)
    if 'COMEX_Copper_Lb' in df.columns and 'COMEX_Gold' in df.columns:
        df['Copper_Gold_Ratio'] = df['COMEX_Copper_Lb'] / df['COMEX_Gold']
        
    # COMEX 铜单位换算：美元/磅 -> 美元/吨 (1吨 = 2204.62磅)
    if 'COMEX_Copper_Lb' in df.columns:
        df['COMEX_Copper_Ton'] = df['COMEX_Copper_Lb'] * 2204.62
        
    return df

st.write("正在同步全球宏观、商品基本面及 A 股市场数据...")

df = fetch_and_align_data()

# 4. 安全渲染机制 (防止雅虎 API 限制导致网页崩溃)
if df.empty or len(df) < 2:
    st.error("⚠️ 数据抓取失败。请检查 Veee 节点状态，或等待雅虎财经 API 限制解除。")
else:
    # 提取 KPI 基础数值
    def get_safe_val(col_name, offset=-1):
        return df[col_name].dropna().iloc[offset] if col_name in df else 0

    latest_cmoc = get_safe_val('CMOC_Stock', -1)
    prev_cmoc = get_safe_val('CMOC_Stock', -2)
    latest_ratio = get_safe_val('Copper_Gold_Ratio', -1)
    prev_ratio = get_safe_val('Copper_Gold_Ratio', -2)
    latest_copper_ton = get_safe_val('COMEX_Copper_Ton', -1)
    prev_copper_ton = get_safe_val('COMEX_Copper_Ton', -2)

    # --- 第一部分：微观与产业核心 KPI ---
    st.subheader("一、 核心资产与产业监控 (对标行业惯例)")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("洛阳钼业 (603993.SS) - 元", f"{latest_cmoc:.2f}", f"{latest_cmoc - prev_cmoc:.2f}")
    col2.metric("COMEX 期铜 (美元/吨)", f"{latest_copper_ton:.0f}", f"{latest_copper_ton - prev_copper_ton:.0f}")
    col3.metric("铜金比 (lb/oz) - 衰退预警线", f"{latest_ratio:.5f}", f"{latest_ratio - prev_ratio:.5f}")

    st.divider()

    # --- 第二部分： Plotly 资产走势映射 (双Y轴) ---
    st.subheader("二、 核心博弈：洛钼股价 vs 铜金比走势映射 (Plotly 交互版)")
    st.write("*(观察逻辑：铜金比下行代表宏观预期转弱，通常会领先或同步于洛钼股价见顶。鼠标悬停可查看清晰时间线数据)*")
    
    if 'CMOC_Stock' in df and 'Copper_Gold_Ratio' in df:
        # 创建带有双Y轴的 Plotly 图表
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 添加洛阳钼业股价 (左轴 - Primary)
        fig.add_trace(
            go.Scatter(x=df.index, y=df['CMOC_Stock'], name="洛钼股价 (左轴 - RMB)", line=dict(color="#FF0000", width=2.5)),
            secondary_y=False,
        )
        
        # 添加铜金比 (右轴 - Secondary)
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Copper_Gold_Ratio'], name="铜金比 (右轴 - lb/oz)", line=dict(color="#FFA500", width=2.5, dash='dot')),
            secondary_y=True,
        )
        
        # 设置图表布局 (悬浮窗模式、统一时间轴、网格)
        fig.update_layout(
            hovermode="x unified", # 统一时间轴悬浮提示，解决乱码重叠问题
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), # 顶部横向图例
            xaxis=dict(title="日期", showgrid=True),
            height=500
        )
        
        # 设置Y轴标题颜色
        fig.update_yaxes(title_text="洛钼股价 (元)", title_font=dict(color="#FF0000"), secondary_y=False)
        fig.update_yaxes(title_text="铜金比", title_font=dict(color="#FFA500"), secondary_y=True)
        
        # 在 Streamlit 中渲染 Plotly 图表
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 第三部分：底层宏观底座 (保留原生轻量化图表) ---
    st.subheader("三、 宏观流动性基石")
    chart_col_bot1, chart_col_bot2 = st.columns(2)

    with chart_col_bot1:
        st.write("💵 美元指数走势 (强美元压制周期商品估值)")
        if 'DXY' in df:
            st.line_chart(df['DXY'], color="#FF4B4B")

    with chart_col_bot2:
        st.write("🦅 10年期美债收益率 (%) (全球无风险利率锚)")
        if 'US_10Y_Nominal' in df:
            st.line_chart(df['US_10Y_Nominal'], color="#0068C9")