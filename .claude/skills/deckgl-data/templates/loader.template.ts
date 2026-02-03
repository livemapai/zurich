/**
 * {DataName} Data Loader
 *
 * Loads {description} from {source}
 */

import type { {DataType} } from '@/types';

export interface {DataName}LoadOptions {
  onProgress?: (progress: number) => void;
  signal?: AbortSignal;
}

/**
 * Load {DataName} data from URL
 */
export async function load{DataName}(
  url: string,
  options: {DataName}LoadOptions = {}
): Promise<{DataType}> {
  const { onProgress, signal } = options;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load {DataName}: ${response.statusText}`);
  }

  // TODO: Add progress tracking if Content-Length available
  if (onProgress) {
    onProgress(50);
  }

  const data = await response.json();

  // TODO: Add validation

  if (onProgress) {
    onProgress(100);
  }

  return data as {DataType};
}
