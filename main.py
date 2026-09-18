import streamlit as st
import pandas as pd
import requests
import pytz
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. 페이지 기본 설정 ---
st.set_page_config(
    page_title="일일 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# --- 2. 한국 시간 기준으로 '어제' 날짜 계산 ---
# 서버 시간이 UTC일 수 있으므로 pytz를 사용해 한국 시간으로 고정해!
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
yesterday = now_kst - timedelta(days=1)
target_dt = yesterday.strftime('%Y%m%d') # 'yyyymmdd' 형식

st.title("🎬 어제의 박스오피스 순위")
st.markdown(f"**조회 날짜:** {yesterday.strftime('%Y년 %m월 %d일')} (한국 시간 기준)")

# --- 3. 데이터 불러오기 함수 (캐싱 적용) ---
# ttl=3600 설정으로 같은 날짜의 요청은 1시간(3600초) 동안 API를 다시 부르지 않고 기억해.
@st.cache_data(ttl=3600)
def fetch_box_office(date_str, api_key):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": date_str
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # HTTP 통신 에러 확인
        data = response.json()
        
        # API 인증키 오류 등의 문제가 있으면 faultInfo가 옴
        if "faultInfo" in data:
            return {"error": data["faultInfo"].get("message", "API 키 오류 등 문제가 발생했어.")}
            
        # 정상 응답일 경우 영화 목록 반환
        if "boxOfficeResult" in data and "dailyBoxOfficeList" in data["boxOfficeResult"]:
            return {"data": data["boxOfficeResult"]["dailyBoxOfficeList"]}
            
        return {"error": "API에서 예상치 못한 형태의 데이터를 보냈어."}
        
    except Exception as e:
        return {"error": f"네트워크 오류나 기타 문제가 발생했어: {e}"}

# --- 4. 메인 로직 및 에러 핸들링 ---
# 스트림릿 클라우드의 secrets에서 API 키를 안전하게 가져오기
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 보안 금고(secrets)에 `KOBIS_KEY`가 없어! Streamlit Cloud 설정에서 추가해 줘.")
    st.stop() # 실행 중단

api_key = st.secrets["KOBIS_KEY"]

with st.spinner("박스오피스 데이터를 가져오는 중이야..."):
    result = fetch_box_office(target_dt, api_key)

# 에러가 발생한 경우 안내 메시지 출력 후 종료
if "error" in result:
    st.error(f"🚨 데이터를 불러오지 못했어. 다음 내용을 확인해 봐!\n\n**상세 메시지:** {result['error']}")
    st.info("💡 팁: API 키가 정확한지, 하루 호출 한도를 초과하지 않았는지 확인해 줘.")
    st.stop()

movie_list = result.get("data", [])

# 영화 목록이 비어있는 경우 (집계 지연 등)
if not movie_list:
    st.warning("어제 날짜의 박스오피스 데이터가 아직 집계되지 않았거나 비어 있어. 나중에 다시 시도해 봐!")
    st.stop()

# --- 5. 데이터 가공 (문자를 숫자로) ---
df = pd.DataFrame(movie_list)

# API는 숫자를 문자로 주니까, 정렬과 계산을 위해 정수형(int)으로 바꿔주자.
cols_to_int = ['rank', 'audiCnt', 'audiAcc', 'scrnCnt']
for col in cols_to_int:
    df[col] = df[col].astype(int)

# --- 6. 1위 영화 지표 카드 (KPI) ---
top_movie = df.iloc[0] # 순위대로 오니 첫 번째가 1위
st.subheader(f"🏆 영예의 1위: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)
col1.metric("오늘 관객수", f"{top_movie['audiCnt']:,}명", f"전일대비 {top_movie['rankInten']} 계단")
col2.metric("누적 관객수", f"{top_movie['audiAcc']:,}명")
col3.metric("상영 스크린 수", f"{top_movie['scrnCnt']:,}개")

st.divider()

# --- 7. 관객수 상위 5편 막대 그래프 ---
st.subheader("📊 관객수 상위 5편")
top5_df = df.head(5)

fig = px.bar(
    top5_df, 
    x='movieNm', 
    y='audiCnt',
    text_auto='.2s',
    title="Top 5 영화 일일 관객수",
    labels={'movieNm': '영화명', 'audiCnt': '관객수'},
    color='audiCnt',
    color_continuous_scale="Blues"
)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# --- 8. 전체 박스오피스 데이터 표 ---
st.subheader("📋 전체 박스오피스 순위표")
# 보여줄 컬럼만 선택하고, 이름도 한글로 예쁘게 바꾸자
display_df = df[['rank', 'movieNm', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
display_df.columns = ['순위', '영화명', '개봉일', '일일관객수', '누적관객수', '스크린수']

# 숫자에 천 단위 콤마를 찍어서 보여주기
st.dataframe(
    display_df.style.format({
        '일일관객수': '{:,}',
        '누적관객수': '{:,}',
        '스크린수': '{:,}'
    }),
    use_container_width=True,
    hide_index=True
)
