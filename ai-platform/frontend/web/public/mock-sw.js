// Preview-only mock service worker — intercepts customer API calls
const MOCK_DASHBOARD = {
  upcoming_bookings: [
    {
      booking_id: 'b1',
      provider_id: 'p1',
      provider_slug: 'luna-beauty',
      provider_name: 'Luna Beauty Studio',
      provider_image_url: null,
      service_name: 'Full Set Acrylics',
      start_time: new Date(Date.now() + 86400000).toISOString(),
      end_time: new Date(Date.now() + 86400000 + 3600000).toISOString(),
      location_type: 'salon',
      status: 'confirmed',
      booking_number: 42,
    },
  ],
  past_bookings: [
    {
      booking_id: 'b2',
      provider_id: 'p1',
      provider_slug: 'luna-beauty',
      provider_name: 'Luna Beauty Studio',
      provider_image_url: null,
      service_name: 'Gel Manicure',
      start_time: new Date(Date.now() - 7 * 86400000).toISOString(),
      end_time: new Date(Date.now() - 7 * 86400000 + 3600000).toISOString(),
      location_type: 'salon',
      status: 'completed',
      booking_number: 38,
    },
  ],
  followed_providers: [],
};

const MOCK_PREFS = { service_interests: ['nails'], lifestyle_preferences: [] };

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.includes('/customer/dashboard')) {
    event.respondWith(Response.json(MOCK_DASHBOARD));
  } else if (url.pathname.includes('/customer/preferences')) {
    event.respondWith(Response.json(MOCK_PREFS));
  }
});
