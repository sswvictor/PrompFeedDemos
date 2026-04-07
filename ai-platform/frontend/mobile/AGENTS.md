# Mobile App — Provider Architecture (Source of Truth)

This file is the single source of truth for the Fixmeapp Provider mobile app structure.
All AI assistants working on this codebase must follow these rules.

---

## 1) App Structure

**Framework:** Expo SDK 52 + Expo Router v4 (file-based routing)
**Styling:** NativeWind (Tailwind via `className` props)
**Auth state:** Zustand (`src/stores/auth.ts`) + `expo-secure-store`
**API client:** `src/lib/api.ts` — single source of truth for all API calls

---

## 2) Navigation Shell Contract (DO NOT BREAK)

The provider app has exactly **3 bottom nav tabs**:

| Tab | Route | Icon/Label |
|-----|-------|------------|
| Home | `/(tabs)/` | Home |
| AI | `/(tabs)/ai` | AI |
| Profile | `/(tabs)/profile` | Profile |

Source of truth: `app/(tabs)/_layout.tsx`

---

## 3) Profile Screen Contract

**File:** `app/(tabs)/profile/index.tsx`

The Profile screen is Instagram-inspired. Layout:
- **Top section:** Provider photo, name, city, stats
- **Top-right corner:** Settings icon → navigates to `/(tabs)/settings`
- **Content tab row** (3 tabs, horizontal):
  - `About` — bio, amenities, location info
  - `Services` — has two sub-tabs:
    - `Book` — bookable services list
    - `Menu` — full price menu
  - `Reviews` — client reviews and ratings

Do not remove the tab row. Do not merge tabs. The three tabs and two Services sub-tabs are locked.

---

## 4) Settings Screen Contract

**File:** `app/(tabs)/settings/index.tsx` (and sub-screens)

Settings is accessible via the top-right icon on the Profile screen.

Settings contains:
- **Edit profile** (`settings/profile.tsx`) — change name, bio, phone, city, Instagram handle, address
- **Manage services** (`settings/services.tsx`) — edit existing services, add new via:
  - Manual input form
  - Photo/screenshot scan (OCR via `POST /onboarding/scan-price-list`)
- **Other settings** — bot config, calendar integrations, etc.

---

## 5) Auth / Onboarding Flow

```
welcome.tsx (cinematic + email inline + OTP)
    ↓ new provider
onboarding/step1.tsx (AI website scan — optional)
    ↓
onboarding/step2.tsx (Instagram handle → createOnboardingProvider → home)
    ↓ existing provider
/(tabs)/  (home dashboard)
```

- `welcome.tsx` handles both new and existing providers in one screen (two phases: splash / otp)
- No separate login.tsx — welcome handles everything
- `onboardingData` module-scope object in `step1.tsx` carries state across onboarding steps

---

## 6) API Client Rules

- All API calls go through `src/lib/api.ts`
- `authRequest()` is the authenticated wrapper — always use it for protected endpoints
- Never call fetch directly in screen components
- `getMyProviderProfile()` → `GET /provider/me` → returns `ProviderProfile`
- `getProviderSession()` → `GET /auth/provider/me` → returns `ProviderMeResult` (auth check only)
- These are different — do not mix them

---

## 7) File Ownership Rules

- Touch only files required for the task at hand
- Never rewrite a file that was not part of the current task scope
- Never delete files unless explicitly instructed
- Before editing any file, read it first
- `app.json` typedRoutes is set to `false` — do not change it back to `true`
