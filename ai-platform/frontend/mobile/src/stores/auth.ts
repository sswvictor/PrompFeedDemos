import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY    = 'fixme_provider_token';
const ID_KEY       = 'fixme_provider_id';
const NAME_KEY     = 'fixme_provider_name';
const SLUG_KEY     = 'fixme_provider_slug';
const PERSONA_KEY  = 'fixme_provider_persona';

interface AuthState {
  token:        string | null;
  providerId:   string | null;
  providerName: string | null;
  providerSlug: string | null;
  isHydrated:   boolean;

  setAuth(token: string, providerId: string, name: string, slug?: string): Promise<void>;
  clearAuth(): Promise<void>;
  rehydrate(): Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  token:        null,
  providerId:   null,
  providerName: null,
  providerSlug: null,
  isHydrated:   false,

  async setAuth(token, providerId, name, slug = '') {
    await SecureStore.setItemAsync(TOKEN_KEY,   token);
    await SecureStore.setItemAsync(ID_KEY,      providerId);
    await SecureStore.setItemAsync(NAME_KEY,    name);
    await SecureStore.setItemAsync(SLUG_KEY,    slug);
    await SecureStore.setItemAsync(PERSONA_KEY, 'provider');
    set({ token, providerId, providerName: name, providerSlug: slug });
  },

  async clearAuth() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    await SecureStore.deleteItemAsync(ID_KEY);
    await SecureStore.deleteItemAsync(NAME_KEY);
    await SecureStore.deleteItemAsync(SLUG_KEY);
    await SecureStore.deleteItemAsync(PERSONA_KEY);
    set({ token: null, providerId: null, providerName: null, providerSlug: null });
  },

  async rehydrate() {
    const token       = await SecureStore.getItemAsync(TOKEN_KEY);
    const providerId  = await SecureStore.getItemAsync(ID_KEY);
    const providerName= await SecureStore.getItemAsync(NAME_KEY);
    const providerSlug= await SecureStore.getItemAsync(SLUG_KEY);
    set({ token, providerId, providerName, providerSlug, isHydrated: true });
  },
}));
