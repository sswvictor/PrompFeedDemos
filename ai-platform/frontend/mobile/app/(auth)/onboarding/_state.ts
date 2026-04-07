/**
 * Shared onboarding state — persists across screens via module scope.
 * Set by welcome.tsx after OTP verification, read by all onboarding screens.
 */
import type { InstagramConnectStatus } from '@/lib/api';

export const onboardingData: {
  email:               string;
  pendingAccessToken:  string;
  isEmailVerified:     boolean;
  igStatus:            InstagramConnectStatus | null;
  igHandle:            string;
  websiteUrl:          string;
  scanResult:          Record<string, any> | null;
} = {
  email:              '',
  pendingAccessToken: '',
  isEmailVerified:    false,
  igStatus:           null,
  igHandle:           '',
  websiteUrl:         '',
  scanResult:         null,
};
