# 영농형 태양광 경제성 계산기

농가가 자기 농지 조건을 입력하면 영농형 태양광 도입 시 수익성(B/C, IRR, 회수기간)을 즉시 확인할 수 있는 의사결정 도구입니다.

KREI(2023) 「영농형 태양광 도입의 경제성 분석」 보고서의 모델을 기반으로 하되, 2026년 5월 기준 시장 데이터와 농지법 개정(일시사용허가 8년 → 23년)을 반영했습니다.

## 기본 가정 (2026 v1.0)

- 대상 지역: 전라남도 (확장 가능 구조)
- 대상 작물: 논벼 (확장 가능 구조)
- 시설 규모: 99 kW / 2,000 ㎡
- 운영 기간: 23년 (농지법 개정)
- 발전가격: RPS 트랙(SMP+REC×1.2) / PPA 트랙(고정가격계약) 선택

## 프로젝트 구조

```
agpv_economics/
├── app.py                    # Streamlit 진입점 (Phase 2)
├── assumptions.yaml          # 모든 기본 가정값 (중앙 관리)
├── core/
│   ├── calculator.py         # NPV/B/C/IRR 계산 엔진
│   ├── finance.py            # 융자 상환 스케줄
│   └── scenarios.py          # 시나리오 빌더
├── tests/
│   └── test_pdf_replication.py  # KREI(2023) 표 재현 검증
└── data/
    ├── regions.json          # 시도별 데이터 (전남 활성)
    └── crops.json            # 작물별 데이터 (벼 활성)
```

## 개발 단계

- [x] Phase 1: 계산 엔진 + PDF 검증
- [ ] Phase 2: Streamlit UI (사이드바 + 결과)
- [ ] Phase 3: 시나리오 비교 + 차트
- [ ] Phase 4: PDF 보고서 생성
- [ ] Phase 5: Streamlit Cloud 배포 + KIFC iframe 임베드

## 실행

```bash
pip install -r requirements.txt
pytest tests/                 # PDF 검증
streamlit run app.py          # 앱 실행 (Phase 2 이후)
```

## 출처

- KREI(2023). 「영농형 태양광 도입의 경제성 분석」 4장
- 한국전력거래소 EPSIS (SMP·REC 가격)
- 한국에너지공단 신재생에너지센터 (REC 가중치, 금융지원사업)
- 재생에너지법 개정안 (2026.02.12 국회 통과)
