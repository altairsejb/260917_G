const regionSelect = document.getElementById('region-select');
const customCodeField = document.getElementById('custom-code-field');
const customCodeInput = document.getElementById('custom-code');
const monthsSelect = document.getElementById('months-select');
const premiumInput = document.getElementById('premium-input');
const analyzeBtn = document.getElementById('analyze-btn');
const resultSection = document.getElementById('result-section');
const loading = document.getElementById('loading');
const errorMessage = document.getElementById('error-message');
const mockBanner = document.getElementById('mock-banner');

function fmt(n) {
  if (n === null || n === undefined) return '-';
  return n.toLocaleString('ko-KR');
}

regionSelect.addEventListener('change', () => {
  customCodeField.classList.toggle('hidden', regionSelect.value !== '__custom__');
});

function getLawdCd() {
  if (regionSelect.value === '__custom__') {
    return customCodeInput.value.trim();
  }
  return regionSelect.value;
}

async function runAnalysis() {
  const lawdCd = getLawdCd();
  if (!lawdCd || lawdCd.length !== 5) {
    showError('법정동코드는 5자리 숫자여야 합니다.');
    return;
  }

  errorMessage.classList.add('hidden');
  resultSection.classList.add('hidden');
  loading.classList.remove('hidden');

  const months = monthsSelect.value;
  const premiumRate = (parseFloat(premiumInput.value) || 0) / 100;

  try {
    const [analysisRes, tradesRes] = await Promise.all([
      fetch(`/api/analysis?lawd_cd=${lawdCd}&months=${months}&premium_rate=${premiumRate}`),
      fetch(`/api/trades?lawd_cd=${lawdCd}&deal_ymd=${currentYearMonth()}`),
    ]);

    if (!analysisRes.ok) throw new Error('분석 데이터를 불러오지 못했습니다.');
    const analysis = await analysisRes.json();
    const tradesData = tradesRes.ok ? await tradesRes.json() : { items: [] };

    renderAnalysis(analysis);
    renderTrades(tradesData.items || []);
    mockBanner.classList.toggle('hidden', analysis.source !== 'mock');
    resultSection.classList.remove('hidden');
  } catch (err) {
    showError(err.message || '요청 중 오류가 발생했습니다.');
  } finally {
    loading.classList.add('hidden');
  }
}

function currentYearMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}${m}`;
}

function renderAnalysis(data) {
  if (!data.estimate) {
    document.getElementById('estimated-price').textContent = '데이터 없음';
    document.getElementById('estimate-note').textContent = '';
    document.getElementById('recent-avg-price').textContent = '-';
    document.getElementById('avg-price').textContent = '-';
    document.getElementById('median-price').textContent = '-';
    document.getElementById('sample-count').textContent = '0';
    document.getElementById('price-range').textContent = '-';
    document.querySelector('#monthly-table tbody').innerHTML = '';
    return;
  }

  document.getElementById('estimated-price').textContent = `${fmt(data.estimate.estimated_new_presale_price_per_pyeong)}만원`;
  document.getElementById('estimate-note').textContent =
    `최근 3개월 평균 대비 +${Math.round(data.estimate.premium_rate * 100)}% 프리미엄 적용`;
  document.getElementById('recent-avg-price').textContent = `${fmt(data.estimate.recent_avg_price_per_pyeong)}만원`;
  document.getElementById('avg-price').textContent = `${fmt(data.avg_price_per_pyeong)}만원`;
  document.getElementById('median-price').textContent = `${fmt(data.median_price_per_pyeong)}만원`;
  document.getElementById('sample-count').textContent = `${fmt(data.sample_count)}건`;
  document.getElementById('price-range').textContent = `${fmt(data.min_price_per_pyeong)} ~ ${fmt(data.max_price_per_pyeong)}만원`;

  const tbody = document.querySelector('#monthly-table tbody');
  tbody.innerHTML = data.monthly.map(m => `
    <tr>
      <td>${m.year_month.slice(0, 4)}-${m.year_month.slice(4)}</td>
      <td>${fmt(m.count)}</td>
      <td>${m.avg_price_per_pyeong ? fmt(m.avg_price_per_pyeong) + '만원' : '-'}</td>
      <td>${m.median_price_per_pyeong ? fmt(m.median_price_per_pyeong) + '만원' : '-'}</td>
    </tr>
  `).join('');
}

function renderTrades(items) {
  const tbody = document.querySelector('#trades-table tbody');
  tbody.innerHTML = items.slice(0, 30).map(it => `
    <tr>
      <td>${it.deal_year}-${String(it.deal_month).padStart(2, '0')}-${String(it.deal_day).padStart(2, '0')}</td>
      <td>${it.apt_name}</td>
      <td>${it.umd_nm}</td>
      <td>${it.exclusive_area}</td>
      <td>${it.floor}</td>
      <td>${fmt(it.deal_amount)}</td>
      <td>${fmt(it.price_per_pyeong)}</td>
    </tr>
  `).join('');
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorMessage.classList.remove('hidden');
}

analyzeBtn.addEventListener('click', runAnalysis);
