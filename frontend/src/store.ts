import { create } from 'zustand';

type AppState = {
  activePage: string;
  setActivePage: (page: string) => void;
};

export const useAppStore = create<AppState>((set) => ({
  activePage: 'Dashboard',
  setActivePage: (page) => set({ activePage: page })
}));
