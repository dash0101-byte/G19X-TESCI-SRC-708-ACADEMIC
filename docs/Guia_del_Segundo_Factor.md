# Guía del segundo factor — activarlo, usarlo, y qué hacer cuando algo se pierde

**Para quién es esto.** Para quien administre el sistema y para cualquiera que quiera
proteger su cuenta con un segundo paso. Todo se hace desde el panel; no hay nada que
instalar en el servidor.

**Qué es.** Además de la contraseña, un código de seis dígitos que cambia cada treinta
segundos y que genera una aplicación en su teléfono. Saber la contraseña deja de bastar
para entrar.

> **Obligatorio para administración, opcional para el resto.** Las cuentas
> `System_Admin` no pueden operar sin él: al entrar, el panel las lleva a activarlo y no
> las deja pasar de ahí. Los asesores y los líderes comerciales pueden activarlo si
> quieren.
>
> El motivo de la diferencia es el alcance: un asesor comprometido expone su cartera; una
> cuenta de administración comprometida expone el sistema entero y además puede borrar el
> rastro de haberlo hecho.

---

## 1. Activarlo (cinco minutos, una sola vez)

Necesita una aplicación de códigos en el teléfono. Cualquiera sirve: **Google
Authenticator**, **Microsoft Authenticator**, **1Password**, **Bitwarden**, **Aegis**.

1. Entre en el panel. Si su cuenta es de administración y aún no lo tiene, la pantalla de
   alta aparece sola. Si no, está en el menú de su sesión.
2. **Escanee el código QR** con la aplicación. Si la cámara no va, escriba a mano la clave
   que aparece debajo.
3. **Guarde los diez códigos de recuperación.** No en este equipo: impresos, o en un gestor
   de contraseñas. Son la única forma de entrar si pierde el teléfono, y **no se volverán a
   mostrar**.
4. Marque la casilla de que los ha guardado.
5. Escriba el código de seis dígitos que enseña la aplicación y pulse **Activar**.
6. El sistema le pedirá entrar de nuevo, ahora con el código. Es a propósito: así se
   comprueba en el momento que el teléfono quedó bien atado.

> **Por qué se pide un código antes de activar.** Si se activara solo con escanear, quien
> escaneara mal el QR se quedaría fuera de su propia cuenta sin haber visto nunca un código
> bueno. El paso 5 es lo que convierte «escaneé algo» en «mi teléfono genera los códigos de
> esta cuenta».

---

## 2. Entrar a partir de ahora

1. Correo y contraseña, como siempre.
2. El sistema pide el código. Escriba el de seis dígitos de la aplicación.

Dos cosas que conviene saber y que sorprenden la primera vez:

* **El mismo código no vale dos veces.** Si entra en un equipo y al momento quiere entrar en
  otro, espere a que el código cambie. No es un fallo: un código que sirviera dos veces se
  podría reutilizar si alguien lo ve.
* **Sirve un código de recuperación** en lugar del de seis dígitos, en cualquier momento.
  Se gasta al usarlo.

Si el teléfono va con la hora desfasada, se admite **medio minuto** de diferencia en cada
sentido. Más allá de eso, los códigos dejan de coincidir: active la hora automática en el
teléfono.

---

## 3. Si pierde el teléfono

En orden, de la más sencilla a la que necesita a otra persona:

### a) Con un código de recuperación

Entre normalmente y, donde pide el código, escriba uno de los diez que guardó. Sirven
igual, y cada uno **una sola vez**.

Nada más entrar, vaya al menú de su sesión, **quite el segundo factor y vuelva a
activarlo** con el teléfono nuevo. Eso genera un secreto nuevo, invalida el anterior y le
da diez códigos nuevos.

### b) Sin códigos, pero con otra cuenta de administración disponible

Pida a esa persona que le quite el segundo factor de la cuenta. Luego vuelva a activarlo
desde cero.

### c) Sin códigos y sin ninguna otra administración

**Este es el caso que hay que evitar, y por eso el sistema no deja llegar a él por
descuido:** la última cuenta de administración con segundo factor activo **no se lo puede
quitar**, y el panel lo dice con todas las letras cuando se intenta.

Aun así, puede ocurrir por la vía de fuera del sistema: perder el teléfono **y** los
códigos siendo la única administración. La salida exige acceso al servidor y a la base de
datos, y la deja alguien con acceso a la máquina:

```bash
python devops/pila.py exec postgres psql -U plurione -d lead_scoring_db -c "UPDATE users SET totp_activo = false, totp_sal = NULL, totp_ultimo_contador = NULL, totp_codigos_de_recuperacion = NULL WHERE email = 'correo@plurione.com';"
```

Al entrar de nuevo, el panel pedirá activarlo otra vez.

> **Que esto exija acceso al servidor es la respuesta correcta, no una carencia.** Cualquier
> mecanismo de rescate que se pudiera usar desde fuera —un enlace por correo, una pregunta
> de seguridad— sería una segunda puerta a la cuenta más poderosa del sistema, y las
> segundas puertas se acaban usando por la vía equivocada. Quien tiene acceso físico o
> administrativo al servidor ya podía hacer cualquier cosa.

**La recomendación que evita todo esto:** que **haya siempre al menos dos cuentas de
administración con segundo factor activo**. Es la única precaución que hay que tomar, y
cuesta cinco minutos.

---

## 4. Quitarlo

Desde el menú de su sesión, confirmando con un código. Se pide el código y no la contraseña
a propósito: quien deje una sesión abierta en un equipo ajeno tiene ahí la contraseña
guardada en el navegador mucho más a menudo que el teléfono.

Si es la última cuenta de administración con segundo factor, el sistema no lo permitirá.
Active el de otra antes.

---

## 5. Lo que hay que saber si alguna vez se rota `SECRET_KEY`

**Rotar esa clave invalida todas las altas de segundo factor.** Todo el mundo tendrá que
volver a escanear el QR, y los códigos de recuperación anteriores dejarán de servir.

El motivo es de diseño y está explicado en el Reporte 33: el sistema **no guarda el secreto
de nadie**. Guarda una sal, y el secreto se calcula con ella y con `SECRET_KEY` en el
momento de comprobar. Es lo que hace que un volcado de la base de datos no contenga nada
con lo que generar códigos —ni siquiera cifrado, porque no hay nada que cifrar—, y el precio
es que el secreto no sobrevive a un cambio de esa clave.

No es una situación nueva: rotar `SECRET_KEY` ya cerraba todas las sesiones. La diferencia
es que esto no se arregla volviendo a entrar.

**Antes de rotarla:**

1. Avise a todo el mundo con segundo factor activo.
2. Asegúrese de poder entrar: tras la rotación, las cuentas de administración pasarán por
   la pantalla de alta, que es accesible con solo la contraseña.
3. Que cada persona vuelva a activarlo y guarde sus códigos nuevos.

---

## 6. Preguntas que van a surgir

**¿Puedo usar el mismo teléfono para varias cuentas?** Sí. La aplicación las distingue por
el nombre, que incluye «PluriOne Lead Scoring» y el correo.

**¿Y si cambio de teléfono a uno nuevo?** Antes de deshacerse del viejo: quite el segundo
factor desde el panel y actívelo en el nuevo. Si ya se deshizo de él, use un código de
recuperación (§3a).

**¿Funciona sin internet en el teléfono?** Sí. Los códigos se calculan con la hora y el
secreto; la aplicación no consulta nada.

**¿Se puede saltar «solo esta vez»?** No, y no hay ninguna opción de recordar el
dispositivo. Un segundo factor que se salta a veces es un segundo factor que no está el día
que hace falta.

**¿El sistema manda códigos por SMS?** No, y no está previsto. Un SMS se intercepta
cambiando la tarjeta del teléfono en la operadora, que es un ataque conocido y barato; el
código de la aplicación no sale del dispositivo.
