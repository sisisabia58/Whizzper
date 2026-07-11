import React from 'react'
import ReactDOM from 'react-dom/client'
import { Internal } from './Internal'
import './index.css'

if (window.location.hash && window.location.hash.includes("connection=")) {
  if (window.opener) {
    try {
      window.opener.postMessage({ type: "google-drive-connected", hash: window.location.hash }, "*");
      window.close();
    } catch (e) {
      console.error("Popup communication failed:", e);
    }
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Internal />
  </React.StrictMode>,
)
