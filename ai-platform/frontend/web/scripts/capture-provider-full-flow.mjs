import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:5174';
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const OUTPUT_DIR = path.resolve('screenshots', 'provider-full-flow');

if (!fs.existsSync(EDGE_PATH)) {
  throw new Error(`Edge executable not found: ${EDGE_PATH}`);
}

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const seedSettings = {
  provider_id: 'prov_demo_123',
  name: 'Lina Berg',
  phone: '+46 70 111 22 33',
  city: 'Stockholm',
  bio: 'Freelance color specialist focused on natural blondes.',
  instagram_username: 'lina.berg.hair',
  home_service: true,
  location_salon: 'Hornsgatan 10, Stockholm',
  categories: ['hair'],
  amenities: ['wifi', 'coffee', 'card_payment'],
  services: [
    {
      service_id: 'svc_1',
      name: 'Haircut Short',
      category: 'hair',
      duration_minutes: 45,
      price_ex_vat: 650,
      home_service_available: false,
      is_active: true,
    },
    {
      service_id: 'svc_2',
      name: 'Haircut Medium',
      category: 'hair',
      duration_minutes: 60,
      price_ex_vat: 820,
      home_service_available: true,
      is_active: true,
    },
    {
      service_id: 'svc_3',
      name: 'Haircut Long',
      category: 'hair',
      duration_minutes: 75,
      price_ex_vat: 980,
      home_service_available: true,
      is_active: true,
    },
  ],
};

const settingsState = JSON.parse(JSON.stringify(seedSettings));
let serviceCounter = settingsState.services.length + 1;

function json(route, status, payload) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function wireApiMocks(context) {
  await context.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const pathname = url.pathname;

    if (pathname === '/api/v1/auth/provider/send-code' && method === 'POST') {
      return json(route, 200, { ok: true, dev_code: '123456' });
    }

    if (pathname === '/api/v1/auth/provider/verify-code' && method === 'POST') {
      return json(route, 200, {
        access_token: 'demo-provider-token',
        token_type: 'bearer',
        has_provider_profile: false,
      });
    }

    if (pathname === '/api/v1/onboarding/provider' && method === 'POST') {
      return json(route, 200, {
        provider_id: 'prov_demo_123',
        slug: 'lina-berg-hair',
      });
    }

    if (pathname === '/api/v1/availability/hours' && method === 'POST') {
      return json(route, 200, { ok: true });
    }

    if (pathname === '/api/v1/salon-links/request' && method === 'POST') {
      return json(route, 200, { ok: true });
    }

    if (pathname === '/api/v1/onboarding/scan-price-list' && method === 'POST') {
      return json(route, 200, {
        services_found: 2,
        services: [
          { name: 'Balayage Refresh', duration_minutes: 120, price_ex_vat: 1600 },
          { name: 'Bang Trim', duration_minutes: 20, price_ex_vat: 250 },
        ],
      });
    }

    if (pathname === '/api/v1/providers/me/settings' && method === 'GET') {
      return json(route, 200, settingsState);
    }

    if (pathname === '/api/v1/providers/me/settings' && method === 'PATCH') {
      const patch = request.postDataJSON() || {};
      Object.assign(settingsState, patch);
      return json(route, 200, settingsState);
    }

    if (pathname === '/api/v1/providers/me/amenities' && method === 'PUT') {
      const body = request.postDataJSON() || {};
      settingsState.amenities = Array.isArray(body.amenity_keys) ? body.amenity_keys : settingsState.amenities;
      return json(route, 200, { amenity_keys: settingsState.amenities });
    }

    if (pathname === '/api/v1/providers/me/services' && method === 'POST') {
      const body = request.postDataJSON() || {};
      const created = {
        service_id: `svc_${serviceCounter++}`,
        name: body.name || 'New Service',
        category: body.category || 'other',
        duration_minutes: Number(body.duration_minutes || 60),
        price_ex_vat: Number(body.price_ex_vat || 0),
        home_service_available: Boolean(body.home_service_available),
        is_active: true,
      };
      settingsState.services.push(created);
      return json(route, 200, created);
    }

    if (pathname.startsWith('/api/v1/providers/me/services/') && method === 'PATCH') {
      const serviceId = pathname.split('/').at(-1);
      const patch = request.postDataJSON() || {};
      const idx = settingsState.services.findIndex((s) => s.service_id === serviceId);
      if (idx >= 0) settingsState.services[idx] = { ...settingsState.services[idx], ...patch };
      return json(route, 200, settingsState.services[idx] || {});
    }

    if (pathname.startsWith('/api/v1/providers/me/services/') && method === 'DELETE') {
      const serviceId = pathname.split('/').at(-1);
      settingsState.services = settingsState.services.filter((s) => s.service_id !== serviceId);
      return route.fulfill({ status: 204, body: '' });
    }

    if (pathname === '/api/v1/home/dashboard' && method === 'GET') {
      return json(route, 200, {
        provider_name: settingsState.name,
        today_label: 'Sunday, 8 March',
        team: [],
        upcoming_bookings: [
          {
            booking_id: 'b_1',
            customer_name: 'Maja Nilsson',
            service_name: 'Haircut Medium',
            scheduled_start: '2026-03-09T09:00:00+01:00',
            scheduled_end: '2026-03-09T10:00:00+01:00',
            customer_notes: 'Please keep length.',
            visit_count: 2,
            is_home_visit: false,
            session_preferences: ['quiet_session'],
          },
        ],
        booking_updates: [],
        requests: [],
        pending_requests_count: 0,
        booking_link: 'https://fixmeapp.com/b/lina-berg-hair',
        waitlist_count: 1,
      });
    }

    if (pathname === '/api/v1/providers/by-slug/lina-berg-hair/profile' && method === 'GET') {
      return json(route, 200, {
        provider_id: settingsState.provider_id,
        slug: 'lina-berg-hair',
        name: settingsState.name,
        city: settingsState.city,
        location_salon: settingsState.location_salon,
        instagram_username: settingsState.instagram_username,
        bio: settingsState.bio,
        amenities: settingsState.amenities,
        services: settingsState.services,
        trust: { rating: 4.9, review_count: 87 },
      });
    }

    return json(route, 200, {});
  });
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: EDGE_PATH,
    args: ['--disable-web-security'],
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: 'en-US',
  });

  await wireApiMocks(context);
  const page = await context.newPage();

  async function snap(name) {
    const fullPath = path.join(OUTPUT_DIR, name);
    await page.screenshot({ path: fullPath, fullPage: true });
    console.log(`Saved ${fullPath}`);
  }

  await page.goto(`${BASE_URL}/provider/onboarding`, { waitUntil: 'networkidle' });
  await page.locator('h1', { hasText: "What's your email?" }).waitFor();
  await snap('01-onboarding-email.png');

  await page.getByPlaceholder('you@email.com').fill('lina@example.com');
  await page.getByRole('button', { name: /Send code/i }).click();
  await page.locator('h1', { hasText: 'Check your email' }).waitFor();
  await snap('02-onboarding-verify.png');

  await page.getByPlaceholder('123456').fill('123456');
  await page.getByRole('button', { name: /Verify code/i }).click();
  await page.locator('h2', { hasText: 'What do you offer?' }).waitFor();
  await page.locator('text=1/6').waitFor();
  await snap('03-onboarding-categories.png');

  await page.getByRole('button', { name: /Hair/i }).first().click();
  await page.getByRole('button', { name: /Continue/i }).click();
  await page.locator('h2', { hasText: 'Your profile' }).waitFor();
  await page.getByPlaceholder('Sofia Lindqvist').fill('Lina Berg');
  await page.getByPlaceholder('Stockholm').fill('Stockholm');
  await page.getByPlaceholder('Salon address (e.g. Storgatan 12, Stockholm)').fill('Hornsgatan 10, Stockholm');
  await snap('04-onboarding-profile.png');

  await page.getByRole('button', { name: /Continue/i }).click();
  await page.locator('h2', { hasText: 'Working hours' }).waitFor();
  await snap('05-onboarding-hours.png');

  await page.getByRole('button', { name: /Continue/i }).click();
  await page.locator('h2', { hasText: 'What do you offer?' }).waitFor();
  await page.locator('text=makes your space special').waitFor();
  await page.getByRole('button', { name: /Free Wi-Fi/i }).click();
  await snap('06-onboarding-amenities.png');

  await page.getByRole('button', { name: /Continue/i }).click();
  await page.locator('h2', { hasText: 'Scan your price list' }).waitFor();
  await snap('07-onboarding-scan.png');

  await page.getByRole('button', { name: /Skip for now/i }).click();
  await page.locator('h2', { hasText: 'Almost done!' }).waitFor();
  await snap('08-onboarding-complete.png');

  await page.getByRole('button', { name: /Go to Provider Home/i }).click();
  await page.waitForURL('**/provider/home');
  await page.locator('text=Upcoming').first().waitFor();
  await snap('09-provider-home.png');

  await page.goto(`${BASE_URL}/provider/settings`, { waitUntil: 'networkidle' });
  await page.locator('text=Settings').first().waitFor();
  await page.waitForTimeout(400);
  await snap('10-provider-settings-profile.png');

  await page.getByRole('button', { name: /Services/i }).click();
  await page.locator('text=Upload screenshot').waitFor();
  await snap('11-provider-settings-services.png');

  await page.getByRole('button', { name: /Amenities/i }).click();
  await page.locator('text=Dogs welcome').waitFor();
  await snap('12-provider-settings-amenities.png');

  await page.goto(`${BASE_URL}/provider/profile`, { waitUntil: 'networkidle' });
  await page.locator('text=Your Profile').waitFor();
  await snap('13-provider-profile.png');

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
