// La traducción de lo que el servidor guarda con identificadores en inglés, y la forma en
// que se enseña el cambio de score. Es pequeña, pero la usan la ficha y la bandeja: un
// tipo sin nombre saldría en pantalla como `LINKEDIN_MESSAGE`.

import { describe, expect, it } from 'vitest';
import {
  AYUDA_DE_TIPO,
  NOMBRES_DE_ACTIVIDAD,
  TIPOS_DECLARABLES,
  describirCambioDeScore,
  formatearScore,
  nombreDeActividad,
} from './actividades';

describe('el cambio de score', () => {
  it('se escribe con una cifra decimal y coma', () => {
    expect(formatearScore(47.8)).toBe('47,8');
    expect(formatearScore(60)).toBe('60,0');
    expect(formatearScore(undefined)).toBe('—');
  });

  it('enseña el de antes y el de después', () => {
    expect(describirCambioDeScore({ score_anterior: 47.8, score: 58.6 })).toBe('47,8 → 58,6');
  });

  it('sin score anterior —una ficha recién creada— enseña solo el nuevo', () => {
    expect(describirCambioDeScore({ score_anterior: null, score: 58.6 })).toBe('58,6');
  });
});

describe('los tipos', () => {
  it('desde la ficha solo se registran las conversaciones del asesor', () => {
    // Ni lo que registra el pipeline (propuesta, reunión) ni lo que registran los
    // formularios y las plataformas (demo, descarga, webinar), ni un «otro evento» que suma
    // sin decir qué pasó.
    expect(TIPOS_DECLARABLES).toEqual(['PHONE_CALL', 'WHATSAPP_MESSAGE', 'LINKEDIN_MESSAGE']);
  });

  it('WhatsApp y LinkedIn son tipos distintos', () => {
    expect(nombreDeActividad('WHATSAPP_MESSAGE')).toBe('Mensaje de WhatsApp');
    expect(nombreDeActividad('LINKEDIN_MESSAGE')).toBe('Mensaje de LinkedIn');
  });

  it('cada casilla tiene nombre en español y una ayuda', () => {
    for (const tipo of TIPOS_DECLARABLES) {
      expect(NOMBRES_DE_ACTIVIDAD[tipo]).toBeTruthy();
      expect(AYUDA_DE_TIPO[tipo]).toBeTruthy();
    }
  });
});
