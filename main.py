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

# --- 2. 한국 시간 기준으로 날짜 설정 ---
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
yesterday_dt = now_kst - timedelta(days=1)

st.title("🎬 일일 박스오피스 순위")

# 날짜 선택 기능 추가 (최대 선택 가능한 날짜는 '어제')
selected_date = st.date_input(
    "조회할 날짜를 선택하세요 (어제 날짜까지만 조회 가능합니다)",
    value=yesterday_dt.date(),
    max_value=yesterday_dt.date()
)
target_dt = selected_date.strftime('%Y%m%d')

# --- 3. 데이터 불러오기 함수 (캐싱 적용) ---
@st.cache_data(ttl=3600)
def fetch_box_office(date_str, api_key):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": date_str
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() 
        data = response.json()
        
        if "faultInfo" in data:
            return {"error": data["faultInfo"].get("message", "API 키 오류 등 문제가 발생했어.")}
            
        if "boxOfficeResult" in data and "dailyBoxOfficeList" in data["boxOfficeResult"]:
            return {"data": data["boxOfficeResult"]["dailyBoxOfficeList"]}
            
        return {"error": "API에서 예상치 못한 형태의 데이터를 보냈어."}
        
    except Exception as e:
        return {"error": f"네트워크 오류나 기타 문제가 발생했어: {e}"}

# --- 4. 메인 로직 및 에러 핸들링 ---
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 보안 금고(secrets)에 `KOBIS_KEY`가 없어! Streamlit Cloud 설정에서 추가해 줘.")
    st.stop() 

api_key = st.secrets["KOBIS_KEY"]

with st.spinner("박스오피스 데이터를 가져오는 중이야..."):
    result = fetch_box_office(target_dt, api_key)

if "error" in result:
    st.error(f"🚨 데이터를 불러오지 못했어. 다음 내용을 확인해 봐!\n\n**상세 메시지:** {result['error']}")
    st.info("💡 팁: API 키가 정확한지, 하루 호출 한도를 초과하지 않았는지 확인해 줘.")
    st.stop()

movie_list = result.get("data", [])

# 선택한 날짜의 데이터가 비어있는 경우 (집계 전)
if not movie_list:
    st.warning("그날은 아직 집계 전입니다. 다른 날짜를 선택해 봐!")
    st.stop()

# --- 5. 데이터 가공 (타입 변환 및 조건부 데이터 생성) ---
df = pd.DataFrame(movie_list)

cols_to_int = ['rank', 'rankInten', 'audiCnt', 'audiAcc', 'scrnCnt']
for col in cols_to_int:
    df[col] = df[col].astype(int)

# 누적 관객 100만 이상인 영화명에 트로피(🏆) 붙이기
df['movieNm_disp'] = df.apply(
    lambda row: f"🏆 {row['movieNm']}" if row['audiAcc'] >= 1000000 else row['movieNm'], 
    axis=1
)

# 순위 증감에 따른 화살표 표시 로직 (문자열로 반환)
def format_rank_inten(val):
    if val > 0:
        return f"🔺 {val}" # 양수면 빨간 위 화살표
    elif val < 0:
        return f"🔻 {abs(val)}" # 음수면 파란 아래 화살표
    else:
        return "-"

df['rankInten_disp'] = df['rankInten'].apply(format_rank_inten)

# --- 6. 1위 영화 지표 카드 (KPI) ---
top_movie = df.iloc[0] 
st.subheader(f"🥇 영예의 1위: {top_movie['movieNm']}")

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

# 새롭게 생성한 증감 컬럼(rankInten_disp)과 영화명 컬럼(movieNm_disp)을 사용
display_df = df[['rank', 'rankInten_disp', 'movieNm_disp', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
display_df.columns = ['순위', '순위변동', '영화명', '개봉일', '일일관객수', '누적관객수', '스크린수']

st.dataframe(
    display_df.style.format({
        '일일관객수': '{:,}',
        '누적관객수': '{:,}',
        '스크린수': '{:,}'
    }),
    use_container_width=True,
    hide_index=True
)
