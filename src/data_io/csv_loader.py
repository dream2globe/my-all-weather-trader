import os
import pandas as pd
from typing import Dict, List, Optional
from data_io.api_fetcher import fetch_yfinance_hourly, fetch_upbit_hourly
from config.settings import config, setup_logger

logger = setup_logger("csv_loader")

class DataLoader:
    def __init__(self, raw_dir: str = 'data/raw/'):
        self.raw_dir = raw_dir
        os.makedirs(self.raw_dir, exist_ok=True)
        
    def get_synced_portfolio_data(self, tickers: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """
        포트폴리오에 포함된 전체 티커들의 시계열 데이터를 수집하고,
        모든 자산의 타임라인을 주식/ETF 휴장일을 포함하는 마스터 타임라인으로 동기화합니다.
        
        Args:
            tickers: {'SP500': 'SPY', 'KOSPI': '229200.KS', 'BTC': 'KRW-BTC'} 형태
        Returns:
            동기화된 티커별 데이터프레임 딕셔너리
        """
        raw_data = {}
        all_indices = []
        
        # 1. 개별 티커 데이터 로드 (로컬이 없으면 API 패치 후 저장)
        for name, ticker in tickers.items():
            df = self._load_or_fetch(ticker)
            if not df.empty:
                raw_data[name] = df
                all_indices.append(df.index)
                logger.info(f"{name} ({ticker}) loaded. Shape: {df.shape}")
            else:
                logger.error(f"Failed to load data for {name}({ticker})")

        if not raw_data:
            return {}

        # 2. 마스터 인덱스 생성 (타임라인 병합)
        # 타임존 충돌 에러(Tz-aware vs Naive) 방지를 위해 각 인덱스를 일괄 tz-naive 로 통일
        naive_indices = []
        for idx in all_indices:
            if getattr(idx, 'tz', None) is not None:
                naive_indices.append(pd.Series(index=idx.tz_localize(None)))
            else:
                naive_indices.append(pd.Series(index=idx))
                
        master_index = pd.DatetimeIndex(pd.concat(naive_indices).index).unique().sort_values()
        
        # 설정된 시작일(start_date) 기준으로 마스터 인덱스 필터링
        start_ts = pd.to_datetime(config.start_date)
        if getattr(master_index, 'tz', None) is not None:
            start_ts = start_ts.tz_localize(master_index.tz)
        master_index = master_index[master_index >= start_ts]

        # 3. 데이터프레임 타임라인 동기화 (Alignment)
        synced_data = {}
        for name, df in raw_data.items():
            # 병합을 위해 개별 df 역시 tz-naive 처리
            if getattr(df.index, 'tz', None) is not None:
                df.index = df.index.tz_localize(None)
                
            # 마스터 인덱스에 맞춰 Reindex. 휴장일이나 비어있는 봉은 ffill(이전 종가 유지)
            aligned_df = df.reindex(master_index)
            # Volume은 거래가 없었으므로 0으로 충당, 나머지는 가격 유지
            aligned_df['Volume'] = aligned_df['Volume'].fillna(0)
            aligned_df = aligned_df.ffill() 
            
            # 최초 상장일 이전의 NA 데이터는 drop하거나 backward fill을 고민해야 하나, 
            # 백테스트에서는 데이터가 모두 존재하는 시점부터 시작하는 것이 정석이므로 엔진에 위임
            synced_data[name] = aligned_df
            
        logger.info(f"Timeline synchronization complete. Master index length: {len(master_index)}")
        return synced_data

    def _load_or_fetch(self, ticker: str) -> pd.DataFrame:
        """
        로컬 캐시(CSV)가 있으면 로드하고, 없으면 API를 통해 가져와서 저장.
        """
        file_path = os.path.join(self.raw_dir, f"{ticker}.csv")
        
        if os.path.exists(file_path):
            logger.info(f"Loading local cache for {ticker}: {file_path}")
            df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
            return df
        
        # 캐시가 없는 경우 API 호출
        if ticker.startswith('KRW-'):
            df = fetch_upbit_hourly(ticker)
        else:
            df = fetch_yfinance_hourly(ticker)
            
        # 수집 성공 시 로컬 캐싱
        if not df.empty:
            # 타임존 정보 완전 제거 후 캐시 저장 (병합 호환성 확보용)
            if getattr(df.index, 'tz', None) is not None:
                df.index = df.index.tz_localize(None)
            df.to_csv(file_path)
            
        return df
