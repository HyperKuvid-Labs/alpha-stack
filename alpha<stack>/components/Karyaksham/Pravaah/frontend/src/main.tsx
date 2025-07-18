import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './assets/index.css'; // Assuming global styles are defined here

// Create a React root and render the main App component into the DOM.
// The 'root' element is typically defined in public/index.html.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);