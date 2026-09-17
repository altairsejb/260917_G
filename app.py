import os
import random
import statistics
from datetime import date
from xml.etree import ElementTree

import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
app.config['DATABASE_URL'] = os.environ['DATABASE_URL']
app.config['JSON_AS_ASCII'] = False

MOLIT_API_KEY = os.environ.get('MOLIT_API_KEY', '').strip()
MOLIT_BASE_URL = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'
PYEONG = 3.3058  # 1평 = 3.3058 m^2

# 서울 25개 자치구 법정동코드(앞 5자리) - 국토부 실거래가 API의 LAWD_CD 파라미터
SEOUL_REGIONS = [
    {'code': '11110', 'name': '종로구'}, {'code': '11140', 'name': '중구'},
    {'code': '11170', 'name': '용산구'}, {'code': '11200', 'name': '성동구'},
    {'code': '11215', 'name': '광진구'}, {'code': '11230', 'name': '동대문구'},
    {'code': '11260', 'name': '중랑구'}, {'code': '11290', 'name': '성북구'},
    {'code': '11305', 'name': '강북구'}, {'code': '11320', 'name': '도봉구'},
    {'code': '11350', 'name': '노원구'}, {'code': '11380', 'name': '은평구'},
    {'code': '11410', 'name': '서대문구'}, {'code': '11440', 'name': '마포구'},
    {'code': '11470', 'name': '양천구'}, {'code': '11500', 'name': '강서구'},
    {'code': '11530', 'name': '구로구'}, {'code': '11545', 'name': '금천구'},
    {'code': '11560', 'name': '영등포구'}, {'code': '11590', 'name': '동작구'},
    {'code': '11620', 'name': '관악구'}, {'code': '11650', 'name': '서초구'},
    {'code': '11680', 'name': '강남구'}, {'code': '11710', 'name': '송파구'},
    {'code': '11740', 'name': '강동구'},
]

# 자치구별 대략적 평당 시세(만원) 기준값 - 목업 데이터 생성용
BASE_PRICE_BY_REGION = {
    '11680': 8800, '11650': 8200, '11710': 6800, '11740': 5200,
    '11215': 5000, '11440': 4800, '11170': 5800, '11590': 4600,
    '11200': 5400, '11560': 4200, '11470': 4400,
}
DEFAULT_BASE_PRICE = 3200

DONG_NAMES_BY_REGION = {
    '11680': ['역삼동', '삼성동', '대치동', '논현동', '청담동'],
    '11650': ['서초동', '반포동', '잠원동', '양재동'],
    '11710': ['잠실동', '문정동', '가락동', '오금동'],
    '11440': ['합정동', '공덕동', '망원동', '연남동'],
}
APT_PREFIXES = ['래미안', '푸르지오', '자이', '힐스테이트', '아이파크', 'e편한세상', '롯데캐슬', '더샵']
UNIT_AREAS = [59.9, 74.8, 84.9, 101.5, 114.7]


def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(app.config['DATABASE_URL'], cursor_factory=RealDictCursor)
    return g.db


def execute(db, sql, params=None):
    cur = db.cursor()
    cur.execute(sql, params or [])
    return cur


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    execute(db, '''
        CREATE TABLE IF NOT EXISTS apartment_trades (
            id SERIAL PRIMARY KEY,
            lawd_cd TEXT NOT NULL,
            deal_ymd TEXT NOT NULL,
            umd_nm TEXT,
            apt_name TEXT,
            exclusive_area NUMERIC,
            deal_amount INTEGER,
            deal_year INTEGER,
            deal_month INTEGER,
            deal_day INTEGER,
            floor INTEGER,
            build_year INTEGER,
            source TEXT DEFAULT 'mock',
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lawd_cd, deal_ymd, apt_name, exclusive_area, deal_amount, deal_day, floor)
        )
    ''')
    db.commit()


def price_per_pyeong(deal_amount_man, exclusive_area_m2):
    if not exclusive_area_m2:
        return 0
    return round(deal_amount_man / (exclusive_area_m2 / PYEONG))


def fetch_from_molit(lawd_cd, deal_ymd):
    """국토부 실거래가 공개시스템(공공데이터포털) 아파트매매 실거래 상세자료 API 호출."""
    params = {'LAWD_CD': lawd_cd, 'DEAL_YMD': deal_ymd, 'numOfRows': '200', 'pageNo': '1'}
    if '%' in MOLIT_API_KEY:
        # 이미 URL 인코딩된 서비스키인 경우 이중 인코딩을 피하기 위해 직접 쿼리스트링을 구성
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        resp = requests.get(f'{MOLIT_BASE_URL}?serviceKey={MOLIT_API_KEY}&{qs}', timeout=10)
    else:
        resp = requests.get(MOLIT_BASE_URL, params={**params, 'serviceKey': MOLIT_API_KEY}, timeout=10)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.content)
    header_code = root.findtext('.//resultCode')
    if header_code not in (None, '00', '000'):
        raise RuntimeError(f'MOLIT API error: {root.findtext(".//resultMsg")}')

    def text(item, *tag_candidates):
        for tag in tag_candidates:
            el = item.find(tag)
            if el is not None and el.text:
                return el.text.strip()
        return None

    items = []
    for item in root.findall('.//item'):
        deal_amount_raw = text(item, 'dealAmount', '거래금액')
        exclusive_area_raw = text(item, 'excluUseAr', '전용면적')
        if not deal_amount_raw or not exclusive_area_raw:
            continue
        items.append({
            'apt_name': text(item, 'aptNm', '아파트') or '',
            'umd_nm': text(item, 'umdNm', '법정동') or '',
            'exclusive_area': float(exclusive_area_raw),
            'deal_amount': int(deal_amount_raw.replace(',', '').strip()),
            'deal_year': int(text(item, 'dealYear', '년') or 0),
            'deal_month': int(text(item, 'dealMonth', '월') or 0),
            'deal_day': int(text(item, 'dealDay', '일') or 0),
            'floor': int(text(item, 'floor', '층') or 0),
            'build_year': int(text(item, 'buildYear', '건축년도') or 0),
        })
    return items


def generate_mock_trades(lawd_cd, deal_ymd):
    """API 키가 없거나 호출에 실패했을 때 사용하는 결정적(seed 고정) 샘플 데이터."""
    rnd = random.Random(f'{lawd_cd}-{deal_ymd}')
    year, month = int(deal_ymd[:4]), int(deal_ymd[4:6])
    base_price = BASE_PRICE_BY_REGION.get(lawd_cd, DEFAULT_BASE_PRICE)
    dong_names = DONG_NAMES_BY_REGION.get(lawd_cd, ['중앙동', '신흥동', '본동'])

    items = []
    for _ in range(rnd.randint(12, 24)):
        area = rnd.choice(UNIT_AREAS)
        noise = rnd.uniform(0.88, 1.15)
        pyeong_price = base_price * noise
        deal_amount = round(pyeong_price * (area / PYEONG))
        items.append({
            'apt_name': f'{rnd.choice(dong_names)}{rnd.choice(APT_PREFIXES)}',
            'umd_nm': rnd.choice(dong_names),
            'exclusive_area': area,
            'deal_amount': deal_amount,
            'deal_year': year,
            'deal_month': month,
            'deal_day': rnd.randint(1, 28),
            'floor': rnd.randint(2, 25),
            'build_year': rnd.randint(1998, 2023),
        })
    return items


def get_trades(lawd_cd, deal_ymd):
    """캐시(Supabase) 우선 조회 -> 없으면 국토부 API(또는 목업) 호출 후 캐싱."""
    db = get_db()
    cached = execute(db, '''
        SELECT * FROM apartment_trades WHERE lawd_cd = %s AND deal_ymd = %s
    ''', (lawd_cd, deal_ymd)).fetchall()
    if cached:
        source = cached[0]['source']
        return [dict(row) for row in cached], source

    source = 'mock'
    items = []
    if MOLIT_API_KEY:
        try:
            items = fetch_from_molit(lawd_cd, deal_ymd)
            source = 'molit'
        except Exception:
            items = []
    if not items:
        items = generate_mock_trades(lawd_cd, deal_ymd)
        source = 'mock'

    cur = db.cursor()
    for it in items:
        cur.execute('''
            INSERT INTO apartment_trades
                (lawd_cd, deal_ymd, umd_nm, apt_name, exclusive_area, deal_amount,
                 deal_year, deal_month, deal_day, floor, build_year, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        ''', (lawd_cd, deal_ymd, it['umd_nm'], it['apt_name'], it['exclusive_area'],
              it['deal_amount'], it['deal_year'], it['deal_month'], it['deal_day'],
              it['floor'], it['build_year'], source))
    db.commit()

    rows = execute(db, '''
        SELECT * FROM apartment_trades WHERE lawd_cd = %s AND deal_ymd = %s
    ''', (lawd_cd, deal_ymd)).fetchall()
    return [dict(row) for row in rows], source


def recent_year_months(months):
    today = date.today()
    result = []
    y, m = today.year, today.month
    for _ in range(months):
        result.append(f'{y}{m:02d}')
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(result))


with app.app_context():
    init_db()


@app.route('/')
def index():
    return render_template('index.html', regions=SEOUL_REGIONS)


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'message': 'Apartment Price Estimator backend is running',
        'molit_api_configured': bool(MOLIT_API_KEY),
    })


@app.route('/api/regions')
def regions():
    return jsonify(SEOUL_REGIONS)


@app.route('/api/trades')
def trades():
    lawd_cd = request.args.get('lawd_cd', '').strip()
    deal_ymd = request.args.get('deal_ymd', '').strip()
    if not lawd_cd or not deal_ymd:
        return jsonify({'error': 'lawd_cd, deal_ymd 파라미터가 필요합니다.'}), 400

    items, source = get_trades(lawd_cd, deal_ymd)
    for it in items:
        it['price_per_pyeong'] = price_per_pyeong(it['deal_amount'], float(it['exclusive_area']))
    items.sort(key=lambda r: (r['deal_year'], r['deal_month'], r['deal_day']), reverse=True)
    return jsonify({'source': source, 'count': len(items), 'items': items})


@app.route('/api/analysis')
def analysis():
    lawd_cd = request.args.get('lawd_cd', '').strip()
    months = min(max(int(request.args.get('months', 6)), 1), 24)
    premium_rate = min(max(float(request.args.get('premium_rate', 0.05)), 0), 1)

    if not lawd_cd:
        return jsonify({'error': 'lawd_cd 파라미터가 필요합니다.'}), 400

    ym_list = recent_year_months(months)
    monthly = []
    all_items = []
    overall_source = 'molit'
    for ymd in ym_list:
        items, source = get_trades(lawd_cd, ymd)
        if source == 'mock':
            overall_source = 'mock'
        prices = [price_per_pyeong(it['deal_amount'], float(it['exclusive_area'])) for it in items]
        all_items.extend(items)
        monthly.append({
            'year_month': ymd,
            'count': len(prices),
            'avg_price_per_pyeong': round(statistics.mean(prices)) if prices else None,
            'median_price_per_pyeong': round(statistics.median(prices)) if prices else None,
        })

    all_prices = [price_per_pyeong(it['deal_amount'], float(it['exclusive_area'])) for it in all_items]
    if not all_prices:
        return jsonify({
            'source': overall_source, 'lawd_cd': lawd_cd, 'months': months,
            'sample_count': 0, 'monthly': monthly, 'estimate': None,
        })

    recent_months_with_data = [m for m in monthly[-3:] if m['avg_price_per_pyeong']]
    recent_avg = (
        round(statistics.mean([m['avg_price_per_pyeong'] for m in recent_months_with_data]))
        if recent_months_with_data else round(statistics.mean(all_prices))
    )
    estimated = round(recent_avg * (1 + premium_rate))

    return jsonify({
        'source': overall_source,
        'lawd_cd': lawd_cd,
        'months': months,
        'sample_count': len(all_prices),
        'avg_price_per_pyeong': round(statistics.mean(all_prices)),
        'median_price_per_pyeong': round(statistics.median(all_prices)),
        'min_price_per_pyeong': min(all_prices),
        'max_price_per_pyeong': max(all_prices),
        'monthly': monthly,
        'estimate': {
            'premium_rate': premium_rate,
            'recent_avg_price_per_pyeong': recent_avg,
            'estimated_new_presale_price_per_pyeong': estimated,
        },
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
