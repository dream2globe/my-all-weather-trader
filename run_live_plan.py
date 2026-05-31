import os
import sys
import json
import pandas as pd
from typing import Dict, Any

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config.settings import config, setup_logger
from data_io.csv_loader import DataLoader
from data_io.account_manager import AccountManager
from strategies.value_averaging import ValueAveragingStrategy

logger = setup_logger("live_plan")

def generate_report():
    logger.info("Generating Weekly Trade Plan based on Actual Holdings & Staggered Injection Strategy...")

    # 외부 매크로 오버라이드 설정 로드
    macro_config_path = os.path.join(os.path.dirname(__file__), 'macro_config.json')
    macro_overrides = {}
    if os.path.exists(macro_config_path):
        try:
            with open(macro_config_path, 'r', encoding='utf-8') as f:
                macro_overrides = json.load(f)
                logger.info("Loaded macro overrides from macro_config.json")
        except Exception as e:
            logger.error(f"Failed to load macro overrides: {e}")

    # 0. 투자 일정 및 목표 정의 (STRATEGY_MANUAL.md 요건 반영)
    START_DATE = pd.Timestamp('2026-03-09')
    TODAY = pd.Timestamp.now()
    
    # 월별 현금 투입 계획 (수정: 분기 -> 월별)
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
        ('2026-12-07', 23_333_340) # 합계 3억 조절용
    ]

    
    # 현재까지 투입되었어야 할 '계획상 총 자본' 계산
    planned_capital = 0
    for date_str, amount in INJECTION_SCHEDULE:
        if pd.Timestamp(date_str) <= TODAY:
            planned_capital += amount
            
    # 시작일로부터 경과한 개월 수 (VA 복리 계산용)
    elapsed_months = (TODAY - START_DATE).days // 30
    
    # 1. 실제 보유 현황 로드
    am = AccountManager()
    actual_holdings = am.get_current_holdings()
    total_invested_original = am.get_total_investment() # 실제 투입된 원금 합계
    
    # 2. 최신 시장 데이터 (국내 ETF 실제 가격) 로드
    import yfinance as yf
    domestic_tickers = {
        'NASDAQ100': '367380.KS', # ACE 미국나스닥100
        'KOSPI': '278530.KS',     # KODEX 200TR
        'VEA': '251350.KS',       # KODEX 선진국MSCI World
        'COPPER': '160580.KS',    # TIGER 구리실물
        'TLT': '453850.KS',       # ACE 미국30년국채액티브(H)
        'GLD': '411060.KS',       # ACE KRX금현물
        'SHV': '0046A0.KS'        # TIGER 미국초단기(3개월이하)국채
    }
    
    current_prices = {}
    
    # 3. 자산별 현황 분석
    # 입력 CSV의 티커(예: 069500.KS)를 내부 자산명(KOSPI)으로 역변환하기 위한 매핑
    reverse_ticker_map = {v: k for k, v in domestic_tickers.items()}
    
    # 새로운 ETF 종목 매핑 추가 (actual_trades.csv 반환을 위함)
    reverse_ticker_map['0046A0.KS'] = 'SHV'    # USA SHORT TERM BOND
    reverse_ticker_map['379780.KS'] = 'NASDAQ100'  # 기존 S&P 500 매수분 포괄
    reverse_ticker_map['379810.KS'] = 'NASDAQ100'  # NADAQ 100
    reverse_ticker_map['069500.KS'] = 'KOSPI'  # 기존 KODEX 200 매수분 포괄
    
    # CSV에 자산명(KOSPI)으로 바로 쓴 경우도 대비
    for k in domestic_tickers.keys():
        reverse_ticker_map[k] = k

    # 모든 대상 티커 (기본 + 현재 보유 중인 티커)
    all_tickers_to_fetch = set(domestic_tickers.values()).union(actual_holdings.keys())
    
    for ticker in all_tickers_to_fetch:
        try:
            hist = yf.Ticker(ticker).history(period='5d') # 1d 대신 5d로 휴장일/데이터 누락 대비
            if not hist.empty:
                current_prices[ticker] = float(hist['Close'].iloc[-1])
            else:
                current_prices[ticker] = 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch price for {ticker}: {e}")
            current_prices[ticker] = 0.0

    # Report 생성 시 하위 호환을 위해 asset 이름으로도 가격 세팅
    for asset, ticker in domestic_tickers.items():
        if ticker in current_prices:
            current_prices[asset] = current_prices[ticker]
            
    logger.info(f"Loaded current_prices: {current_prices}")

    total_eval_value = 0.0
    for csv_ticker, qty in actual_holdings.items():
        # 평가액 계산 시 해당 종목의 "진짜 종가"를 반영
        price = current_prices.get(csv_ticker, 0.0)
        logger.info(f"Evaluating {csv_ticker} (Qty: {qty}) with price: {price}")
        total_eval_value += (qty * price)

    invested_by_ticker = am.get_investment_by_ticker()

    # 잔여 캐시 (계획자본 - 총투입원금)
    cash_balance = planned_capital - total_invested_original
    current_total_portfolio = total_eval_value + cash_balance

    target_configs = {
        'NASDAQ100': (config.weight_nasdaq100, config.va_growth_rate_nasdaq100),
        'KOSPI': (config.weight_kospi, config.va_growth_rate_kospi),
        'VEA': (config.weight_vea, config.va_growth_rate_vea),
        'COPPER': (config.weight_copper, config.va_growth_rate_copper),
        'TLT': (config.weight_tlt, config.va_growth_rate_tlt),
        'GLD': (config.weight_gld, config.va_growth_rate_gld),
        'SHV': (config.weight_shv, config.va_growth_rate_shv)
    }

    report_data = []
    for asset_name, (weight, growth_rate) in target_configs.items():
        # 목표 평가액
        base_allocation = planned_capital * weight
        target_value = base_allocation * ((1 + growth_rate) ** elapsed_months)
        
        # 현재 평가액 계산 및 현재 수량 계산
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
        va_max_purchase_cap = config.va_max_purchase_cap
        tolerance_band = config.tolerance_band_kospi
        
        if diff > 0:
            # 매수: 1회 최대 매수 상한선(현금 고갈 방어)
            dynamic_max_buy = target_value * va_max_purchase_cap
            base_action_amount = min(diff, dynamic_max_buy)
        elif diff < 0:
            # 매도: 초과분
            # 허용 오차 밴드(Tolerance Band)
            exceed_ratio = abs(diff) / target_value
            if exceed_ratio > tolerance_band:
                pure_exceed_value = abs(diff) - (target_value * tolerance_band)
                base_action_amount = -(pure_exceed_value * 0.5)
            else:
                base_action_amount = 0.0
        # -------------------------------------------------------------------------
        
        # 🔥 중동 전쟁 & 인플레이션 매크로 오버라이드 반영 (Macro Override Rules)
        # 1. NASDAQ100: 지정학적 불확실성 관망, 최소 진입 (권고액의 25%)
        # 2. KOSPI: 위험 자산 회피, 전면 보류 (0%)
        # 3. GLD: 금리 상승 우려로 인한 단기 하락, 분할 진입 (권고액의 50%)
        # 4. SHV: 나머지 컷된 현금을 모두 모아 달러 기반 파킹 (기존 산출액 + 다른 자산에서 아낀 금액)
        override_ratio = 1.0
        override_msg = ""
        
        if asset_name in macro_overrides:
            override_ratio = macro_overrides[asset_name].get('override_ratio', 1.0)
            override_msg = macro_overrides[asset_name].get('override_msg', '')
        else:
            # Fallback 로직
            override_ratio = 1.0
            override_msg = "설정값 없음: 100% 기본 진입"
            
        final_action_amount = base_action_amount * override_ratio
        
        report_data.append({
            'Asset': asset_name,
            'Target_Weight': f"{weight*100:.1f}%",
            'Target_Value': target_value,
            'Current_Value': current_val,
            'Gap': diff,
            'Base_Action_Amount': base_action_amount, # 원본 기록
            'Action_Amount': final_action_amount,     # 오버라이드된 실제 매수액
            'Override_Msg': override_msg,
            'Current_Qty': current_qty,
            'Cumulative_Profit': cumulative_profit,
            'Invested_Principal': invested_principal
        })
        
    # --- 🔵 SHV 잔여 현금 전액 몰아주기 (Sweep to SHV) ---
    # NASDAQ100, KOSPI, GLD에서 매수 보류(Cut)되어 남은 현금을 계산해서 SHV 권고액에 추가합산
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

    # 5. 리포트 생성
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
        
        # 국내 ETF 매핑
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
            
            # Format profit with + sign
            profit_str = f"+{row['Cumulative_Profit']:,.0f}" if row['Cumulative_Profit'] > 0 else f"{row['Cumulative_Profit']:,.0f}"
            
            f.write(f"| {row['Asset']} | {name} | {code} | {row['Invested_Principal']:,.0f} | {row['Current_Value']:,.0f} | {profit_str} | **{row['Action_Amount']:,.0f}** | 약 {qty:.1f} 주 | {row['Override_Msg']} |\n")

        f.write("\n> **참고**: 위 예상 수량은 당일 국내 ETF 종가를 바탕으로 산출된 근사치입니다. 실제 매수 시 증권사 앱의 호가를 확인하세요.\n")

    logger.info(f"Report generated: {report_path}")

if __name__ == "__main__":
    generate_report()
