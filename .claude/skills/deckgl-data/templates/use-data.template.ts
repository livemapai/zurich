/**
 * use{DataName} Hook
 *
 * Loads and caches {DataName} data with loading state management
 */

import { useState, useEffect } from 'react';
import { load{DataName} } from '@/lib/data/{dataName}';
import type { {DataType}, LoadingState } from '@/types';

export function use{DataName}(url: string | null): LoadingState<{DataType}> {
  const [state, setState] = useState<LoadingState<{DataType}>>({
    data: null,
    isLoading: false,
    error: null,
    progress: 0,
  });

  useEffect(() => {
    if (!url) {
      setState({ data: null, isLoading: false, error: null, progress: 0 });
      return;
    }

    const controller = new AbortController();

    setState((prev) => ({ ...prev, isLoading: true, error: null, progress: 0 }));

    load{DataName}(url, {
      onProgress: (progress) => {
        setState((prev) => ({ ...prev, progress }));
      },
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, isLoading: false, error: null, progress: 100 });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== 'AbortError') {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            error: error instanceof Error ? error : new Error(String(error)),
            progress: 0,
          }));
        }
      });

    return () => controller.abort();
  }, [url]);

  return state;
}
