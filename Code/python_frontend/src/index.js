import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import MermaidRenderer from './MermaidRenderer';
import reportWebVitals from './reportWebVitals';

// Expose to new windows
window.React = React;
window.ReactDOM = ReactDOM;
window.MermaidRenderer = MermaidRenderer;

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Optional performance monitoring
reportWebVitals();
