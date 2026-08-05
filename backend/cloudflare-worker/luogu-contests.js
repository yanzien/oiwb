// ============================================================================
//  洛谷比赛抓取 Worker（Cloudflare Worker）
//  直连兜底方案：解析 https://www.luogu.com.cn/contest/list 内嵌的
//  JSON.parse(decodeURIComponent("...")) 数据，规避前端 CORS + Cloudflare 验证。
//  - 用 Cache API 缓存 20 分钟，降低频率触发风控的概率
//  - 失败自动返回 502 + 错误信息，前端可优雅降级
//  - 仅用于个人竞赛日历展示，请勿高频轰炸
// ============================================================================

const LUOGU_CONTEST_LIST = 'https://www.luogu.com.cn/contest/list';
const CACHE_TTL = 20 * 60; // 20 分钟
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

function cors() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store'
  };
}

function err(body, status) {
  return new Response(JSON.stringify({ ok: false, error: body }), {
    status, headers: { ...cors(), 'Content-Type': 'application/json; charset=utf-8' }
  });
}

// 解析洛谷比赛列表页，提取内嵌 JSON
async function fetchLuogu(cache) {
  const cacheKey = 'luogu-contests';
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const resp = await fetch(LUOGU_CONTEST_LIST, {
    headers: {
      'User-Agent': UA,
      'Referer': 'https://www.luogu.com.cn/',
      'Accept-Language': 'zh-CN,zh;q=0.9'
    },
    redirect: 'follow'
  });
  if (!resp.ok) throw new Error('luogu http ' + resp.status);
  const html = await resp.text();

  // 匹配 JSON.parse(decodeURIComponent("..."))
  const m = html.match(/JSON\.parse\(decodeURIComponent\("([^"]+)"\)/);
  if (!m) throw new Error('data not found (likely Cloudflare challenge)');
  const raw = decodeURIComponent(m[1]);
  const data = JSON.parse(raw);
  const list = (data.currentData && data.currentData.contests && data.currentData.contests.result) || [];
  const now = Date.now();

  const contests = list
    .filter(c => (c.endTime || 0) * 1000 > now) // 只保留未结束
    .map(c => ({
      id: 'luogu-' + c.id,
      oj: '洛谷',
      name: c.name,
      url: 'https://www.luogu.com.cn/contest/' + c.id,
      time: new Date(c.startTime * 1000 + 8 * 3600 * 1000).toISOString().slice(0, 16), // YYYY-MM-DDTHH:MM(UTC+8 北京时)
      oj_type: c.type || '',
      rated: !!c.rated,
      reg: false,
      problems: []
    }));

  const payload = new Response(JSON.stringify({ ok: true, source: 'luogu-worker', contests }), {
    headers: { ...cors(), 'Content-Type': 'application/json; charset=utf-8' }
  });
  // 克隆一份写入缓存（Response 只能读一次）
  const toCache = payload.clone();
  const c = new Response(await payload.text(), { headers: { ...cors(), 'Content-Type': 'application/json; charset=utf-8' } });
  c.headers.append('CF-Cache-Status', 'MISS');
  cache.put(cacheKey, toCache);
  return c;
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors() });
    }
    if (request.method !== 'GET') {
      return err('method not allowed', 405);
    }
    const cache = caches.default;
    try {
      const res = await fetchLuogu(cache);
      return res;
    } catch (e) {
      return err('luogu fetch failed: ' + (e && e.message ? e.message : e), 502);
    }
  }
};
