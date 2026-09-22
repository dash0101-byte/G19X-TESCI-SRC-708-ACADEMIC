// ============================================================================
// Asignar asesor desde la ficha 360
// ============================================================================
//
// Las fichas que llegan por la página de interés vienen sin asesor: repartir cartera es una
// decisión del líder. Se comprueba:
// * que el selector solo se le ofrece a quien puede repartir —a un asesor el servidor le
//   respondería 403, y ofrecer lo que va a ser rechazado es peor que no ofrecerlo—;
// * que asignar manda `assigned_rep_id` por la ruta de siempre y recarga la ficha;
// * que se ve quién la atiende hoy, o que no la atiende nadie.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchSalesReps: vi.fn(),
  getCurrentUserRole: vi.fn(),
  updateLead: vi.fn(),
}));

import { fetchSalesReps, getCurrentUserRole, updateLead } from '../services/api';
import AsignarAsesor from './AsignarAsesor.jsx';

const ASESORES = {
  total: 2,
  items: [
    { id: 3, full_name: 'Asesor de Pruebas', leads_asignados: 4, capacity: 50 },
    { id: 4, full_name: 'Otra Asesora', leads_asignados: 9, capacity: 50 },
  ],
};

const FICHA = { id: 13, assigned_rep_id: null };

beforeEach(() => {
  fetchSalesReps.mockReset().mockResolvedValue(ASESORES);
  updateLead.mockReset().mockResolvedValue({});
  getCurrentUserRole.mockReset().mockReturnValue('Sales_Lead');
});

describe('a quién se le ofrece', () => {
  it('al líder, sí', async () => {
    render(<AsignarAsesor lead={FICHA} />);

    expect(await screen.findByLabelText('Asignar a')).toBeInTheDocument();
  });

  it('al asesor, no: ni se le enseña ni se pide el equipo', () => {
    getCurrentUserRole.mockReturnValue('Commercial_Executive');
    const { container } = render(<AsignarAsesor lead={FICHA} />);

    expect(container).toBeEmptyDOMElement();
    expect(fetchSalesReps).not.toHaveBeenCalled();
  });
});

describe('asignar', () => {
  it('manda el asesor elegido y recarga la ficha', async () => {
    const usuario = userEvent.setup();
    const recargar = vi.fn();
    render(<AsignarAsesor lead={FICHA} onAsignado={recargar} />);
    await screen.findByLabelText('Asignar a');

    await usuario.selectOptions(screen.getByLabelText('Asignar a'), '4');
    await usuario.click(screen.getByRole('button', { name: 'Asignar' }));

    await waitFor(() => expect(updateLead).toHaveBeenCalledWith(13, { assigned_rep_id: 4 }));
    expect(recargar).toHaveBeenCalled();
  });

  it('sin elegir a nadie, el botón no hace nada', async () => {
    render(<AsignarAsesor lead={FICHA} />);
    await screen.findByLabelText('Asignar a');

    expect(screen.getByRole('button', { name: 'Asignar' })).toBeDisabled();
  });

  it('un rechazo del servidor se enseña y no se traga', async () => {
    const usuario = userEvent.setup();
    updateLead.mockRejectedValue(new Error('No puede cambiar el asesor asignado.'));
    render(<AsignarAsesor lead={FICHA} />);
    await screen.findByLabelText('Asignar a');

    await usuario.selectOptions(screen.getByLabelText('Asignar a'), '4');
    await usuario.click(screen.getByRole('button', { name: 'Asignar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No puede cambiar el asesor');
  });
});

describe('quién la atiende hoy', () => {
  it('sin asesor, lo dice', async () => {
    render(<AsignarAsesor lead={FICHA} />);

    expect(await screen.findByText('Sin asesor')).toBeInTheDocument();
  });

  it('con asesor, lo nombra y ofrece reasignar', async () => {
    render(<AsignarAsesor lead={{ ...FICHA, assigned_rep_id: 3 }} />);

    expect(await screen.findByText('Asesor de Pruebas')).toBeInTheDocument();
    expect(screen.getByLabelText('Reasignar a')).toBeInTheDocument();
  });
});
