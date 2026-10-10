"use client";

import { useCallback, useSyncExternalStore } from "react";

const noopSubscribe = () => () => {};

/**
 * 媒体查询 hook（水合安全）。
 * 用 useSyncExternalStore：服务端快照恒为 false，与客户端水合首帧一致，
 * 水合完成后再切换到真实媒体查询值——不会产生 hydration mismatch。
 */
export default function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    // 服务端快照：false（与首帧客户端水合渲染一致）
    () => false,
  );
}

/** 是否已在浏览器端完成水合（服务端恒 false，水合后变 true）。 */
export function useMounted(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}
