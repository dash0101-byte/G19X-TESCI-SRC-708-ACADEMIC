import React from 'react';

/**
 * «N nuevos de publicaciones, sin asesor», en los dos sitios donde hace falta.
 *
 * Nació dentro de `Publicaciones` en el capítulo 25 y ahí se quedó. El punto 11 de §6.2
 * decía por qué eso no bastaba, con una frase que es toda la explicación: **el tablero es
 * donde el líder mira primero**. Un aviso de que hay trabajo sin repartir que solo se ve
 * entrando a la pestaña de las publicaciones es un aviso que hay que ir a buscar, y el
 * capítulo 28 lo dio por cerrado sin estarlo.
 *
 * Se saca a un componente en vez de copiar el bloque. La frase, el plural y el criterio de
 * cuándo se enseña viven **una vez**: dos copias se habrían desincronizado en el primer
 * cambio de texto, y una de las dos habría quedado diciendo algo distinto del número que
 * tiene al lado, que es exactamente la avería del capítulo 27.
 *
 * El número lo cuenta siempre el servidor (`nuevos_sin_asesor`), con la misma condición que
 * marca las fichas en el listado (`es_de_publicacion` y sin asesor asignado). Aquí no se
 * calcula nada.
 *
 * `onIrARepartir` es opcional a propósito: en el tablero el contador es el punto de partida
 * y tiene que llevar a donde se reparten; dentro de «Publicaciones» no, porque quien está
 * ahí vino a gestionar publicaciones y el salto le sacaría de lo que estaba haciendo.
 */
export default function ContadorSinAsesor({ total, onIrARepartir }) {
  // `null` es «no se ha preguntado» —o «no se preguntó porque es un asesor»— y no es cero.
  if (total === null || total === undefined) return null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '10px 14px',
        margin: '14px 0',
        background: 'var(--bg-surface-elevated)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.8rem',
        flexWrap: 'wrap',
      }}
    >
      <strong style={{ fontSize: '1.2rem', fontFamily: 'var(--font-mono)' }}>{total}</strong>
      <span>
        Nuevos de publicaciones, sin asesor.
        {total > 0 && ' Están esperando a que alguien los atienda.'}
      </span>
      {onIrARepartir && total > 0 && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onIrARepartir}>
          Ver y repartir
        </button>
      )}
    </div>
  );
}
