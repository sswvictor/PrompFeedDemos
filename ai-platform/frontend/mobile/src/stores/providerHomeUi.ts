import { create } from 'zustand';

type ProviderHomeView = 0 | 1; // 0 = Bookings, 1 = Inbox

interface ProviderHomeUiState {
  activeView: ProviderHomeView;
  setActiveView: (view: ProviderHomeView) => void;
  resetToBookings: () => void;
}

export const useProviderHomeUi = create<ProviderHomeUiState>((set) => ({
  activeView: 0,
  setActiveView: (view) => set({ activeView: view }),
  resetToBookings: () => set({ activeView: 0 }),
}));
