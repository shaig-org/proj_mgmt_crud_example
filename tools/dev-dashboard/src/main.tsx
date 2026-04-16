import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/tokens.css';
import './styles/layout.css';
import './flame.css';

const el = document.getElementById('root');
if (!el) throw new Error('#root not found');

createRoot(el).render(<App />);
void StrictMode;
