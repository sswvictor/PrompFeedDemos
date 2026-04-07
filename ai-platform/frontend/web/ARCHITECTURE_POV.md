# POV Architecture (Customer / Provider / Salon)

This project now uses a persona-first route layout so each point of view is explicit and isolated.

## Route ownership

### Customer POV
- `/customer/onboarding` -> `src/personas/customer/onboarding/CustomerOnboardingRoute.jsx`
- `/customer/login` -> `src/personas/customer/auth/CustomerLoginRoute.jsx`
- `/customer/home` -> `src/personas/customer/home/CustomerHomePage.jsx`
- `/customer/profile` -> `src/personas/customer/profile/CustomerProfilePage.jsx`
- Customer tab bar -> `src/personas/customer/navigation/CustomerTabBar.jsx`

### Provider POV (freelancer)
- `/provider/onboarding` -> `src/personas/provider/onboarding/ProviderOnboardingRoute.jsx`
- `/provider/login` -> `src/personas/provider/auth/ProviderLoginRoute.jsx`
- `/provider/home` -> `src/personas/provider/home/ProviderHomePage.jsx`
- `/provider/profile` -> `src/personas/provider/profile/ProviderProfilePage.jsx`
- `/provider/settings` -> `src/pages/ProviderSettings.jsx`
- Provider tab bar -> `src/personas/provider/navigation/ProviderTabBar.jsx`

### Salon POV
- `/salon/onboarding` -> `src/personas/salon/onboarding/SalonOnboardingRoute.jsx`
- `/salon/login` -> `src/personas/salon/auth/SalonLoginRoute.jsx`
- `/salon/home` -> `src/personas/salon/home/SalonHomePage.jsx`
- `/salon/profile` -> `src/personas/salon/profile/SalonProfilePage.jsx`
- `/salon/settings` -> `src/pages/ProviderSettings.jsx`
- Salon tab bar -> `src/personas/salon/navigation/SalonTabBar.jsx`

## Salon team connection model (mcnulty-v2 compatible)
- Employee/staff model: `app/models/worker.py` linked by `workers.provider_id -> providers.provider_id`.
- Freelancer/chair renter link model: `providers.parent_provider_id` (self-referential provider relationship).
- Approval workflow table: `app/models/salon_link_request.py` with statuses `pending|approved|rejected|removed`.
- Salon ops API:
  - `GET /api/v1/home/dashboard` -> team + upcoming bookings + pending worker/freelancer requests.
  - `POST /api/v1/salon-links/{request_id}/approve`
  - `POST /api/v1/salon-links/{request_id}/reject`
  - `GET /api/v1/salon-links/incoming`

## Public customer-facing routes
- `/p/:slug` -> public provider profile (customer perspective)
- `/b/:slug`, `/book/:provider_id` -> booking flow (customer perspective)

## Central route contract
- `src/app/routeCatalog.js` contains canonical route constants and persona prefix helpers:
  - `ROUTES`
  - `isCustomerRoute(path)`
  - `isProviderRoute(path)`
  - `isSalonRoute(path)`

## Guardrails
- Implemented in `src/App.jsx`.
- Provider token sessions use `fixme_provider_persona` (`provider` or `salon`) to route to the correct business POV.
- If customer session exists (`fixme_token`), customer is redirected away from provider/salon paths to `/customer/home`.

## Legacy URL compatibility
- Legacy paths still resolve:
  - `/onboard` -> landing choice
  - `/onboard/customer` -> `/customer/onboarding`
  - `/onboard/provider?...` -> provider/salon onboarding routes
  - `/settings` -> provider or salon landing based on `fixme_provider_persona`

## Why this structure
- Makes onboarding/login/profile/home/nav explicit per persona.
- Prevents perspective leaks (provider/salon seeing customer booking UI after login).
- Keeps migration safe by supporting old links while team moves to canonical paths.
