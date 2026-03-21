import pandas as pd
import os
from typing import Dict

class AccountManager:
    def __init__(self, trade_log_path: str = 'data/actual_trades.csv'):
        self.trade_log_path = trade_log_path
        
    def get_current_holdings(self) -> Dict[str, float]:
        """
        주어진 매매 기록(CSV)을 읽어 현재 보유 중인 종목별 수량을 계산합니다.
        Returns:
            {'069500.KS': 195, 'SPY': 0, ...}
        """
        if not os.path.exists(self.trade_log_path):
            return {}
            
        df = pd.read_csv(self.trade_log_path)
        if df.empty:
            return {}
            
        # Ticker별 수량 합산 (BUY는 +, SELL은 -)
        holdings = {}
        for _, row in df.iterrows():
            ticker = row['Ticker']
            qty = row['Quantity']
            action = row['Action'].upper()
            
            if action == 'BUY':
                holdings[ticker] = holdings.get(ticker, 0.0) + qty
            elif action == 'SELL':
                holdings[ticker] = holdings.get(ticker, 0.0) - qty
                
        return holdings

    def get_total_investment(self) -> float:
        """총 투입 원금을 계산합니다 (Price * Quantity)."""
        if not os.path.exists(self.trade_log_path):
            return 0.0
            
        df = pd.read_csv(self.trade_log_path)
        # BUY일 때 투입, SELL일 때 회수
        total = 0.0
        for _, row in df.iterrows():
            # Amount가 없으므로 직접 계산
            amount = row['Price'] * row['Quantity']
            if row['Action'].upper() == 'BUY':
                total += amount
            else:
                total -= amount
        return total

    def get_investment_by_ticker(self) -> Dict[str, float]:
        """티커별 투입 원금을 계산합니다."""
        if not os.path.exists(self.trade_log_path):
            return {}
            
        df = pd.read_csv(self.trade_log_path)
        investment = {}
        for _, row in df.iterrows():
            ticker = row['Ticker']
            amount = row['Price'] * row['Quantity']
            if row['Action'].upper() == 'BUY':
                investment[ticker] = investment.get(ticker, 0.0) + amount
            else:
                investment[ticker] = investment.get(ticker, 0.0) - amount
        return investment

