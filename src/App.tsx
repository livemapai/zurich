/**
 * App - Root Application Component
 *
 * Routes between two rendering modes:
 * - /viewer (default): deck.gl data visualization
 * - /game: React Three Fiber game experience
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ViewerPage } from '@/pages/ViewerPage';
import { GamePage } from '@/pages/GamePage';
import { TransitPage } from '@/pages/TransitPage';
import { StylesPage } from '@/pages/StylesPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Default route redirects to viewer */}
        <Route path="/" element={<Navigate to="/viewer" replace />} />

        {/* deck.gl visualization mode */}
        <Route path="/viewer" element={<ViewerPage />} />

        {/* R3F game mode */}
        <Route path="/game" element={<GamePage />} />

        {/* Transit visualization mode */}
        <Route path="/transit" element={<TransitPage />} />

        {/* AI Styles viewer mode */}
        <Route path="/styles" element={<StylesPage />} />

        {/* Fallback for unknown routes */}
        <Route path="*" element={<Navigate to="/viewer" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
