import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuth = create(
  persist(
    (set) => ({
      token: null,
      refresh: null,
      user: null,
      setAuth: (token, refresh, user) => set({ token, refresh, user }),
      logout: () => set({ token: null, refresh: null, user: null }),
    }),
    { name: "splito-auth" }
  )
);
