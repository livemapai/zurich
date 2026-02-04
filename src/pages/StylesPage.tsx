/**
 * StylesPage - AI Styles Viewer Page
 *
 * Displays AI-generated tile styles on a MapLibre map with a
 * sidebar for style selection and generation status.
 *
 * Route: /styles
 */

import { StylesViewer } from '@/components/StylesViewer';
import '@/styles/styles-page.css';

export function StylesPage() {
  return <StylesViewer />;
}

export default StylesPage;
