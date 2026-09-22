// ============================================================================
// El simulador de scoring
// ============================================================================
//
// Es el único componente que llama sola a la API mientras alguien mueve un control.
// Eso trae dos problemas que no se ven mirando el código: cuántas veces llama, y qué
// respuesta gana cuando llegan dos desordenadas.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { act } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// El módulo de API se sustituye entero: aquí se prueba el componente, no el transporte.
vi.mock('../services/api', () => ({
  predictScoreLive: vi.fn(),
}));

import { predictScoreLive } from '../services/api';
import ScoringSimulator from './ScoringSimulator.jsx';

const PREDICCION = {
  score: 88,
  score_category: 'HOT',
  conversion_probability: 0.81,
  ml_probability: 0.78,
  heuristic_score: 92,
  decay_factor: 1.0,
  ai_explanation: { recommended_action: 'Llamar hoy mismo.' },
};

/** Cambia el valor de un control gobernado por React. */
async function cambiar(elemento, valor) {
  await act(async () => {
    fireEvent.change(elemento, { target: { value: valor } });
  });
}

/** Avanza los temporizadores falsos dentro de `act`, para que React procese el estado. */
async function avanzar(ms) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  predictScoreLive.mockReset();
});

describe('la primera evaluación', () => {
  it('no llama nada más montarse: espera a que el pulso se calme', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);

    expect(predictScoreLive).not.toHaveBeenCalled();

    await avanzar(250);
    expect(predictScoreLive).toHaveBeenCalledTimes(1);
  });

  it('mientras no hay resultado enseña un hueco, no un cero que parece una puntuación', () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('al llegar la respuesta pinta la puntuación, el cuadrante y el desglose', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);
    await avanzar(250);

    await waitFor(() => expect(screen.getByText('88')).toBeInTheDocument());
    expect(screen.getByText('HOT')).toBeInTheDocument();
    expect(screen.getByText('Prob. ML: 81%')).toBeInTheDocument();
    // 0.78 * 60 y 92 * 0.4
    expect(screen.getByText('46.8 pts')).toBeInTheDocument();
    expect(screen.getByText('36.8 pts')).toBeInTheDocument();
    expect(screen.getByText('Llamar hoy mismo.')).toBeInTheDocument();
  });
});

describe('el pulso de las peticiones', () => {
  it('mover un control muchas veces seguidas produce UNA sola llamada', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    const { container } = render(<ScoringSimulator />);
    await avanzar(250);
    predictScoreLive.mockClear();

    const deslizador = container.querySelector('input[type="range"]');
    for (const valor of ['1', '2', '3', '4', '5']) {
      await cambiar(deslizador, valor);
      await act(async () => {
        vi.advanceTimersByTime(50); // menos que el pulso de 250 ms
      });
    }
    await avanzar(300);

    // Sin el `clearTimeout` del efecto serían cinco inferencias por cada arrastre del
    // deslizador, y cada una ejecuta el modelo en el servidor.
    expect(predictScoreLive).toHaveBeenCalledTimes(1);
  });

  it('una respuesta vieja que llega tarde no pisa a la nueva', async () => {
    // Dos inferencias en vuelo. La PRIMERA tarda más que la segunda: es lo que ocurre
    // cuando el modelo tiene que generar la explicación por IA en una y en otra no.
    let resolverPrimera;
    predictScoreLive
      .mockImplementationOnce(
        () =>
          new Promise((r) => {
            resolverPrimera = () => r({ ...PREDICCION, score: 11, score_category: 'COLD' });
          }),
      )
      .mockResolvedValueOnce({ ...PREDICCION, score: 99, score_category: 'HOT' });

    const { container } = render(<ScoringSimulator />);
    await avanzar(250); // dispara la primera, que se queda colgada

    const deslizador = container.querySelector('input[type="range"]');
    await cambiar(deslizador, '20');
    await avanzar(250); // dispara la segunda, que responde ya

    await waitFor(() => expect(screen.getByText('99')).toBeInTheDocument());

    // Y AHORA contesta la primera, con datos de una entrada que ya nadie tiene delante.
    await act(async () => {
      resolverPrimera();
      await Promise.resolve();
    });

    // Lo que se ve tiene que corresponder a lo que hay en los controles.
    expect(screen.getByText('99')).toBeInTheDocument();
    expect(screen.queryByText('11')).not.toBeInTheDocument();
  });
});

describe('cuando la inferencia falla', () => {
  it('lo dice en pantalla en vez de dejar el resultado anterior como si fuera nuevo', async () => {
    predictScoreLive.mockResolvedValueOnce(PREDICCION);
    const { container } = render(<ScoringSimulator />);
    await avanzar(250);
    await waitFor(() => expect(screen.getByText('88')).toBeInTheDocument());

    predictScoreLive.mockRejectedValueOnce(new Error('Error en inferencia de scoring'));
    const deslizador = container.querySelector('input[type="range"]');
    await cambiar(deslizador, '20');
    await avanzar(250);

    // El fallo iba a `console.error` y nada más: en pantalla seguía el 88 de la entrada
    // ANTERIOR, indistinguible de una evaluación recién hecha de la entrada actual.
    await waitFor(() =>
      expect(screen.getByText(/Error en inferencia de scoring/)).toBeInTheDocument(),
    );
  });

  it('el aviso de error desaparece en cuanto una evaluación vuelve a funcionar', async () => {
    predictScoreLive.mockRejectedValueOnce(new Error('Servicio no disponible'));
    const { container } = render(<ScoringSimulator />);
    await avanzar(250);
    await waitFor(() => expect(screen.getByText(/Servicio no disponible/)).toBeInTheDocument());

    predictScoreLive.mockResolvedValueOnce(PREDICCION);
    const deslizador = container.querySelector('input[type="range"]');
    await cambiar(deslizador, '9');
    await avanzar(250);

    await waitFor(() => expect(screen.getByText('88')).toBeInTheDocument());
    expect(screen.queryByText(/Servicio no disponible/)).not.toBeInTheDocument();
  });
});

describe('los controles', () => {
  it('la atenuación temporal se calcula con vida media de 14 días', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);

    // Con 0 días de inactividad no hay pérdida ninguna.
    expect(screen.getByText(/Atenuación: 100\.0%/)).toBeInTheDocument();
  });

  it('a los 14 días la atenuación es exactamente la mitad', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    const { container } = render(<ScoringSimulator />);

    const deslizadores = container.querySelectorAll('input[type="range"]');
    const decaimiento = deslizadores[deslizadores.length - 1];
    await cambiar(decaimiento, '14');

    expect(screen.getByText(/Atenuación: 50\.0%/)).toBeInTheDocument();
  });

  it('marcar una casilla de intención comercial entra en la siguiente inferencia', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);
    await avanzar(250);
    predictScoreLive.mockClear();

    const propuesta = screen.getByLabelText(/Propuesta \/ Cotización/);
    await act(async () => {
      fireEvent.click(propuesta);
    });
    await avanzar(250);

    expect(predictScoreLive).toHaveBeenCalledTimes(1);
    expect(predictScoreLive.mock.calls[0][0]).toMatchObject({ proposal_sent: true });
  });

  it('el cargo escrito a mano viaja tal cual al motor', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);
    await avanzar(250);
    predictScoreLive.mockClear();

    const cargo = screen.getByPlaceholderText(/Ej. CTO/);
    await cambiar(cargo, 'Jefa de Selección');
    await avanzar(250);

    expect(predictScoreLive.mock.calls[0][0]).toMatchObject({ job_title: 'Jefa de Selección' });
  });
});

describe('cada control escribe su propio campo', () => {
  // Todos los controles comparten un `handleChange(campo, valor)`. Un campo mal escrito
  // en la llamada no rompe nada visible: el motor recibe el objeto sin esa clave, usa su
  // valor por defecto, y el simulador enseña una puntuación que no corresponde a lo que
  // hay en pantalla. Esta tabla comprueba, control a control, que lo que se mueve es lo
  // que viaja.
  const CASOS = [
    ['Tamaño de Empresa', 'select', '11-50', { company_size: '11-50' }],
    ['Urgencia de Contratación', 'select', 'EXPLORATORIA', { urgency: 'EXPLORATORIA' }],
    ['Solicitó Demo', 'checkbox', null, { requested_demo: false }],
    ['Reunión Agendada', 'checkbox', null, { meeting_scheduled: true }],
    ['Asistió a Webinar', 'checkbox', null, { attended_webinar: false }],
  ];

  it.each(CASOS)('%s', async (etiqueta, tipo, valor, esperado) => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);
    await avanzar(250);
    predictScoreLive.mockClear();

    // Coincidencia por subcadena con una función: las etiquetas llevan paréntesis,
    // barras y signos «+», que en una expresión regular habría que escapar uno a uno.
    const control = screen.getByLabelText((texto) => texto.includes(etiqueta));
    if (tipo === 'checkbox') {
      await act(async () => {
        fireEvent.click(control);
      });
    } else {
      await cambiar(control, valor);
    }
    await avanzar(250);

    expect(predictScoreLive).toHaveBeenCalledTimes(1);
    expect(predictScoreLive.mock.calls[0][0]).toMatchObject(esperado);
  });

  it('los deslizadores mandan números, no las cadenas que da el DOM', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    const { container } = render(<ScoringSimulator />);
    await avanzar(250);
    predictScoreLive.mockClear();

    const deslizadores = container.querySelectorAll('input[type="range"]');
    await cambiar(deslizadores[0], '17');
    await avanzar(250);

    const enviado = predictScoreLive.mock.calls[0][0];
    // Sin el `parseInt`, el backend recibiría "17" y Pydantic lo aceptaría por coerción;
    // pero el contador de la propia pantalla concatenaría en vez de sumar.
    expect(enviado.page_views).toBe(17);
    expect(typeof enviado.page_views).toBe('number');
  });

  it('los clics en las casillas se reflejan en la propia casilla', async () => {
    predictScoreLive.mockResolvedValue(PREDICCION);
    render(<ScoringSimulator />);

    const demo = screen.getByLabelText(/Solicitó Demo/);
    expect(demo).toBeChecked();
    await act(async () => {
      fireEvent.click(demo);
    });
    expect(demo).not.toBeChecked();
  });
});
