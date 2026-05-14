# 영농형 태양광 경제성 계산기

농가가 자기 농지 조건을 입력하면 영농형 태양광 도입 시 수익성(B/C, IRR, 회수기간, 월별 통장 흐름)을 즉시 확인할 수 있는 의사결정 도구입니다.

KREI(2023) 「영농형 태양광 도입의 경제성 분석」 보고서의 모델을 기반으로 하되, 2026년 5월 기준 시장 데이터와 농지법 개정(2026.05.07 국회 통과, 일시사용허가 8년 → 23년)을 반영했습니다.

## 기본 가정 (2026 v1.1)

- 대상 지역: 전라남도 (확장 가능 구조)
- 대상 작물: 논벼 (확장 가능 구조)
- 시설 규모: 99 kW / 2,000 ㎡
- 운영 기간: 23년 (농지법 개정)
- 발전가격: RPS 트랙(SMP+REC×1.2) / PPA 트랙(고정가격계약) 선택

## 프로젝트 구조

```
agpv_economics/
├── app.py                    # Streamlit 진입점
├── assumptions.yaml          # 모든 기본 가정값 (중앙 관리)
├── .streamlit/config.toml    # Streamlit 테마·서버 설정
├── core/
│   ├── calculator.py         # NPV/B/C/IRR 엔진
│   ├── finance.py            # 거치+원금균등 대출 스케줄
│   ├── monthly.py            # 실제 월별 현금흐름 (regime 블록)
│   ├── scenarios.py          # 시나리오 빌더
│   └── config.py             # assumptions.yaml 로더
├── ui/
│   ├── __init__.py
│   └── tabs.py               # 6개 탭 렌더링
├── tests/
│   └── test_pdf_replication.py  # KREI(2023) 표 재현 검증
├── requirements.txt          # 프로덕션 의존성
├── requirements-dev.txt      # 개발용 (pytest 등)
└── .github/workflows/
    └── keep-alive.yml        # Streamlit Cloud sleep 방지
```

## 로컬 실행

```bash
# 가상환경 만들기 (선택)
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt -r requirements-dev.txt

# 테스트 (PDF 재현 검증)
pytest tests/

# 앱 실행
streamlit run app.py
```

브라우저에서 http://localhost:8501 자동 열림.

## Streamlit Cloud 배포

### 1단계: share.streamlit.io 배포

1. https://share.streamlit.io 접속 → **Continue with GitHub** 로그인
2. 우상단 **New app** 클릭
3. 다음 정보 입력:
   - **Repository**: `eastrover-collab/agpv-roi-calculator`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **Python version**: `3.12` (또는 3.11)
   - **App URL** (선택): `agpv-roi-calculator` (기본 추천명 그대로 OK)
4. **Deploy!** 클릭 → 약 3~5분 빌드 → 발급 URL 표시
   - 예: `https://agpv-roi-calculator.streamlit.app`

### 2단계: Sleep 방지 (선택)

무료 플랜은 12시간 트래픽 없으면 hibernate되어 첫 방문 시 10~30초 콜드스타트.
`.github/workflows/keep-alive.yml`이 자동으로 6시간마다 ping해서 깨워줍니다.

배포 URL이 위 예시와 다르면:
- GitHub repo Settings → Secrets and variables → Actions → **New repository secret**
- 이름: `STREAMLIT_APP_URL`, 값: 실제 배포 URL

### 3단계: KIFC 워드프레스 iframe 임베드

워드프레스 페이지에 **HTML 블록** (또는 "사용자 정의 HTML" 위젯) 추가 후 아래 코드 삽입:

```html
<!-- 영농형 태양광 경제성 계산기 임베드 -->
<div style="position: relative; width: 100%; min-height: 900px;">
  <iframe
    src="https://agpv-roi-calculator.streamlit.app/?embed=true&embed_options=hide_loading_screen,show_padding,light_theme"
    style="width: 100%; height: 100%; min-height: 900px; border: 0; border-radius: 8px;"
    allowfullscreen
    loading="lazy"
    title="영농형 태양광 경제성 계산기"
  ></iframe>
</div>

<p style="font-size: 0.85em; color: #6b7280; margin-top: 8px;">
  💡 모바일에서는 별도 창으로 열어 사용하시면 더 편합니다 →
  <a href="https://agpv-roi-calculator.streamlit.app" target="_blank" rel="noopener">새 창에서 열기</a>
</p>
```

**`?embed=true` 옵션**:
- `hide_loading_screen`: 로딩 화면 숨김 (즉시 콘텐츠 표시)
- `show_padding`: 적당한 여백 유지
- `light_theme`: 강제 라이트 모드 (KIFC 사이트와 일관)

**모바일 반응형**: 화면 너비 768px 미만에서는 사이드바 자동 축소.
사용자가 좌측 햄버거 메뉴 클릭하면 입력 폼 표시.

### 4단계: 배포 후 점검

배포 URL 접속 후 다음을 확인:
- [ ] 사이드바 4단계 색상 표시되는지
- [ ] 6개 탭 모두 동작 (한눈에 / 월별 / 23년 / 시나리오 / 리스크 / 전문가)
- [ ] 차트(Plotly)가 정상 렌더링되는지
- [ ] 하단 KREI(2023) → 2026 비교 expander 동작

## 출처

- KREI(2023). 「영농형 태양광 도입의 경제성 분석」 4장
- 한국전력거래소 EPSIS (SMP·REC 가격, 2026.1~4월 평균)
- 한국에너지공단 신재생에너지센터 (REC 가중치, 금융지원사업)
- 통계청 KOSIS 농가경제조사 (논벼 소득)
- 전남도농업기술원 + 영암군 실증 (단수 감소 21%)
- 재생에너지법 개정안 (2026.05.07 국회 통과)

## 라이선스

본 계산기는 농가·정책담당자·연구자 누구나 자유롭게 사용 가능합니다.
KREI 보고서의 모델 구조와 가정값은 원 보고서를 따르며, 본 코드는 그 모델의 재구현 + 2026 데이터 적용입니다.

## 문의

- GitHub Issues: https://github.com/eastrover-collab/agpv-roi-calculator/issues
- KIFC (사단법인 식량과기후): 홈페이지 참조

---

⚠️ 본 계산기는 추정치입니다. 실제 도입 결정 전 한국에너지공단(1855-3020) 또는 농협 상담 권장.
