import React from 'react';

// Perfiles recibidos por día: una barra por día, con los días sin perfiles a cero para que un
// hueco no se lea como un dato que falta. Sin librería de gráficos: son barras, y un SVG
// basta.
//
// Solo perfiles, no visitas: dos series en una misma escala esconderían la que es diez veces
// más pequeña, que es justo la que importa. Las visitas del periodo van en su dato de arriba
// y, día a día, en la tabla que acompaña al gráfico.
const ALTO = 120;
const ANCHO_DE_BARRA = 10;
const SEPARACION = 3;

function etiquetaDelDia(dia) {
  const [, mes, numero] = dia.split('-');
  return `${Number(numero)}/${Number(mes)}`;
}

export default function GraficoPorDia({ dias, recortado = false }) {
  if (!dias || dias.length === 0) {
    return (
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Todavía no hay visitas ni perfiles que dibujar.
      </p>
    );
  }
  const maximo = Math.max(1, ...dias.map((d) => d.perfiles));
  const ancho = dias.length * (ANCHO_DE_BARRA + SEPARACION);
  const total = dias.reduce((suma, d) => suma + d.perfiles, 0);
  const primero = dias[0].dia;
  const ultimo = dias[dias.length - 1].dia;

  return (
    <figure style={{ margin: '0 0 16px' }}>
      <figcaption style={{ fontSize: '0.8rem', fontWeight: 700, marginBottom: '6px' }}>
        Perfiles recibidos por día
        {recortado && (
          <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}> (los últimos {dias.length} días)</span>
        )}
      </figcaption>
      <div style={{ overflowX: 'auto' }}>
        <svg
          role="img"
          aria-label={`${total} perfiles entre el ${etiquetaDelDia(primero)} y el ${etiquetaDelDia(ultimo)}; el día con más recibió ${Math.max(...dias.map((d) => d.perfiles))}.`}
          width={Math.max(ancho, 120)}
          height={ALTO + 18}
          style={{ display: 'block' }}
        >
          <line x1="0" y1={ALTO} x2={Math.max(ancho, 120)} y2={ALTO} stroke="var(--border-subtle)" />
          {dias.map((d, i) => {
            const alto = Math.round((d.perfiles / maximo) * (ALTO - 10));
            return (
              <rect
                key={d.dia}
                data-testid="barra"
                x={i * (ANCHO_DE_BARRA + SEPARACION)}
                y={ALTO - alto}
                width={ANCHO_DE_BARRA}
                height={alto}
                rx="2"
                fill="var(--color-primary)"
              >
                <title>{`${etiquetaDelDia(d.dia)}: ${d.perfiles} perfiles, ${d.visitas} visitas`}</title>
              </rect>
            );
          })}
          <text x="0" y={ALTO + 14} fontSize="10" fill="var(--text-muted)">{etiquetaDelDia(primero)}</text>
          <text x={Math.max(ancho, 120)} y={ALTO + 14} fontSize="10" fill="var(--text-muted)" textAnchor="end">
            {etiquetaDelDia(ultimo)}
          </text>
        </svg>
      </div>
      <details style={{ marginTop: '6px', fontSize: '0.75rem' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>Ver los datos día a día</summary>
        <table style={{ borderCollapse: 'collapse', marginTop: '6px' }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              <th scope="col" style={{ padding: '2px 8px' }}>Día</th>
              <th scope="col" style={{ padding: '2px 8px' }}>Perfiles</th>
              <th scope="col" style={{ padding: '2px 8px' }}>Visitas</th>
            </tr>
          </thead>
          <tbody>
            {dias.map((d) => (
              <tr key={d.dia}>
                <th scope="row" style={{ padding: '2px 8px', textAlign: 'left', fontWeight: 400 }}>{d.dia}</th>
                <td style={{ padding: '2px 8px', fontFamily: 'var(--font-mono)' }}>{d.perfiles}</td>
                <td style={{ padding: '2px 8px', fontFamily: 'var(--font-mono)' }}>{d.visitas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
