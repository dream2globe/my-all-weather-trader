import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class BacktestSettings(BaseSettings):
    # 포트폴리오 기본 설정
    initial_investment: float = Field(300_000_000.0, description="초기 자본금(예: 3억 원)")
    
    # 전략별 자산 비중 (연금 30% 안전자산 룰)
    weight_sp500: float = Field(0.25, description="S&P 500 ETF (가치평균법, 25%)")
    weight_kospi: float = Field(0.25, description="KOSPI 200 (가치평균법, 25%)")
    weight_gld: float = Field(0.15, description="금 ETF (가치평균법, 15%)")
    weight_shv: float = Field(0.15, description="미국 단기채 ETF (가치평균법, 안전자산 15%)")
    weight_btc: float = Field(0.05, description="BTC (변동성 기반 역피라미드 매수, 5%)")
    weight_eth: float = Field(0.05, description="ETH (변동성 기반 역피라미드 매수, 5%)")
    cash_buffer_weight: float = Field(0.10, description="대기 현금 (현금성 안전자산 10%)")

    # 가치평균법(VA) 파라미터 (자산별 타겟 경로) — Grid Search 실증 최적값
    va_growth_rate_sp500: float = Field(0.006, description="SPY 월별 목표 복리 성장률 (0.6% -> 실측 CAGR 8.8%)")
    va_growth_rate_kospi: float = Field(0.003, description="KOSPI 월별 목표 복리 성장률 (0.3% -> 실측 CAGR 4.6%)")
    va_growth_rate_gld: float = Field(0.004, description="GLD 월별 목표 복리 성장률 (0.4% -> 실측 CAGR 11.2%)")
    va_growth_rate_shv: float = Field(0.0005, description="SHV 월별 목표 복리 성장률 (0.05% -> 현금성 단기채 보수적 목표)")
    va_growth_rate_btc: float = Field(0.012, description="BTC 월별 목표 복리 성장률 (1.2% -> 코인의 높은 변동성 고려)")
    va_growth_rate_eth: float = Field(0.015, description="ETH 월별 목표 복리 성장률 (1.5% -> 이더리움의 높은 성장세 반영)")
    va_max_purchase_cap: float = Field(0.05, description="가치평균법 1회 최대 매수 허용치(해당 자산 배분액 대비 비율, 예: 5%)")
    tolerance_band_kospi: float = Field(0.05, description="KOSPI 초과 상승 시 곧바로 매도하지 않는 상단 허용 오차 한도 (+5% 이내면 관망)")

    # 역피라미드 매매 & 변동성 타겟팅 기준 (BTC 전용)
    crypto_grid_range: float = Field(0.05, description="가상화폐 그리드 매매 시그널 폭 (예: 5% 단위)")
    mdd_trigger_level_1: float = Field(-0.12, description="역피라미드 1차 매수 진입 MDD 임계값 (-12%)")
    mdd_trigger_level_2: float = Field(-0.25, description="역피라미드 2차 매수 진입 MDD 임계값 (-25%)")
    btc_volatility_target: float = Field(0.05, description="BTC 14일 ATR 비율이 이 수치를 넘으면 폭등/폭락세로 간주하여 보유 물량 50% 강제 현금화 (5%)")
    eth_volatility_target: float = Field(0.06, description="ETH 14일 ATR 비율 타겟 (이더리움은 비트코인보다 변동성이 커서 6%로 설정)")

    # 시스템 / 시뮬레이션 환경 (수수료, 슬리피지 등)
    start_date: str = Field("2019-01-01", description="백테스트 분석 시작일 (코로나 위기 포함 장기 시뮬레이션)")
    stock_commission_rate: float = Field(0.00015, description="주식/ETF 매매 수수료 (예: 0.015%)")
    crypto_commission_rate: float = Field(0.0005, description="가상화폐 매매 수수료 (비트코인 0.05% 기준)")
    slippage_rate: float = Field(0.001, description="매매 시 슬리피지율 (예: 0.1%)")
    
    # 1일봉(Daily) 기반 데이터 로딩 관련 최적화 (시간 단위 잦은 거래 방지)
    use_hourly_data: bool = Field(False, description="1시간 봉 대신 1일(Daily) 봉 단위 데이터 활용 여부")
    
    # 로깅 설정
    log_level: str = Field("INFO", description="기본 로그 레벨(DEBUG, INFO, WARNING, ERROR, CRITICAL)")

    # 유효성 검증(Validation)
    @validator('cash_buffer_weight')
    def check_weights_sum(cls, v, values):
        total_weight = (
            values.get('weight_sp500', 0) +
            values.get('weight_kospi', 0) +
            values.get('weight_gld', 0) +
            values.get('weight_shv', 0) +
            values.get('weight_btc', 0) +
            values.get('weight_eth', 0) +
            v
        )
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"자산 비중의 합은 1.0(100%)이어야 합니다. 현재 합계: {total_weight}")
        return v

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

# 글로벌 설정 인스턴스
config = BacktestSettings()

def setup_logger(name: str) -> logging.Logger:
    """프로젝트 전반에서 사용할 로거 세팅"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(config.log_level)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger
