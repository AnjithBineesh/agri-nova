"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { Farm } from "./types";

const KEY = "agrinova.farm";

interface FarmState {
  farms: Farm[];
  farm: Farm | null;
  loading: boolean;
  error: string | null;
  selectFarm: (id: number) => void;
  reload: () => Promise<Farm[]>;
}

const FarmContext = createContext<FarmState | null>(null);

export function FarmProvider({ children }: { children: React.ReactNode }) {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const list = await api.get<Farm[]>("/api/farms");
      setFarms(list);
      setError(null);
      setSelected((cur) => {
        let stored: number | null = null;
        try {
          stored = Number(window.localStorage.getItem(KEY)) || null;
        } catch {
          stored = null;
        }
        const want = cur ?? stored;
        return list.find((f) => f.id === want)?.id ?? list[0]?.id ?? null;
      });
      return list;
    } catch (e: any) {
      setError(e.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const selectFarm = (id: number) => {
    setSelected(id);
    try {
      window.localStorage.setItem(KEY, String(id));
    } catch {
      /* ignore */
    }
  };

  const farm = farms.find((f) => f.id === selected) ?? null;
  return (
    <FarmContext.Provider value={{ farms, farm, loading, error, selectFarm, reload }}>{children}</FarmContext.Provider>
  );
}

export function useFarm() {
  const ctx = useContext(FarmContext);
  if (!ctx) throw new Error("useFarm must be used inside FarmProvider");
  return ctx;
}
