/**
 * PipelinePage - MapLibre Pipeline Educational Visualization
 *
 * Interactive visualization explaining how the vector tile pipeline
 * works - from raw geodata to rendered map on screen.
 *
 * Route: /pipeline
 */

import { PipelineViewer } from '@/components/PipelineViewer';

export function PipelinePage() {
  return <PipelineViewer />;
}

export default PipelinePage;
