// ============================================================================
// La matriz de prospectos
// ============================================================================
//
// Es la pantalla que más se mira. Casi todo lo que hace es pintar, pero tiene tres
// cosas que sí deciden: los tres estados excluyentes (cargando / vacía / con filas),
// el cuadrante que da color a cada fila, y qué ocurre al pulsar un botón dentro de una
// fila que también es pulsable.

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import LeadsTable from './LeadsTable.jsx';

const PROSPECTO = {
  id: 12,
  first_name: 'Ana',
  last_name: 'Ruiz',
  email: 'ana@acme.test',
  company: 'ACME S.A.',
  job_title: 'Directora de Talento',
  industry: 'Software/TI',
  source: 'LinkedIn Ads',
  current_score: 87,
  conversion_probability: 0.734,
  score_category: 'HOT',
  status: 'QUALIFIED',
};

function montar(props = {}) {
  const utilidades = {
    setSelectedCategory: vi.fn(),
    setSearchQuery: vi.fn(),
    onSelectLead: vi.fn(),
    onRefresh: vi.fn(),
  };
  render(
    <LeadsTable
      leads={[PROSPECTO]}
      loading={false}
      selectedCategory=""
      searchQuery=""
      {...utilidades}
      {...props}
    />,
  );
  return utilidades;
}

describe('los tres estados de la tabla', () => {
  it('mientras carga no enseña filas viejas', () => {
    montar({ loading: true, leads: [PROSPECTO] });

    expect(screen.getByText(/Cargando y evaluando/)).toBeInTheDocument();
    // Aunque le pasen prospectos, cargando manda: enseñar la lista anterior mientras
    // llega la nueva hace creer que el filtro no ha surtido efecto.
    expect(screen.queryByText('ana@acme.test')).not.toBeInTheDocument();
  });

  it('sin resultados lo dice, en vez de dejar el hueco en blanco', () => {
    montar({ leads: [] });
    expect(screen.getByText(/No se encontraron prospectos/)).toBeInTheDocument();
  });

  it('con resultados pinta una fila por prospecto', () => {
    montar({ leads: [PROSPECTO, { ...PROSPECTO, id: 13, email: 'luis@acme.test' }] });
    expect(screen.getByText('ana@acme.test')).toBeInTheDocument();
    expect(screen.getByText('luis@acme.test')).toBeInTheDocument();
  });
});

describe('cómo se lee cada fila', () => {
  it('la probabilidad del modelo se muestra como porcentaje entero', () => {
    montar();
    expect(screen.getByText('73%')).toBeInTheDocument();
  });

  it('un prospecto todavía sin probabilidad no escribe NaN en pantalla', () => {
    montar({ leads: [{ ...PROSPECTO, conversion_probability: null }] });

    // `Math.round(null * 100)` da 0, pero `undefined` da NaN. Un prospecto recién
    // creado, antes de su primer scoring, llega sin el campo.
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it('un prospecto sin probabilidad ninguna tampoco', () => {
    const sinCampo = { ...PROSPECTO };
    delete sinCampo.conversion_probability;
    montar({ leads: [sinCampo] });
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it('los huecos de empresa y cargo se rellenan con un texto, no con vacío', () => {
    montar({ leads: [{ ...PROSPECTO, company: null, job_title: '' }] });
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('No especificado')).toBeInTheDocument();
  });

  it('el cuadrante da su clase a la insignia', () => {
    const { container } = render(
      <LeadsTable
        leads={[
          { ...PROSPECTO, id: 1, score_category: 'HOT' },
          { ...PROSPECTO, id: 2, score_category: 'WARM' },
          { ...PROSPECTO, id: 3, score_category: 'COLD' },
        ]}
        loading={false}
        selectedCategory=""
        searchQuery=""
        setSelectedCategory={vi.fn()}
        setSearchQuery={vi.fn()}
        onSelectLead={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    for (const clase of ['badge-hot', 'badge-warm', 'badge-cold']) {
      expect(container.querySelector(`.${clase}`)).not.toBeNull();
    }
  });
});

describe('lo que llega por una publicación de LinkedIn', () => {
  it('se marca mientras no lo atienda nadie', () => {
    montar({ leads: [{ ...PROSPECTO, source: 'LinkedIn', assigned_rep_id: null }] });
    expect(screen.getByText('Nuevo desde LinkedIn')).toBeInTheDocument();
  });

  it('deja de marcarse en cuanto tiene asesor', () => {
    montar({ leads: [{ ...PROSPECTO, source: 'LinkedIn', assigned_rep_id: 3 }] });
    expect(screen.queryByText('Nuevo desde LinkedIn')).not.toBeInTheDocument();
  });

  it('un prospecto de publicidad pagada no lleva la marca', () => {
    montar({ leads: [{ ...PROSPECTO, source: 'LinkedIn Ads', assigned_rep_id: null }] });
    expect(screen.queryByText('Nuevo desde LinkedIn')).not.toBeInTheDocument();
  });
});

describe('filtros y búsqueda', () => {
  it('cada píldora pide su cuadrante y «Todos» lo limpia', async () => {
    const usuario = userEvent.setup();
    const { setSelectedCategory } = montar();

    await usuario.click(screen.getByRole('button', { name: /HOT/ }));
    await usuario.click(screen.getByRole('button', { name: /WARM/ }));
    await usuario.click(screen.getByRole('button', { name: /COLD/ }));
    await usuario.click(screen.getByRole('button', { name: 'Todos' }));

    expect(setSelectedCategory.mock.calls.map((c) => c[0])).toEqual([
      'HOT',
      'WARM',
      'COLD',
      '',
    ]);
  });

  it('la píldora activa se distingue de las demás', () => {
    montar({ selectedCategory: 'WARM' });
    expect(screen.getByRole('button', { name: /WARM/ })).toHaveClass('btn-primary');
    expect(screen.getByRole('button', { name: /HOT/ })).toHaveClass('btn-secondary');
    expect(screen.getByRole('button', { name: 'Todos' })).toHaveClass('btn-secondary');
  });

  it('el buscador es controlado: escribir avisa hacia arriba en cada tecla', async () => {
    const usuario = userEvent.setup();
    const { setSearchQuery } = montar();

    await usuario.type(screen.getByPlaceholderText(/Buscar por nombre/), 'acme');

    // El valor lo gobierna el padre, así que cada pulsación llega con una sola letra:
    // lo que se comprueba es que ninguna se pierde.
    expect(setSearchQuery).toHaveBeenCalledTimes(4);
    expect(setSearchQuery.mock.calls.map((c) => c[0])).toEqual(['a', 'c', 'm', 'e']);
  });

  it('el botón de refrescar pide recargar', async () => {
    const usuario = userEvent.setup();
    const { onRefresh } = montar();
    await usuario.click(screen.getByTitle('Refrescar lista'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

describe('abrir un prospecto', () => {
  it('pulsar la fila abre la ficha en modo lectura', async () => {
    const usuario = userEvent.setup();
    const { onSelectLead } = montar();

    await usuario.click(screen.getByText('ana@acme.test'));

    expect(onSelectLead).toHaveBeenCalledWith(12);
  });

  it('«Editar» abre en modo edición y NO dispara además el clic de la fila', async () => {
    const usuario = userEvent.setup();
    const { onSelectLead } = montar();

    await usuario.click(screen.getByTitle(/Editar información/));

    // Sin `stopPropagation` el clic subiría a la fila y se llamaría dos veces: la
    // segunda con `false`, que reabriría la ficha en lectura y perdería el modo edición.
    expect(onSelectLead).toHaveBeenCalledTimes(1);
    expect(onSelectLead).toHaveBeenCalledWith(12, true);
  });

  it('«Ficha 360» abre en lectura y tampoco duplica el aviso', async () => {
    const usuario = userEvent.setup();
    const { onSelectLead } = montar();

    await usuario.click(screen.getByTitle(/Diagnóstico 360|diagnóstico 360/));

    expect(onSelectLead).toHaveBeenCalledTimes(1);
    expect(onSelectLead).toHaveBeenCalledWith(12, false);
  });

  it('los botones de acción de una fila son los de ESA fila', async () => {
    const usuario = userEvent.setup();
    const { onSelectLead } = montar({
      leads: [PROSPECTO, { ...PROSPECTO, id: 99, email: 'otro@acme.test' }],
    });

    const filaDelSegundo = screen.getByText('otro@acme.test').closest('tr');
    await usuario.click(within(filaDelSegundo).getByTitle(/Editar información/));

    expect(onSelectLead).toHaveBeenCalledWith(99, true);
  });
});
