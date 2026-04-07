/**
 * Fixmeapp Web Booking API client.
 */

const API_BASE = '/api/v1';

const ADMIN_ACTOR_SESSION_KEY = "fixme_admin_actor";
const ENV_ADMIN_ACTOR = import.meta.env.VITE_ADMIN_ACTOR || "johanna@fixmeapp.ai";

function getAdminHeaders(adminToken) {
  const adminActor = (sessionStorage.getItem(ADMIN_ACTOR_SESSION_KEY) || ENV_ADMIN_ACTOR || '').trim();
  const headers = { 'X-Admin-Token': adminToken };
  if (adminActor) headers['X-Admin-Actor'] = adminActor;
  return headers;
}
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = payload?.detail || payload?.message || '';
    } catch {
      const text = await response.text().catch(() => '');
      detail = (text || '').trim();
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) return null;

  return response.json();
}
// Provider
export async function getProvider(providerId) {
  return request(`/providers/${providerId}`);
}

export async function getProviderTrustSignals(providerId) {
  return request(`/provider/${providerId}/trust-signals`);
}

export async function getProviderBySlug(slug) {
  return request(`/providers/by-slug/${slug}`);
}

export async function getProviderProfile(slug) {
  return request(`/providers/by-slug/${slug}/profile`);
}

export async function getProviderProfileById(providerId) {
  return request(`/providers/${providerId}/profile`);
}

// Services
export async function getServices(providerId) {
  return request(`/services?provider_id=${providerId}`);
}

// Availability
export async function getAvailableSlots(providerId, date, durationMinutes = 30, slotInterval = 15) {
  return request(
    `/availability/slots?provider_id=${providerId}&date=${date}&duration_minutes=${durationMinutes}&slot_interval=${slotInterval}`
  );
}

// Booking
export async function createBooking(bookingData) {
  return request('/booking/create', {
    method: 'POST',
    body: JSON.stringify(bookingData),
  });
}

// Dashboard
export async function getHomeDashboard(token) {
  return request('/home/dashboard', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updateBookingStatus(bookingId, status, token) {
  return request(`/bookings/${bookingId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ status }),
  });
}

export async function rescheduleBooking(bookingId, newStart, newEnd, token) {
  return request(
    `/bookings/${bookingId}/reschedule?new_start=${encodeURIComponent(newStart)}&new_end=${encodeURIComponent(newEnd)}`,
    { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
  );
}

// Customer
export async function createCustomer(customerData) {
  return request('/customer/create', {
    method: 'POST',
    body: JSON.stringify(customerData),
  });
}

export async function getCustomerDashboard(token) {
  return request('/customer/me/dashboard', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Customer auth
export async function sendCustomerOtp(email) {
  return request('/auth/customer/send-code', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function verifyCustomerOtp(email, code) {
  return request('/auth/customer/verify-code', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  });
}

// Provider auth session
export async function getProviderSession(token) {
  return request('/auth/provider/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Customer profile (privacy settings etc.)
export async function updateCustomerProfile(token, fields) {
  return request('/customer/me/profile', {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(fields),
  });
}

// Customer preferences
export async function updateCustomerPreferences(token, serviceInterests, lifestylePreferences) {
  return request('/customer/me/preferences', {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      service_interests: serviceInterests,
      lifestyle_preferences: lifestylePreferences,
    }),
  });
}

export async function getCustomerPreferences(token) {
  return request('/customer/me/preferences', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ------ GDPR / Data rights ------------------------------------------------------------------------------------------------------------------------------------------------------------------
/** Submit a data rights request. type = "export" | "deletion" */
export async function submitGdprRequest(token, requestType, notes = null) {
  return request('/customer/me/gdpr/request', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ request_type: requestType, notes }),
  });
}

/** List all GDPR requests submitted by the current customer. */
export async function getMyGdprRequests(token) {
  return request('/customer/me/gdpr/requests', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function cancelCustomerBooking(token, bookingId) {
  return request(`/customer/me/bookings/${bookingId}/cancel`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function sendLateNotification(token, bookingId, minutes) {
  return request(`/customer/me/bookings/${bookingId}/running-late`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ minutes }),
  });
}

export async function sendProviderLateAlert(token, bookingId, minutes) {
  return request(`/bookings/${bookingId}/provider-running-late`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ minutes }),
  });
}

export async function uploadCustomerAvatar(token, file) {
  const form = new FormData();
  form.append('file', file);
  const response = await fetch(`${API_BASE}/customer/me/avatar`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    // No Content-Type; browser sets multipart boundary
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return response.json();
}

/**
 * Personalised discovery feed --- POST /api/v1/feed/search
 *
 * Passes the logged-in customer's user_id (fixme_user_id) so the backend
 * can boost providers that match their saved service_interests and
 * lifestyle_preferences from onboarding.
 */
export async function searchFeed(prompt, { customerId = null } = {}) {
  const customerUserId = localStorage.getItem('fixme_user_id') || null;
  return request('/feed/search', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      customer_id: customerId,
      customer_user_id: customerUserId,
    }),
  });
}

/**
 * Prompt-first discovery feed (typed UI blocks) — POST /api/v1/feed/prompt
 */
export async function getPromptFeed(prompt, { customerId = null, sessionId = null } = {}) {
  const customerUserId = localStorage.getItem('fixme_user_id') || null;
  return request('/feed/prompt', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      customer_id: customerId,
      customer_user_id: customerUserId,
      session_id: sessionId,
    }),
  });
}

// Demo AI chat
export async function searchProviders({ location = '', serviceCategory = '' } = {}) {
  const params = new URLSearchParams();
  if (location) params.set('location', location);
  if (serviceCategory) params.set('service_category', serviceCategory);
  const qs = params.toString();
  return request(`/providers/search${qs ? `?${qs}` : ''}`);
}

export async function sendProviderChatMessage({ providerId, threadId, message, senderId = null, customerId = null }) {
  return request('/chat/provider/message', {
    method: 'POST',
    body: JSON.stringify({
      provider_id: providerId,
      thread_id: threadId,
      message,
      sender_id: senderId,
      customer_id: customerId,
    }),
  });
}

export async function sendPlatformChatMessage({ threadId, message, senderId = null }) {
  return request('/chat/platform/message', {
    method: 'POST',
    body: JSON.stringify({
      thread_id: threadId,
      message,
      sender_id: senderId,
    }),
  });
}

export async function sendTestChatMessage({ providerId, userId, message }) {
  return request('/test/chat', {
    method: 'POST',
    body: JSON.stringify({
      provider_id: providerId,
      user_id: userId,
      message,
    }),
  });
}

// Finance
export async function getFinanceInsights(period = 'this_month', token) {
  return request(`/provider/insights?period=${period}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getFinanceRecent(token, limit = 15) {
  return request(`/provider/finance/recent?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getFinanceSummary(token, startDate, endDate) {
  return request(`/provider/finance/summary?start_date=${startDate}&end_date=${endDate}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function markBookingPaid(token, bookingId) {
  return request(`/provider/finance/bookings/${bookingId}/mark-paid`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Waitlist
export async function joinWaitlist({ providerId, email, name, serviceId = null, preferredDays = null, earliestHour = 8, latestHour = 18 }) {
  return request('/waitlist/join', {
    method: 'POST',
    body: JSON.stringify({
      provider_id: providerId,
      email,
      name,
      service_id: serviceId,
      preferred_days: preferredDays,
      earliest_hour: earliestHour,
      latest_hour: latestHour,
    }),
  });
}


export async function getDemoProviderLock() {
  return request('/demo/provider-lock');
}

// Provider follow (customer JWT required)
export async function followProvider(token, providerId) {
  return request(`/providers/${providerId}/follow`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function unfollowProvider(token, providerId) {
  return request(`/providers/${providerId}/follow`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getFollowStatus(token, providerId) {
  return request(`/providers/${providerId}/follow/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getFollowerCount(providerId) {
  return request(`/providers/${providerId}/followers/count`);
}

// Admin (internal ops)

export async function getAdminMe(adminToken) {
  return request('/admin/me', {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminVerifications(adminToken, status = 'pending') {
  return request(`/admin/verifications?status=${status}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function approveVerification(adminToken, verificationId) {
  return request(`/admin/verifications/${verificationId}/approve`, {
    method: 'POST',
    headers: getAdminHeaders(adminToken),
  });
}

export async function rejectVerification(adminToken, verificationId, reason = '') {
  return request(`/admin/verifications/${verificationId}/reject`, {
    method: 'POST',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify({ reason: reason || null }),
  });
}

export async function getAdminVerificationStats(adminToken) {
  return request('/admin/verifications/stats', {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminGdprRequests(adminToken, { status, requestType } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (requestType) params.set('request_type', requestType);
  const qs = params.toString() ? `?${params}` : '';
  return request(`/admin/gdpr-requests${qs}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function updateAdminGdprRequest(adminToken, requestId, { status, adminNotes }) {
  return request(`/admin/gdpr-requests/${requestId}`, {
    method: 'PATCH',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify({ status, admin_notes: adminNotes || null }),
  });
}

export async function getAdminGdprStats(adminToken) {
  return request('/admin/gdpr-requests/stats', {
    headers: getAdminHeaders(adminToken),
  });
}

// Provider calendar sync
export async function getProviderCalendarConnections(token) {
  return request('/provider/calendar/connections', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getProviderCalendarConnectUrl(token, connector) {
  return request(`/provider/calendar/${connector}/connect-url`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function upsertProviderCalendarConnection(token, connector, payload) {
  return request(`/provider/calendar/${connector}/callback`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export async function disconnectProviderCalendarConnection(token, connectionId) {
  return request(`/provider/calendar/connections/${connectionId}/disconnect`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function syncProviderCalendarConnectionNow(token, connectionId) {
  return request(`/provider/calendar/connections/${connectionId}/sync-now`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getProviderIcsLink(token) {
  return request('/provider/calendar/ics/link', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function rotateProviderIcsToken(token) {
  return request('/provider/calendar/ics/rotate-token', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}



// Provider intraday time blocks (lunch/private)
export async function getProviderTimeBlocks(token, fromAt, toAt) {
  const params = new URLSearchParams();
  if (fromAt) params.set('from_at', fromAt);
  if (toAt) params.set('to_at', toAt);
  const qs = params.toString();
  return request(`/provider/calendar/blocks${qs ? `?${qs}` : ''}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function createProviderTimeBlock(token, payload) {
  return request('/provider/calendar/blocks', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export async function deleteProviderTimeBlock(token, blockId) {
  return request(`/provider/calendar/blocks/${blockId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Provider Inbox (Instagram DM management)
export async function getInboxConversations(token) {
  return request('/inbox/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getInboxConversation(token, conversationId) {
  return request(`/inbox/conversations/${conversationId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function flagConversationNeedsHuman(token, conversationId) {
  return request(`/inbox/conversations/${conversationId}/flag-human`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function providerReplyToConversation(token, conversationId, text) {
  return request(`/inbox/conversations/${conversationId}/provider-reply`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ text }),
  });
}

export async function resumeBotForConversation(token, conversationId) {
  return request(`/inbox/conversations/${conversationId}/resume-bot`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}


export async function submitProviderIncidentReport(token, bookingId, payload) {
  return request(`/customer/me/bookings/${bookingId}/report`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}
export async function submitCustomerReliabilityReport(token, customerId, payload) {
  return request(`/customer/${customerId}/reliability-report`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export async function getCustomerReliabilityScore(token, customerId) {
  return request(`/customer/${customerId}/reliability-score`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updateCustomerFavorites(token, providerIds) {
  return request('/customer/me/favorites', {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ provider_ids: providerIds }),
  });
}

export async function getAdminSearch(adminToken, q, limit = 20) {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return request(`/admin/search?${params.toString()}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminUser(adminToken, userId) {
  return request(`/admin/users/${userId}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function patchAdminUser(adminToken, userId, payload) {
  return request(`/admin/users/${userId}`, {
    method: 'PATCH',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}

export async function getAdminProvider(adminToken, providerId) {
  return request(`/admin/providers/${providerId}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function patchAdminProvider(adminToken, providerId, payload) {
  return request(`/admin/providers/${providerId}`, {
    method: 'PATCH',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}

export async function getAdminBookings(adminToken, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') params.set(k, String(v));
  });
  const qs = params.toString();
  return request(`/admin/bookings${qs ? `?${qs}` : ''}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function patchAdminBooking(adminToken, bookingId, payload) {
  return request(`/admin/bookings/${bookingId}`, {
    method: 'PATCH',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}

export async function createAdminManualAccount(adminToken, payload) {
  return request('/admin/accounts/manual', {
    method: 'POST',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}

export async function createAdminManualBooking(adminToken, payload) {
  return request('/admin/bookings/manual', {
    method: 'POST',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}

export async function getAdminLevelInspector(adminToken, actorType, actorId) {
  return request(`/admin/level/${actorType}/${actorId}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminAuditLogs(adminToken, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') params.set(k, String(v));
  });
  const qs = params.toString();
  return request(`/admin/audit-logs${qs ? `?${qs}` : ''}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminReports(adminToken, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') params.set(k, String(v));
  });
  const qs = params.toString();
  return request(`/admin/reports${qs ? `?${qs}` : ''}`, {
    headers: getAdminHeaders(adminToken),
  });
}

export async function getAdminReportStats(adminToken) {
  return request('/admin/reports/stats', {
    headers: getAdminHeaders(adminToken),
  });
}

export async function patchAdminReport(adminToken, reportScope, reportId, payload) {
  return request(`/admin/reports/${reportScope}/${reportId}`, {
    method: 'PATCH',
    headers: getAdminHeaders(adminToken),
    body: JSON.stringify(payload),
  });
}




