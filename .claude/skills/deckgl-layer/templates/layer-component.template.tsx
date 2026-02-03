/**
 * {LayerName}Layer React Component
 */

import { useMemo } from 'react';
import { create{LayerName}Layer, type {LayerName}LayerConfig } from '@/layers/{LayerName}Layer';
import type { {DataType} } from '@/types';

interface {LayerName}LayerProps extends {LayerName}LayerConfig {
  data: {DataType}[] | null;
}

export function {LayerName}Layer({ data, ...config }: {LayerName}LayerProps) {
  const layer = useMemo(() => {
    if (!data || data.length === 0) return null;
    return create{LayerName}Layer(data, config);
  }, [data, config.visible, config.opacity, config.pickable]);

  return layer;
}
