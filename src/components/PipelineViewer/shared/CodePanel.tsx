/**
 * CodePanel - Syntax-Highlighted Code Display
 *
 * Uses CodeMirror for syntax highlighting with a dark theme.
 * Supports JSON, TypeScript, and Protobuf languages.
 */

import { useMemo } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { EditorView } from '@codemirror/view';

interface CodePanelProps {
  code: string;
  language: string;
  title: string;
  editable?: boolean;
  onChange?: (value: string) => void;
  error?: string | null;
}

/** Custom dark theme for code panels */
const darkTheme = EditorView.theme(
  {
    '&': {
      backgroundColor: 'transparent',
      fontSize: '13px',
    },
    '.cm-content': {
      fontFamily: "'SF Mono', Monaco, 'Cascadia Code', Consolas, monospace",
      padding: '12px 0',
    },
    '.cm-gutters': {
      backgroundColor: 'rgba(0, 0, 0, 0.2)',
      borderRight: '1px solid rgba(255, 255, 255, 0.05)',
      color: 'rgba(255, 255, 255, 0.3)',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'rgba(136, 192, 255, 0.1)',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(136, 192, 255, 0.05)',
    },
    '.cm-selectionBackground': {
      backgroundColor: 'rgba(136, 192, 255, 0.2) !important',
    },
    '.cm-cursor': {
      borderLeftColor: '#88c0ff',
    },
    '.cm-matchingBracket': {
      backgroundColor: 'rgba(136, 192, 255, 0.3)',
      outline: 'none',
    },
  },
  { dark: true }
);

/** Syntax highlighting colors */
const syntaxHighlighting = EditorView.theme(
  {
    '.cm-keyword': { color: '#c792ea' },
    '.cm-string': { color: '#c3e88d' },
    '.cm-number': { color: '#f78c6c' },
    '.cm-propertyName': { color: '#82aaff' },
    '.cm-punctuation': { color: '#89ddff' },
    '.cm-comment': { color: '#676e95', fontStyle: 'italic' },
    '.cm-variableName': { color: '#eeffff' },
    '.cm-typeName': { color: '#ffcb6b' },
    '.cm-operator': { color: '#89ddff' },
  },
  { dark: true }
);

export function CodePanel({
  code,
  language,
  title,
  editable = false,
  onChange,
  error,
}: CodePanelProps) {
  // Select language extension based on type
  const extensions = useMemo(() => {
    const exts = [darkTheme, syntaxHighlighting, EditorView.lineWrapping];

    if (language === 'json') {
      exts.push(json());
    } else if (language === 'typescript' || language === 'javascript') {
      exts.push(javascript({ typescript: language === 'typescript' }));
    }
    // Protobuf uses default highlighting (no specific extension)

    return exts;
  }, [language]);

  return (
    <div className="code-panel">
      <div className="code-panel-header">
        <span className="code-panel-title">{title}</span>
        <span className="code-panel-language">{language}</span>
      </div>

      <div className="code-panel-content">
        <CodeMirror
          value={code}
          height="auto"
          extensions={extensions}
          editable={editable}
          onChange={onChange}
          basicSetup={{
            lineNumbers: true,
            foldGutter: false,
            highlightActiveLineGutter: true,
            highlightActiveLine: true,
            bracketMatching: true,
            autocompletion: false,
            searchKeymap: false,
          }}
        />
      </div>

      {error && (
        <div className="code-error">
          <span className="error-icon">⚠</span>
          <span className="error-message">{error}</span>
        </div>
      )}
    </div>
  );
}
