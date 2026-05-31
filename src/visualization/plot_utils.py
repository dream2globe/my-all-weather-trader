import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from features.indicators import calculate_performance_metrics

def set_style():
    sns.set_theme(style="darkgrid")
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['figure.figsize'] = (14, 8)

def plot_asset_allocation(result_df: pd.DataFrame, save_path: str = None):
    """시간에 따른 자산군 비중 Stacked Area 차트"""
    set_style()
    plt.figure()
    
    plot_df = result_df.resample('W').last() if len(result_df) > 1000 else result_df
    
    val_cols = [c for c in plot_df.columns if c.endswith('_val')] + ['Cash']
    alloc_df = plot_df[val_cols].div(plot_df['Total_Value'], axis=0) * 100
    
    alloc_df.plot.area(alpha=0.8, colormap='tab20')
    plt.title('Asset Allocation Over Time', fontsize=16, fontweight='bold')
    plt.xlabel('Date')
    plt.ylabel('Weight (%)')
    plt.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
    else:
        plt.show()
    plt.close()

def generate_tear_sheet(result_df: pd.DataFrame, trades_df: pd.DataFrame = None, save_path: str = None):
    """핵심 성과 지표(Metrics) 및 자산별 누적 수익률 요약 텍스트 출력"""
    metrics = calculate_performance_metrics(result_df)
    
    report = "=" * 40 + "\n"
    report += " 📊 백테스트 성과 요약 (Tear Sheet)\n"
    report += "=" * 40 + "\n"
    
    for k, v in metrics.items():
        if k in ['Total Return', 'CAGR', 'Max MDD', 'Volatility (Ann.)']:
            report += f"{k:<20}: {v*100:8.2f} %\n"
        else:
            report += f"{k:<20}: {v:8.2f}\n"
            
    # 자산별 수익률 계산 (trades_df 가 있을 경우)
    if trades_df is not None and not trades_df.empty:
        report += "-" * 40 + "\n"
        report += " 📈 자산별 연평균 수익률 (CAGR by Asset)\n"
        report += "-" * 40 + "\n"
        
        tickers = trades_df['Ticker'].unique()
        for ticker in tickers:
            ticker_trades = trades_df[trades_df['Ticker'] == ticker]
            
            # 총 매수 금액 (투입 원금)
            buys = ticker_trades[ticker_trades['Action'] == 'BUY']
            total_invested = buys['Value'].sum() + buys['Commission'].sum()
            
            # 총 매도 금액 (회수 금액)
            sells = ticker_trades[ticker_trades['Action'] == 'SELL']
            total_recovered = sells['Value'].sum() - sells['Commission'].sum()
            
            # 현재 평가 금액 (마지막 날 기준)
            col_name = f"{ticker}_val" if f"{ticker}_val" in result_df.columns else f"{ticker.replace('.KS', '')}_val"
            if col_name in result_df.columns:
                current_value = result_df[col_name].iloc[-1]
            else:
                current_value = 0.0
                
            # 수익률 계산: (현재평가금액 + 누적회수금액) / 누적투입금액 - 1 -> 연환산
            if total_invested > 0:
                asset_return = (current_value + total_recovered) / total_invested - 1.0
                start_dt = result_df.index[0]
                end_dt = result_df.index[-1]
                years = max((end_dt - start_dt).days / 365.25, 0.01)
                asset_cagr = (1 + asset_return) ** (1 / years) - 1.0
                report += f"{ticker:<20}: {asset_cagr*100:8.2f} %\n"
            else:
                report += f"{ticker:<20}:      N/A (매수 내역 없음)\n"

    report += "=" * 40 + "\n"
    
    print(report)
    if save_path:
        with open(save_path, 'w') as f:
            f.write(report)

def generate_markdown_report(result_df: pd.DataFrame, trades_df: pd.DataFrame, save_path: str = None, timestamp: str = ""):
    """실전 매매용 주간 운용 계획서 (Markdown) 생성"""
    metrics = calculate_performance_metrics(result_df)
    
    img_suffix = f"_{timestamp}" if timestamp else ""
    
    report = f"# 📈 주간 포트폴리오 운용 리포트\n\n"
    report += f"> **작성일**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    report += "## 1. 성과 요약 (Performance Summary)\n\n"
    report += "| 지표 | 수치 |\n"
    report += "|:---|---:|\n"
    for k, v in metrics.items():
        if k in ['Total Return', 'CAGR', 'Max MDD', 'Volatility (Ann.)']:
            report += f"| **{k}** | **{v*100:.2f}%** |\n"
        else:
            report += f"| {k} | {v:.2f} |\n"
            
    if trades_df is not None and not trades_df.empty:
        report += "\n### 자산별 연평균 수익률 (CAGR by Asset)\n\n"
        report += "| 자산 | 수익률 (CAGR) |\n"
        report += "|:---|---:|\n"
        
        tickers = trades_df['Ticker'].unique()
        for ticker in tickers:
            ticker_trades = trades_df[trades_df['Ticker'] == ticker]
            buys = ticker_trades[ticker_trades['Action'] == 'BUY']
            total_invested = buys['Value'].sum() + buys['Commission'].sum()
            sells = ticker_trades[ticker_trades['Action'] == 'SELL']
            total_recovered = sells['Value'].sum() - sells['Commission'].sum()
            
            col_name = f"{ticker}_val" if f"{ticker}_val" in result_df.columns else f"{ticker.replace('.KS', '')}_val"
            current_value = result_df[col_name].iloc[-1] if col_name in result_df.columns else 0.0
                
            if total_invested > 0:
                asset_return = (current_value + total_recovered) / total_invested - 1.0
                start_dt = result_df.index[0]
                end_dt = result_df.index[-1]
                years = max((end_dt - start_dt).days / 365.25, 0.01)
                asset_cagr = (1 + asset_return) ** (1 / years) - 1.0
                report += f"| **{ticker}** | **{asset_cagr*100:.2f}%** |\n"
            else:
                report += f"| **{ticker}** | N/A |\n"

    report += "\n---\n\n"
    report += "## 2. 현재 자산 배분 비중 (Current Allocation)\n\n"
    
    val_cols = [c for c in result_df.columns if c.endswith('_val')]
    latest = result_df.iloc[-1]
    total_val = latest['Total_Value']
    
    report += "| 자산 | 평가액 (KRW) | 비중 (%) |\n"
    report += "|:---|---:|---:|\n"
    for col in val_cols:
        asset = col.replace('_val', '')
        val = latest[col]
        weight = (val / total_val) * 100
        report += f"| {asset} | {val:,.0f} | {weight:.1f}% |\n"
    report += f"| **Cash** | **{latest['Cash']:,.0f}** | **{(latest['Cash']/total_val)*100:.1f}%** |\n"
    report += f"| **Total** | **{total_val:,.0f}** | **100.0%** |\n\n"
    
    report += "---\n\n"
    report += "## 3. 최근 매매 기록 (Recent Trades)\n\n"
    if trades_df is not None and not trades_df.empty:
        # 최근 10개 거래만 표시
        recent_trades = trades_df.tail(10).copy()
        report += "| 날짜 | 티커 | 작업 | 가격 | 수량 | 가치 |\n"
        report += "|:---|:---|:---|---:|---:|---:|\n"
        for idx, row in recent_trades.iterrows():
            date_str = idx.strftime('%Y-%m-%d')
            report += f"| {date_str} | {row['Ticker']} | {row['Action']} | {row['Price']:,.2f} | {row['Quantity']:.4f} | {row['Value']:,.0f} |\n"
    else:
        report += "최근 매매 내역이 없습니다.\n"
        
    report += "\n---\n\n"
    report += "## 4. 시각화 자료 (자산 비중 변화)\n\n"
    report += f"![Asset Allocation](./allocation{img_suffix}.png)\n"
    
    if save_path:
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(report)
    return report
