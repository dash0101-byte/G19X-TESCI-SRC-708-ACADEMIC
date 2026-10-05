// ============================================================================
// Los cuatro paneles del tablero
// ============================================================================
//
// El tablero es la primera pantalla que abre el líder, y hasta hoy no tenía pruebas
// propias: lo que pinta se daba por bueno porque «solo pinta». Lo que pintaba, en el embudo,
// eran las claves del servidor —NEW, ENGAGED, QUALIFIED— en un panel por lo demás entero en
// castellano. Se encontró recorriendo la demostración con los tres roles, no leyendo código:
// la traducción lleva escrita desde el capítulo 29 y su cabecera dice que es «la única».

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AnalyticsCharts from './AnalyticsCharts.jsx';

const RESUMEN = {
  total_leads: 4,
  hot_leads_count: 1,
  warm_leads_count: 1,
  cold_leads_count: 2,
  average_score: 50.7,
  mql_to_sql_conversion_rate: 0.5,
  pipeline_distribution: { NEW: 2, ENGAGED: 1, QUALIFIED: 1 },
  top_industries: [{ industry: 'Software/TI', average_score: 35.5, lead_count: 4 }],
  leads_by_source: [],
};

describe('el embudo de conversión', () => {
  it('nombra cada etapa en castellano, como la ficha', () => {
    render(<AnalyticsCharts summary={RESUMEN} campaigns={[]} />);

    const embudo = screen.getByText('Embudo de Conversión de Ventas').closest('.glass-panel');
    expect(within(embudo).getByText('Nuevo')).toBeInTheDocument();
    expect(within(embudo).getByText('En conversación')).toBeInTheDocument();
    expect(within(embudo).getByText('Calificado')).toBeInTheDocument();
  });

  it('y no deja ninguna clave del servidor en pantalla', () => {
    // La comprobación que de verdad vigila esto: no basta con que aparezca «Nuevo», hace
    // falta que no aparezca «NEW» al lado. Si alguien añade una etapa y se olvida de la
    // tabla, esto se pone en rojo.
    render(<AnalyticsCharts summary={RESUMEN} campaigns={[]} />);

    const embudo = screen.getByText('Embudo de Conversión de Ventas').closest('.glass-panel');
    for (const clave of Object.keys(RESUMEN.pipeline_distribution)) {
      expect(
        within(embudo).queryByText(clave),
        `el embudo sigue enseñando la clave «${clave}»`,
      ).not.toBeInTheDocument();
    }
  });

  it('cada etapa lleva su cuenta y su porcentaje sobre el total', () => {
    render(<AnalyticsCharts summary={RESUMEN} campaigns={[]} />);

    const embudo = screen.getByText('Embudo de Conversión de Ventas').closest('.glass-panel');
    expect(embudo).toHaveTextContent('2 leads (50%)');
    expect(embudo).toHaveTextContent('1 leads (25%)');
  });
});

describe('sin datos', () => {
  it('sin resumen no se dibuja nada, en vez de un tablero de ceros', () => {
    const { container } = render(<AnalyticsCharts summary={null} campaigns={[]} />);

    expect(container).toBeEmptyDOMElement();
  });
});
