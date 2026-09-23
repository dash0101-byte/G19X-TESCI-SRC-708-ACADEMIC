import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import PaginaDeInteres from './components/PaginaDeInteres.jsx';
import { redDeLaUrl } from './services/api';
import './index.css';

// La única ruta pública del sistema: `/interes/<enlace de la publicación>`. No hay
// enrutador porque no hay más rutas: el panel entero vive en «/» y cambia de pestaña por
// estado. Añadir uno para un solo caso sería más código del que ahorra.
const RUTA_DE_INTERES = /^\/interes\/([A-Za-z0-9_-]{6,64})\/?$/;
const enInteres = RUTA_DE_INTERES.exec(window.location.pathname);

// La red por la que se repartió el enlace (`?r=whatsapp`), tal cual viene. No se comprueba
// aquí: la reconoce el servidor, y una que no reconozca se cuenta como «sin red» sin
// estorbar a quien está intentando escribir (capítulo 27).
const red = redDeLaUrl();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {enInteres ? <PaginaDeInteres slug={enInteres[1]} red={red} /> : <App />}
  </React.StrictMode>,
);
