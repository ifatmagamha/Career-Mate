/// <reference types="vite/client" />

// Backend address. To run the API elsewhere, create ui/.env.local with e.g. VITE_API_URL=http://localhost:8010
export const API: string = import.meta.env.VITE_API_URL || 'http://localhost:8000';
