import csv
import json
import urllib.request
import urllib.error
import datetime
import os

# 1. Calculate Holdings and Invested Principal
actual_holdings = {}
invested_by_ticker = {}
total_invested_original = 0.0

with open('data/actual_trades.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ticker = row['Ticker']
        action = row['Action'].upper()
        price = float(row['Price'])
        qty = float(row['Quantity'])
        
        if ticker not in actual_holdings:
            actual_holdings[ticker] = 0.0
        if ticker not in invested_by_ticker:
            invested_by_ticker[ticker] = 0.0
            
        if action == 'BUY':
            actual_holdings[ticker] += qty
            invested_by_ticker[ticker] += (price * qty)
            total_invested_original += (price * qty)
        elif action == 'SELL':
            # Reduce invested_by_ticker proportionally
            if actual_holdings[ticker] > 0:
                avg_price = invested_by_ticker[ticker] / actual_holdings[ticker]
                invested_by_ticker[ticker] -= (avg_price * qty)
            actual_holdings[ticker] -= qty
            total_invested_original -= (avg_price * qty)

# Clean up empty holdings
actual_holdings = {k: v for k, v in actual_holdings.items() if v > 0}

# 2. Get latest prices using last known price from actual_trades.csv
current_prices = {}
with open('data/actual_trades.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ticker = row['Ticker']
        price = float(row['Price'])
        current_prices[ticker] = price # Update to the latest price in the file

domestic_tickers = {
    'NASDAQ100': '367380.KS', # ACE 미국나스닥100
    'KOSPI': '278530.KS',     # KODEX 200TR
    'VEA': '251350.KS',       # KODEX 선진국MSCI World
    'COPPER': '160580.KS',    # TIGER 구리실물
    'TLT': '453850.KS',       # ACE 미국30년국채액티브(H)
    'GLD': '411060.KS',       # ACE KRX금현물
    'SHV': '0046A0.KS'        # TIGER 미국초단기(3개월이하)국채
}

all_tickers_to_fetch = set(domestic_tickers.values()).union(actual_holdings.keys())

for ticker in all_tickers_to_fetch:
    if ticker not in current_prices:
        current_prices[ticker] = 0.0

for asset, ticker in domestic_tickers.items():
    current_prices[asset] = current_prices[ticker]

# 3. Target Weights and Growth Rates
target_configs = {
    'NASDAQ100': (0.25, 0.009),
    'KOSPI': (0.15, 0.003),
    'VEA': (0.10, 0.004),
    'COPPER': (0.10, 0.004),
    'TLT': (0.05, 0.0035),
    'GLD': (0.15, 0.004),
    'SHV': (0.10, 0.0005)
}

# 4. Investment Schedule
START_DATE = datetime.datetime.strptime('2026-03-09', '%Y-%m-%d')
TODAY = datetime.datetime.now()

INJECTION_SCHEDULE = [
    ('2026-03-09', 90_000_000), 
    ('2026-04-06', 23_333_333),
    ('2026-05-04', 23_333_333),
    ('2026-06-08', 23_333_333),
    ('2026-07-06', 23_333_333),
    ('2026-08-03', 23_333_333),
    ('2026-09-07', 23_333_333),
    ('2026-10-05', 23_333_333),
    ('2026-11-02', 23_333_333),
    ('2026-12-07', 23_333_340)
]

planned_capital = 0
for date_str, amount in INJECTION_SCHEDULE:
    if datetime.datetime.strptime(date_str, '%Y-%m-%d') <= TODAY:
        planned_capital += amount

elapsed_months = (TODAY - START_DATE).days // 30

# 5. Asset Mapping
reverse_ticker_map = {v: k for k, v in domestic_tickers.items()}
reverse_ticker_map['0046A0.KS'] = 'SHV'    
reverse_ticker_map['379780.KS'] = 'NASDAQ100'  
reverse_ticker_map['379810.KS'] = 'NASDAQ100'  
reverse_ticker_map['069500.KS'] = 'KOSPI'  

total_eval_value = 0.0
for csv_ticker, qty in actual_holdings.items():
    price = current_prices.get(csv_ticker, 0.0)
    total_eval_value += (qty * price)

cash_balance = planned_capital - total_invested_original
current_total_portfolio = total_eval_value + cash_balance

# 6. Macro Overrides
macro_config_path = 'macro_config.json'
macro_overrides = {}
if os.path.exists(macro_config_path):
    with open(macro_config_path, 'r', encoding='utf-8') as f:
        macro_overrides = json.load(f)

# 7. Generate Plan
report_data = []
for asset_name, (weight, growth_rate) in target_configs.items():
    base_allocation = planned_capital * weight
    target_value = base_allocation * ((1 + growth_rate) ** elapsed_months)
    
    current_val = 0.0
    current_qty = 0.0
    invested_principal = 0.0
    
    for csv_ticker, qty in actual_holdings.items():
        if reverse_ticker_map.get(csv_ticker, csv_ticker) == asset_name:
            price = current_prices.get(csv_ticker, 0.0)
            current_val += qty * price
            current_qty += qty
            invested_principal += invested_by_ticker.get(csv_ticker, 0.0)
    
    diff = target_value - current_val
    cumulative_profit = current_val - invested_principal
    
    # ------------------ VA 핵심 방어 로직 (Max Cap & Tolerance Band) ------------------
    base_action_amount = 0.0
    va_max_purchase_cap = 0.05
    tolerance_band = 0.05 # For KOSPI, but let's apply generalized or strictly to KOSPI
    
    if diff > 0:
        # 매수: 1회 최대 매수 상한선(현금 고갈 방어)
        dynamic_max_buy = target_value * va_max_purchase_cap
        base_action_amount = min(diff, dynamic_max_buy)
        # 현금(cash_balance) 제약도 고려해야 하지만 리포트 산출이므로 일단 표기
    elif diff < 0:
        # 매도: 초과분
        # 허용 오차 밴드(Tolerance Band) - 기본 5%
        # KOSPI 등 변동성 자산 랠리 허용
        exceed_ratio = abs(diff) / target_value
        if exceed_ratio > tolerance_band:
            pure_exceed_value = abs(diff) - (target_value * tolerance_band)
            # 초과분의 50%만 매도
            base_action_amount = -(pure_exceed_value * 0.5)
        else:
            base_action_amount = 0.0
    # -------------------------------------------------------------------------
    
    override_ratio = 1.0
    override_msg = "설정값 없음: 100% 기본 진입"
    if asset_name in macro_overrides:
        override_ratio = macro_overrides[asset_name].get('override_ratio', 1.0)
        override_msg = macro_overrides[asset_name].get('override_msg', '')
        
    final_action_amount = base_action_amount * override_ratio
    
    report_data.append({
        'Asset': asset_name,
        'Target_Weight': f"{weight*100:.1f}%",
        'Target_Value': target_value,
        'Current_Value': current_val,
        'Gap': diff,
        'Base_Action_Amount': base_action_amount, 
        'Action_Amount': final_action_amount,     
        'Override_Msg': override_msg,
        'Current_Qty': current_qty,
        'Cumulative_Profit': cumulative_profit,
        'Invested_Principal': invested_principal
    })

total_cut_amount = 0
shv_index = None
for i, row in enumerate(report_data):
    if row['Asset'] != 'SHV':
        cut_amount = row['Base_Action_Amount'] - row['Action_Amount']
        total_cut_amount += cut_amount
    else:
        shv_index = i
        
if shv_index is not None and total_cut_amount > 0:
    report_data[shv_index]['Action_Amount'] += total_cut_amount
    report_data[shv_index]['Override_Msg'] = f"우회 자금(+{total_cut_amount/10000:,.0f}만) 전액 달러파킹"

report_path = f"reports/live_trade_plan_{TODAY.strftime('%Y%m%d')}.md"
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("# 📡 실전 계좌 기반 주간 투자 계획서 (단계적 투입 반영)\n\n")
    f.write(f"> **기준 일시**: {TODAY.strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"> **현재 계획 자본**: {planned_capital:,.0f} KRW (전체 3억 중 { (planned_capital/300000000)*100:.1f}% 투입 중)\n")
    f.write(f"> **총 자산 가치**: {current_total_portfolio:,.0f} KRW (평가액: {total_eval_value:,.0f} / 현금: {cash_balance:,.0f})\n\n")

    f.write("## 1. 목표 대비 현재 상태 (매크로 오버라이드 전)\n\n")
    f.write("| 자산 | 목표 비중 | 목표 평가액 | 현재 평가액 | 부족분 (Gap) | 엔진 원본 권고액 |\n")
    f.write("|:---|:---:|---:|---:|---:|---:|\n")
    for row in report_data:
        f.write(f"| {row['Asset']} | {row['Target_Weight']} | {row['Target_Value']:,.0f} | {row['Current_Value']:,.0f} | {row['Gap']:,.0f} | **{row['Base_Action_Amount']:,.0f}** |\n")
    
    f.write("\n--- \n")
    f.write("## 2. 🛡️ 리스크 오버라이드 반영 최종 매매 지시 (Action Items)\n\n")
    f.write("> **전략 요약**: V2.2 업데이트 이후 **'글로벌 다변화 50:50 황금비율'** 셋업입니다. 나스닥, 글로벌 선진국(VEA), 장기채(TLT) 등 핵심 엔진의 권고 수치를 최우선으로 추종하되, `macro_config.json` 매크로 상황에 따라 일시적 컷아웃이 발생할 수 있습니다.\n\n")
    
    mapping_info = {
        'NASDAQ100': ('ACE 미국나스닥100', '367380'),
        'KOSPI': ('KODEX 200TR', '278530'),
        'VEA': ('KODEX 선진국MSCI World', '251350'),
        'COPPER': ('TIGER 구리실물', '160580'),
        'TLT': ('ACE 미국30년국채액티브(H)', '453850'),
        'GLD': ('ACE KRX금현물', '411060'),
        'SHV': ('TIGER 미국초단기국채', '0046A0')
    }
    
    f.write("| 자산 | 집행 종목 | 종목코드 | 매입원금 | 평가금액 | 누적 수익 | 최종 권고 매수액 | 예상 수량 | 오버라이드 사유 |\n")
    f.write("|:---|:---|:---:|---:|---:|---:|---:|---:|:---|\n")
    for row in report_data:
        name, code = mapping_info.get(row['Asset'], (row['Asset'], '-'))
        price = current_prices.get(row['Asset'], 1.0)
        qty = row['Action_Amount'] / price if price > 0 else 0
        
        profit_str = f"+{row['Cumulative_Profit']:,.0f}" if row['Cumulative_Profit'] > 0 else f"{row['Cumulative_Profit']:,.0f}"
        
        f.write(f"| {row['Asset']} | {name} | {code} | {row['Invested_Principal']:,.0f} | {row['Current_Value']:,.0f} | {profit_str} | **{row['Action_Amount']:,.0f}** | 약 {qty:.1f} 주 | {row['Override_Msg']} |\n")

    f.write("\n> **참고**: 위 예상 수량은 당일 국내 ETF 종가를 바탕으로 산출된 근사치입니다. 실제 매수 시 증권사 앱의 호가를 확인하세요.\n")

print(f"Generated {report_path}")
