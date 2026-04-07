/**
 * Fixmeapp Provider - Mobile API client.
 * Mirrors the endpoint paths from the web app's bookingApi.js exactly.
 */
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';

const API_BASE =
  (Constants.expoConfig?.extra?.apiUrl as string | undefined) ||
  process.env.EXPO_PUBLIC_API_URL ||
  'http://localhost:8000';

console.log('[API] BASE URL:', API_BASE);

async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync('fixme_provider_token');
}

async function request<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}/api/v1${endpoint}`;
  console.log('[API] →', options.method ?? 'GET', url);
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
  console.log('[API] ←', res.status, url);

  if (!res.ok) {
    let detail = '';
    try {
      const payload = await res.json();
      detail = payload?.detail || payload?.message || '';
      console.log('[API] ERROR body:', JSON.stringify(payload));
    } catch {
      detail = await res.text().catch(() => '');
      console.log('[API] ERROR text:', detail);
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

async function authRequest<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
  tokenOverride?: string,
): Promise<T> {
  const token = tokenOverride ?? (await getToken());
  return request<T>(endpoint, {
    ...options,
    headers: {
      ...(options.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

// Auth

export interface SendCodeResult {
  message: string;
  dev_code?: string | null;
}

export interface VerifyCodeResult {
  access_token: string;
  token_type: string;
  user_id: string;
  is_new_user: boolean;
  has_provider_profile: boolean;
  provider_id?: string | null;
  slug?: string | null;
}

export interface ProviderMeResult {
  user_id: string;
  email: string;
  has_provider_profile: boolean;
  provider_id?: string | null;
  provider_name?: string | null;
  slug?: string | null;
}

export interface ProviderPublicService {
  service_id: string;
  name: string;
  category?: string | null;
  description?: string | null;
  duration_minutes: number;
  price_ex_vat: number;
  home_service_available: boolean;
}

export interface ProviderPublicWorkingHour {
  open: boolean;
  start?: string | null;
  end?: string | null;
}

export interface ProviderPublicProfile {
  provider_id: string;
  name: string;
  city?: string | null;
  bio?: string | null;
  image_url?: string | null;
  ig_profile_picture_url?: string | null;
  instagram_username?: string | null;
  slug?: string | null;
  business_type?: string | null;
  price_level?: number | null;
  home_service?: boolean;
  location_salon?: string | null;
  categories?: string[];
  trust?: {
    rating?: number;
    review_count?: number;
    revisit_rate?: number;
    total_completed_bookings?: number;
  };
  services?: ProviderPublicService[];
  amenities?: string[];
  working_hours?: Record<string, ProviderPublicWorkingHour>;
  booking_policy?: string | null;
  cancellation_policy?: string | null;
  booking_url?: string | null;
  fixmeapp_followers_count?: number;
  ig_followers_count?: number | null;
  ig_following_count?: number | null;
  is_verified?: boolean;
  loyalty_tier?: string;
  level_badge?: string;
}

export async function sendProviderCode(email: string): Promise<SendCodeResult> {
  return request('/auth/provider/send-code', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function verifyProviderCode(email: string, code: string): Promise<VerifyCodeResult> {
  return request('/auth/provider/verify-code', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  });
}

export async function getProviderSession(tokenOverride?: string): Promise<ProviderMeResult> {
  return authRequest('/auth/provider/me', {}, tokenOverride);
}

export async function getProviderProfileBySlug(slug: string): Promise<ProviderPublicProfile> {
  return request(`/providers/by-slug/${slug}/profile`);
}

export async function getProviderProfileById(providerId: string): Promise<ProviderPublicProfile> {
  return request(`/providers/${providerId}/profile`);
}

export interface InstagramConnectStartResult {
  auth_url: string;
  state: string;
  expires_in_seconds: number;
}

export interface InstagramConnectStatus {
  connected: boolean;
  instagram_user_id?: string | null;
  instagram_username?: string | null;
  profile_picture_url?: string | null;
  followers_count?: number | null;
  following_count?: number | null;
}

export async function startInstagramConnect(
  returnTo: string,
  tokenOverride?: string,
): Promise<InstagramConnectStartResult> {
  return authRequest('/instagram/connect/start', {
    method: 'POST',
    body: JSON.stringify({ return_to: returnTo }),
  }, tokenOverride);
}

export async function getInstagramConnectStatus(
  tokenOverride?: string,
): Promise<InstagramConnectStatus> {
  return authRequest('/instagram/connect/status', {}, tokenOverride);
}

export async function disconnectInstagramConnect(tokenOverride?: string): Promise<void> {
  return authRequest('/instagram/connect/disconnect', { method: 'POST' }, tokenOverride);
}

// Provider profile

export interface ProviderProfile {
  provider_id:        string;
  name:               string;
  slug?:              string;
  email?:             string;
  phone?:             string;
  bio?:               string;
  instagram_username?: string;  // matches backend ProviderSettingsOut
  location_salon?:    string;
  home_service?:      boolean;
  city?:              string;
  image_url?:         string;
  business_type?:     string;
  amenities?:         string[];
}

export async function getMyProviderProfile(): Promise<ProviderProfile> {
  return authRequest('/providers/me/settings');
}

export async function updateProviderProfile(fields: Partial<ProviderProfile>): Promise<ProviderProfile> {
  return authRequest('/providers/me/settings', { method: 'PATCH', body: JSON.stringify(fields) });
}

// Onboarding

export interface ScannedService {
  name: string;
  duration_minutes?: number | null;
  price_ex_vat?: number | null;
  category?: string | null;
}

export interface ScanData {
  name?: string | null;
  city?: string | null;
  address?: string | null;
  bio?: string | null;
  amenity_keys?: string[];
  services?: ScannedService[];
  working_hours?: Record<string, {
    open: boolean;
    start?: string | null;
    end?: string | null;
  }>;
  booking_policy?: string | null;
  cancellation_policy?: string | null;
}

export interface ScannedServiceFromPhoto {
  name: string;
  duration_minutes: number;
  price_ex_vat: number;
  category?: string | null;
}

export async function scanPriceListPhoto(
  uri: string,
  mimeType: string,
): Promise<{ services: ScannedServiceFromPhoto[]; services_found: number; note?: string }> {
  const token = await getToken();
  const form = new FormData();
  form.append('file', { uri, type: mimeType, name: 'pricelist.jpg' } as any);
  form.append('categories', '[]');
  const res = await fetch(`${API_BASE}/api/v1/onboarding/scan-price-list`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as any)?.detail || `Scan failed: ${res.status}`);
  }
  return res.json();
}

// ─── Booking ──────────────────────────────────────────────────────────────────

export interface TimeSlot {
  start: string;
  end: string;
}

export interface BookingResult {
  booking_id: string;
  booking_number?: string;
  status: string;
}

export async function getAvailableSlots(
  providerId: string,
  date: string,
  durationMinutes: number,
): Promise<TimeSlot[]> {
  return authRequest(
    `/availability/slots?provider_id=${providerId}&date=${date}&duration_minutes=${durationMinutes}&slot_interval=15`,
  );
}

export async function createGuestBooking(data: {
  provider_id: string;
  service_name: string;
  price_ex_vat: number;
  scheduled_start: string;   // ISO datetime e.g. "2025-03-27T10:00:00"
  scheduled_end: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  notes?: string;
}): Promise<BookingResult> {
  // Build notes string that includes phone (backend has no phone field)
  const notesStr = [
    data.customer_phone ? `Phone: ${data.customer_phone}` : '',
    data.notes || '',
  ].filter(Boolean).join('\n') || undefined;

  const payload = {
    provider_id: data.provider_id,
    scheduled_start: data.scheduled_start,
    scheduled_end: data.scheduled_end,
    walkin_customer_name: data.customer_name,
    walkin_customer_email: data.customer_email,
    customer_notes: notesStr,
    is_walkin: true,
    line_items: [{
      service_type: data.service_name,
      quantity: 1,
      unit_price_ex_vat: data.price_ex_vat,
    }],
  };

  const res = await fetch(`${API_BASE}/api/v1/booking/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any)?.detail || `Booking failed: ${res.status}`);
  }
  return res.json();
}

export async function scanWebsite(url: string, tokenOverride?: string): Promise<ScanData> {
  try {
    return await authRequest<ScanData>('/setup/scan-website', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }, tokenOverride);
  } catch {
    return authRequest<ScanData>('/setup/import-url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }, tokenOverride);
  }
}

export interface ScanApplyPayload {
  working_hours?: Record<string, {
    open: boolean;
    start?: string | null;
    end?: string | null;
  }>;
}

export async function applyScanToProviderProfile(
  payload: ScanApplyPayload,
  tokenOverride?: string,
): Promise<void> {
  return authRequest('/setup/import-apply', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, tokenOverride);
}

export interface OnboardingProviderPayload {
  name: string;
  city?: string | null;
  instagram_username?: string | null;
  service_categories?: string[];
  bio?: string | null;
  home_service?: boolean;
  amenity_keys?: string[];
  scanned_services?: ScannedService[];
  booking_policy?: string | null;
  cancellation_policy?: string | null;
  ig_user_id?: string | null;
  ig_access_token?: string | null;
}

export interface OnboardingProviderResult {
  provider_id: string;
  name: string;
  slug?: string | null;
  message: string;
}

export async function createOnboardingProvider(
  payload: OnboardingProviderPayload,
  tokenOverride?: string,
): Promise<OnboardingProviderResult> {
  return authRequest('/onboarding/provider', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, tokenOverride);
}

// Home dashboard

export interface BookingItem {
  booking_id: string;
  booking_number: number;
  status: string;
  scheduled_start: string;
  scheduled_end: string;
  service_name?: string;
  customer_name?: string;
  customer_id?: string;
  customer_email?: string;
  customer_notes?: string;
  customer_image_url?: string | null;
  is_home_visit?: boolean;
  session_preferences?: string[];
  late_alert_minutes?: number | null;
  late_alert_sent_at?: string | null;
  total_amount_inc_vat?: number;
  visit_count?: number;
  reliability_score?: number;
}

export interface TeamMember {
  id: string;
  display_name: string;
  role?: string | null;
  image_url?: string | null;
  member_type: 'worker' | 'freelancer' | 'chair_renter' | string;
  rating: number;
  is_working_today: boolean;
}

export interface HomeBookingUpdate {
  booking_id: string;
  booking_number: number;
  customer_name: string;
  customer_image_url?: string | null;
  customer_rating?: number;
  service_name: string;
  original_start: string;
  original_end?: string;
  requested_start: string;
  requested_end: string;
  is_home_visit?: boolean;
}

export interface HomeRequestItem {
  request_id: string;
  request_type: 'booking' | 'worker' | string;
  person_name: string;
  person_image_url?: string | null;
  service_name?: string | null;
  scheduled_start?: string | null;
  is_home_visit?: boolean | null;
  customer_note?: string | null;
  session_preferences?: string[];
  worker_role?: string | null;
  worker_message?: string | null;
  worker_city?: string | null;
  business_type?: string | null;
}

export interface HomeDashboard {
  provider_id?: string;
  provider_name?: string;
  today_label?: string;

  // Current dashboard payload
  team?: TeamMember[];
  upcoming_bookings?: BookingItem[];
  booking_updates?: HomeBookingUpdate[];
  requests?: HomeRequestItem[];
  pending_requests_count?: number;
  booking_link?: string | null;
  referred_bookings_count?: number;
  referral_completed_bookings_count?: number;
  referral_credit_rate_sek?: number;
  referral_earned_total_sek?: number;
  referral_earned_this_month_sek?: number;
  referral_pending_payout_sek?: number;
  referral_paid_total_sek?: number;
  referral_balance_sek?: number;
  referral_last_payout_at?: string | null;
  waitlist_count?: number;
  trust_score?: number;
  trust_tier?: string;
  trust_confidence?: number;
  trust_breakdown?: Record<string, number>;

  // Legacy compatibility fields
  bookings_today?: BookingItem[];
  bookings_upcoming?: BookingItem[];
  revenue_today?: number;
  revenue_this_week?: number;
  currency?: string;
  next_booking?: BookingItem | null;
}

export async function getHomeDashboard(): Promise<HomeDashboard> {
  return authRequest('/home/dashboard');
}

// Bookings

export async function updateBookingStatus(bookingId: string, status: string): Promise<BookingItem> {
  return authRequest(`/bookings/${bookingId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export async function rescheduleBooking(
  bookingId: string,
  newStart: string,
  newEnd: string,
): Promise<BookingItem> {
  const params = new URLSearchParams({ new_start: newStart, new_end: newEnd });
  return authRequest(`/bookings/${bookingId}/reschedule?${params.toString()}`, { method: 'POST' });
}

export async function sendProviderLateAlert(bookingId: string, minutes: number): Promise<void> {
  return authRequest(`/bookings/${bookingId}/provider-running-late`, {
    method: 'POST',
    body: JSON.stringify({ minutes }),
  });
}

export async function submitCustomerReliabilityReport(
  customerId: string,
  payload: { category: string; details?: string },
): Promise<void> {
  return authRequest(`/customer/${customerId}/reliability-report`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// Services

export interface Service {
  service_id:          string;
  name:                string;
  category?:           string;
  duration_minutes:    number;
  price_ex_vat:        number;
  home_service_available: boolean;
  is_active:           boolean;
}

export async function getProviderServices(): Promise<Service[]> {
  return authRequest('/provider/services');
}

export async function createService(payload: Omit<Service, 'service_id'>): Promise<Service> {
  return authRequest('/provider/services', { method: 'POST', body: JSON.stringify(payload) });
}

export async function updateService(serviceId: string, payload: Partial<Service>): Promise<Service> {
  return authRequest(`/provider/services/${serviceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteService(serviceId: string): Promise<void> {
  return authRequest(`/provider/services/${serviceId}`, { method: 'DELETE' });
}

// Availability / Time blocks

export interface TimeBlock {
  block_id:  string;
  label:     string;
  starts_at: string;
  ends_at:   string;
}

export async function getProviderTimeBlocks(fromAt?: string, toAt?: string): Promise<TimeBlock[]> {
  const params = new URLSearchParams();
  if (fromAt) params.set('from_at', fromAt);
  if (toAt) params.set('to_at', toAt);
  const qs = params.toString();
  return authRequest(`/provider/calendar/blocks${qs ? `?${qs}` : ''}`);
}

export async function createProviderTimeBlock(payload: {
  label: string; starts_at: string; ends_at: string;
}): Promise<TimeBlock> {
  return authRequest('/provider/calendar/blocks', { method: 'POST', body: JSON.stringify(payload) });
}

export async function deleteProviderTimeBlock(blockId: string): Promise<void> {
  return authRequest(`/provider/calendar/blocks/${blockId}`, { method: 'DELETE' });
}

// Inbox

export interface Conversation {
  conversation_id: string;
  customer_name?:  string;
  last_message?:   string;
  last_message_at?: string;
  unread_count?:   number;
  needs_human?:    boolean;
}

export async function getInboxConversations(): Promise<Conversation[]> {
  return authRequest('/inbox/conversations');
}

// Calendar

export interface CalendarConnection {
  connection_id:     string;
  connector:         string;
  display_name?:     string;
  sync_enabled:      boolean;
  external_calendar_id?: string;
}

export async function getProviderCalendarConnections(): Promise<CalendarConnection[]> {
  return authRequest('/provider/calendar/connections');
}

export async function getCalendarConnectUrl(connector: string): Promise<{ auth_url: string; state: string }> {
  return authRequest(`/provider/calendar/${connector}/connect-url`, { method: 'POST' });
}

export async function disconnectCalendar(connectionId: string): Promise<void> {
  return authRequest(`/provider/calendar/connections/${connectionId}/disconnect`, { method: 'POST' });
}

export async function exchangeCalendarCode(
  connector: string,
  code: string,
  state: string,
): Promise<{ ok: boolean }> {
  return authRequest(`/provider/calendar/${connector}/callback`, {
    method: 'POST',
    body: JSON.stringify({ code, state }),
  });
}

// Bot settings

export interface BotSettings {
  bot_enabled:        boolean;
  tone?:              string;
  language?:          string;
  after_hours_mode?:  string;
}

export async function getBotSettings(): Promise<BotSettings> {
  return authRequest('/provider/bot-settings');
}

export async function updateBotSettings(payload: Partial<BotSettings>): Promise<BotSettings> {
  return authRequest('/provider/bot-settings', { method: 'PATCH', body: JSON.stringify(payload) });
}

// Amenities

export async function getProviderAmenities(): Promise<string[]> {
  return authRequest('/provider/amenities');
}

export async function updateProviderAmenities(keys: string[]): Promise<void> {
  return authRequest('/provider/amenities', { method: 'PUT', body: JSON.stringify({ amenity_keys: keys }) });
}

// Push token

export async function registerPushToken(pushToken: string): Promise<void> {
  return authRequest('/provider/push-token', {
    method: 'POST',
    body: JSON.stringify({ push_token: pushToken }),
  });
}

export async function unregisterPushToken(): Promise<void> {
  return authRequest('/provider/push-token', { method: 'DELETE' });
}

// Finance

export interface FinanceInsights {
  period:               string;
  total_bookings:       number;
  completed:            number;
  cancelled:            number;
  revenue_this_period:  number;
  revenue_prev_period:  number;
  top_services?:        Array<{ name: string; count: number }>;
}

export interface RecentBookingItem {
  booking_id:      string;
  booking_number:  number;
  status:          string;
  scheduled_start: string;
  service_name:    string | null;
  customer_name:   string | null;
  amount_inc_vat:  number;
  payment_status:  string;   // "paid" | "draft" | "sent" | "no_invoice"
  invoice_id:      string | null;
}

export interface FinanceSummary {
  start_date:          string;
  end_date:            string;
  total_bookings:      number;
  completed_bookings:  number;
  revenue_ex_vat:      number;
  vat_collected:       number;
  revenue_inc_vat:     number;
  top_services?:       Array<{ name: string; count: number }>;
  unpaid_count:        number;
  unpaid_amount:       number;
}

export async function getFinanceInsights(period = 'this_month'): Promise<FinanceInsights> {
  return authRequest(`/provider/insights?period=${period}`);
}

export async function getFinanceRecent(limit = 15): Promise<RecentBookingItem[]> {
  return authRequest(`/provider/finance/recent?limit=${limit}`);
}

export async function getFinanceSummary(startDate: string, endDate: string): Promise<FinanceSummary> {
  return authRequest(`/provider/finance/summary?start_date=${startDate}&end_date=${endDate}`);
}

export async function markBookingPaid(bookingId: string): Promise<{ ok: boolean; invoice_id: string; status: string }> {
  return authRequest(`/provider/finance/bookings/${bookingId}/mark-paid`, { method: 'POST' });
}

// Setup / Onboarding wizard

export interface ImportPreview {
  bio?:                 string;
  services?:            Array<{ name: string; duration_minutes?: number; price_ex_vat?: number }>;
  working_hours?:       Array<{ day: string; open: string; close: string }>;
  amenities?:           string[];
  cancellation_policy?: string;
}

export async function importUrl(url: string): Promise<ImportPreview> {
  return authRequest('/setup/import-url', {
    method: 'POST',
    body:   JSON.stringify({ url }),
  });
}

export async function applyImport(preview: ImportPreview): Promise<void> {
  return authRequest('/setup/import-apply', {
    method: 'POST',
    body:   JSON.stringify(preview),
  });
}

export async function verifyBusiness(formData: FormData): Promise<void> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/api/v1/setup/verify-business`, {
    method:  'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body:    formData,
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json())?.detail || ''; } catch { /* ignore */ }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
}

// Booking update requests

export interface BookingUpdateRequest {
  request_id:        string;
  booking_id:        string;
  customer_name?:    string;
  service_name?:     string;
  original_start:    string;
  requested_start:   string;
  requested_end:     string;
  customer_message?: string;
}

export async function getBookingUpdateRequests(): Promise<BookingUpdateRequest[]> {
  const dashboard = await authRequest<HomeDashboard>('/home/dashboard');
  const updates = dashboard.booking_updates ?? [];
  return updates.map((u) => ({
    request_id: u.booking_id,
    booking_id: u.booking_id,
    customer_name: u.customer_name,
    service_name: u.service_name,
    original_start: u.original_start,
    requested_start: u.requested_start,
    requested_end: u.requested_end,
    customer_message: '',
  }));
}

export async function respondToBookingUpdate(
  requestId: string,
  action: 'accept' | 'decline',
): Promise<void> {
  const nextStatus = action === 'accept' ? 'confirmed' : 'cancelled';
  return authRequest(`/bookings/${requestId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: nextStatus }),
  });
}

export interface AiCommandResult {
  action: string;
  message: string;
  details?: Record<string, unknown>;
}

export async function sendAiCommand(message: string): Promise<AiCommandResult> {
  return authRequest('/provider/ai/command', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
