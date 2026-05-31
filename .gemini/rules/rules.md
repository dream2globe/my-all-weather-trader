# My All-Weather Trender - Agent Context & Rules

## 🧠 프로젝트 개요 (Context)
이 프로젝트는 사용자가 본인의 퇴직연금(IRP) 및 개인연금 계좌 운용을 위해 구축한 **동적 자산 배분 백테스트 엔진 및 투자 플랫폼**입니다.
가장 큰 특징은 전통적인 정적 리밸런싱을 넘어선 **'가치평균법(Value Averaging)'**, 그리고 **'변동성 타겟팅 기반 역피라미드(Inverse Pyramid)'**의 결합입니다.

## 🤖 에이전트 룰 (Rules for Next Sessions)
새로운 대화 세션이 시작될 때 AI 에이전트는 무조건 아래의 규칙을 상기합니다.

1. **데이터 소스 및 통일**: 주식/ETF는 `yfinance` 모듈을 통한 `1h`(1시간 봉) 데이터 처리가 핵심입니다. (`use_hourly_data = True`). 모든 타임라인 인덱스는 병합 시 로컬(Naive) 타입으로 통일합니다. (암호화폐는 비활성 상태이나 `pyupbit` 코드는 데이터 수집용으로 유지됨)
2. **투트랙 원칙 지키기 (절대주의!)**: 포트폴리오 계산 엔진(`main.py`, `settings.py`) 내의 메인 종목 티커(SPY, GLD, SHV)를 **결코 함부로 국내 코드로 변경하지 마세요!** 실제 계좌 매매 계획 생성(`generate_live_plan.py`)만이 `actual_trades.csv`의 국내 종목 보유 현황을 엔진 기준과 매핑하여 수행합니다.
3. **가상화폐(Crypto) 비활성**: 현재 BTC/ETH 전략 및 백테스트 실행은 중단된 상태입니다. 자산 배분 비중은 주식(SPY, KOSPI)으로 통합되어 있습니다.
4. **수동 매매 기록 및 계획**: 실제 계좌 매매 내역은 `data/actual_trades.csv`에 기록하며(`Date,Ticker,Action,Price,Quantity,Name` 형식), `generate_live_plan.py`를 실행하여 실제 잔고 기반의 차주 투자 계획을 생성합니다. (금액은 프로그램이 자동 계산함)
5. **코드 수정 제약사항 (Look-ahead Bias)**: 특정 전략(`strategies/`)에 지표(`features/indicators.py`) 기능을 추가할 때 미래 데이터를 참조하면 백테스트 신뢰성이 즉시 훼손되므로 절대 엄금합니다.
6. **결함 방지 및 검증**: 어떠한 리팩터링 및 신규 로직을 파이프라인에 이식하고 나면, 반드시 `pytest tests/` 명령어가 `PASSED`를 반환하는지 스스로 선 검증해야 합니다.
7. **가상 환경 및 명령행 실행**: 이 프로젝트는 `uv`를 통해 생성된 `.venv` 가상 환경 사용을 원칙으로 합니다. 모든 파이썬 실행 및 테스트 시에는 `source .venv/bin/activate` 명령을 먼저 수행하여 가상 환경 내에서 진행해야 합니다.
8. **매크로 오버라이드 유의사항**: 지정학적 리스크나 금리/인플레 등 외부 상황 발생 시, `macro_config.json`을 사용하여 `generate_live_plan.py`의 구매 액션을 오버라이드(override) 합니다. 코드를 하드코딩하지 않고 환경 설정 파일을 사용합니다.
