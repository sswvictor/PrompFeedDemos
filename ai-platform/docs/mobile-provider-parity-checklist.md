# Mobile Provider Parity Checklist (Web -> Mobile)

Scope: provider experience only (`Home`, `AI`, `Profile`, `Settings`) in mobile app.

Out of scope in this phase: mobile auth/onboarding.

## Source of truth (web)

- Home: `frontend/web/src/personas/provider/home/ProviderHomePage.jsx`
- AI: `frontend/web/src/personas/provider/home/ProviderInsightsPage.jsx`
- Profile: `frontend/web/src/personas/provider/profile/ProviderProfilePage.jsx`
- Settings shell: `frontend/web/src/personas/provider/profile/ProviderSettingsPage.jsx`
- Settings sections: `frontend/web/src/features/settings/BusinessSettingsPage.jsx`
- Provider nav: `frontend/web/src/personas/provider/navigation/ProviderTabBar.jsx`

## Mobile target files

- Home: `frontend/mobile/app/(tabs)/index.tsx`
- AI: `frontend/mobile/app/(tabs)/insights.tsx`
- Profile: `frontend/mobile/app/(tabs)/profile.tsx`
- Settings shell: `frontend/mobile/app/(tabs)/settings/index.tsx`
- Settings sections:
  - `frontend/mobile/app/(tabs)/settings/profile.tsx`
  - `frontend/mobile/app/(tabs)/settings/services.tsx`
  - `frontend/mobile/app/(tabs)/settings/amenities.tsx`
  - `frontend/mobile/app/(tabs)/settings/calendar.tsx`
  - `frontend/mobile/app/(tabs)/settings/bot.tsx`
- API client: `frontend/mobile/src/lib/api.ts`
- Auth store: `frontend/mobile/src/stores/auth.ts`

## Phase order

1. API contract parity for provider tabs/settings
2. Home parity
3. AI parity
4. Profile parity
5. Settings parity
6. QA parity pass (web vs mobile behavior)

## Feature parity checklist

### 1) Home (Provider)

- [ ] Upcoming bookings list with the same card actions:
  - complete
  - cancel
  - reschedule
  - running late
  - report customer
- [ ] Booking updates section (accept/decline request flow)
- [ ] Join/requests section parity where applicable
- [ ] Setup wizard visibility and interaction parity
- [ ] Calendar panel parity:
  - day / week / month switching
  - day booking grouping
  - time blocks create/delete behavior
- [ ] Referral credits card parity (values, labels, formatting)
- [ ] Waitlist counter visibility parity
- [ ] Team section parity (if data is present)

### 2) AI tab

- [ ] Inbox + AI findings two-tab behavior parity
- [ ] Same suggestions/findings structure
- [ ] Same primary actions and empty/loading/error states

### 3) Profile

- [ ] Header parity:
  - level
  - following
  - followers
  - rating badge display
- [ ] Tabs: About / Services / Reviews
- [ ] Services sub-tabs: Menu / Book
- [ ] Booking-link share/open behavior parity
- [ ] Settings entry points parity from profile

### 4) Settings

- [ ] Settings hub navigation parity
- [ ] Profile section parity
- [ ] Services CRUD parity
- [ ] Amenities parity
- [ ] Calendar connect/disconnect/sync parity
- [ ] Bot settings parity (including gated states)

## QA acceptance

- [ ] Same provider data appears in web and mobile Home
- [ ] Same provider data appears in web and mobile Profile
- [ ] Settings updates from mobile are visible in web after refresh
- [ ] Calendar actions from mobile reflected in web
- [ ] AI tab data/sections align with web
- [ ] No auth/onboarding files changed in this phase
