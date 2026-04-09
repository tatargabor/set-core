const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://setcode.dev',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// Rate limit: max 3 submissions per IP per hour
const RATE_LIMIT_WINDOW = 3600; // seconds
const RATE_LIMIT_MAX = 10;

async function sendNotification(entry, env) {
  const interestList = entry.interests.length > 0
    ? entry.interests.join(', ')
    : '(none selected)';

  const body = [
    `New contact from setcode.dev`,
    ``,
    `Email: ${entry.email}`,
    `Interests: ${interestList}`,
    `Message: ${entry.message || '(empty)'}`,
    `Time: ${entry.timestamp}`,
  ].join('\n');

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      },
      body: JSON.stringify({
        from: 'SET Contact <contact@setcode.dev>',
        to: [env.NOTIFY_EMAIL, 'tatar.gabor@gmail.com'],
        reply_to: entry.email,
        subject: `[setcode.dev] New contact: ${entry.email}`,
        text: body,
      }),
    });
    if (!res.ok) {
      console.error('Resend error:', res.status, await res.text());
    }
  } catch (e) {
    // Email is best-effort — don't fail the submission
    console.error('Email notification failed:', e);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Admin: list contacts (GET /list?key=<ADMIN_KEY>)
    if (url.pathname === '/list' && request.method === 'GET') {
      const key = url.searchParams.get('key');
      if (!key || key !== env.ADMIN_KEY) {
        return new Response('Unauthorized', { status: 401 });
      }

      const list = await env.CONTACTS.list({ prefix: 'contact_' });
      const entries = [];
      for (const k of list.keys) {
        const val = await env.CONTACTS.get(k.name);
        if (val) entries.push(JSON.parse(val));
      }

      return Response.json(entries);
    }

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405, headers: CORS_HEADERS });
    }

    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

    try {
      // Rate limiting via KV
      const rateKey = `rate_${ip}`;
      const rateData = await env.CONTACTS.get(rateKey);
      const count = rateData ? parseInt(rateData, 10) : 0;

      if (count >= RATE_LIMIT_MAX) {
        return Response.json(
          { error: 'Too many submissions. Try again later.' },
          { status: 429, headers: CORS_HEADERS }
        );
      }

      const body = await request.json();
      const { email, interests, message } = body;

      // Validation
      if (!email || !email.includes('@') || email.length > 320) {
        return Response.json({ error: 'Valid email required' }, { status: 400, headers: CORS_HEADERS });
      }

      if (message && message.length > 2000) {
        return Response.json({ error: 'Message too long' }, { status: 400, headers: CORS_HEADERS });
      }

      if (interests && (!Array.isArray(interests) || interests.length > 10)) {
        return Response.json({ error: 'Invalid interests' }, { status: 400, headers: CORS_HEADERS });
      }

      // Honeypot: reject if hidden field is filled (bots fill all fields)
      if (body.website) {
        return Response.json({ status: 'ok' }, { headers: CORS_HEADERS });
      }

      const entry = {
        email: email.trim().slice(0, 320),
        interests: (interests || []).slice(0, 10),
        message: (message || '').slice(0, 2000),
        timestamp: new Date().toISOString(),
      };

      // Store in KV
      const contactKey = `contact_${Date.now()}_${crypto.randomUUID().slice(0, 8)}`;
      await env.CONTACTS.put(contactKey, JSON.stringify(entry), { expirationTtl: 60 * 60 * 24 * 365 });

      // Bump rate limit counter
      await env.CONTACTS.put(rateKey, String(count + 1), { expirationTtl: RATE_LIMIT_WINDOW });

      // Send email notification (best-effort, non-blocking)
      await sendNotification(entry, env);

      return Response.json({ status: 'ok' }, { headers: CORS_HEADERS });
    } catch (err) {
      return Response.json({ error: 'Invalid request' }, { status: 400, headers: CORS_HEADERS });
    }
  },
};
