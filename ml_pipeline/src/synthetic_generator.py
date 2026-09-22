import random

import numpy as np
import pandas as pd


def generate_synthetic_leads_dataset(num_samples: int = 2500, random_seed: int = 42) -> pd.DataFrame:
    """
    Genera un dataset sintético de prospectos B2B para PluriOne S.A. de C.V.

    ADVERTENCIA SOBRE LA NATURALEZA DE ESTOS DATOS
    ----------------------------------------------
    La etiqueta `converted` NO procede de resultados comerciales observados: se calcula
    aquí, como una función suave de las propias variables más un término de ruido. Un
    modelo entrenado sobre esto está aprendiendo a recuperar la fórmula de abajo, no a
    predecir el comportamiento de un comprador real.

    Eso hace que las métricas obtenidas sirvan para **verificar la integridad del
    pipeline** —que las variables llegan, que el preprocesado no las corrompe, que la
    calibración funciona— y no como estimación del rendimiento en producción. El
    Capítulo 12 de la memoria técnica desarrolla esta distinción, que es la primera
    pregunta razonable que cabe hacerle a un ROC-AUC de 0.94.

    La probabilidad latente que genera la etiqueta se usa internamente y **no se publica**
    en el DataFrame: es la respuesta del examen. Un modelo entrenado con esa columna entre
    sus variables alcanzaría una precisión casi perfecta sin haber aprendido nada.
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    job_titles = [
        ("CTO", 0.90),
        ("CIO", 0.88),
        ("Director de Tecnología", 0.85),
        ("VP de Recursos Humanos", 0.82),
        ("Head of Engineering", 0.80),
        ("Gerente de Talento TI", 0.70),
        ("Engineering Manager", 0.65),
        ("Director de Operaciones", 0.60),
        ("Gerente de Proyectos TI", 0.45),
        ("Líder Técnico", 0.40),
        ("Desarrollador Senior", 0.25),
        ("Consultor Independiente", 0.15),
        ("Estudiante / Trainee", 0.05),
    ]

    industries = [
        ("FinTech", 0.85),
        ("Software/TI", 0.80),
        ("Banking", 0.78),
        ("E-Commerce", 0.70),
        ("Healthcare", 0.60),
        ("Logistics", 0.55),
        ("Retail", 0.50),
        ("Consulting", 0.45),
        ("Manufacturing", 0.35),
        ("Education", 0.25),
    ]

    company_sizes = [
        ("1000+", 0.80),
        ("201-1000", 0.75),
        ("51-200", 0.60),
        ("11-50", 0.40),
        ("1-10", 0.20),
    ]

    channels = [
        ("LinkedIn Ads", 0.75),
        ("Webinar", 0.70),
        ("Demo Request Form", 0.85),
        ("Organic Search", 0.55),
        ("Outbound Cold Email", 0.40),
        ("Referral", 0.80),
    ]

    data = []

    for i in range(num_samples):
        # Seleccionar atributos con probabilidades ponderadas
        title, title_weight = random.choices(job_titles, weights=[0.10, 0.08, 0.12, 0.10, 0.10, 0.12, 0.10, 0.08, 0.08, 0.05, 0.04, 0.02, 0.01])[0]
        industry, ind_weight = random.choices(industries, weights=[0.20, 0.22, 0.15, 0.12, 0.08, 0.07, 0.06, 0.04, 0.04, 0.02])[0]
        comp_size, size_weight = random.choices(company_sizes, weights=[0.18, 0.25, 0.30, 0.18, 0.09])[0]
        channel, chan_weight = random.choices(channels, weights=[0.25, 0.20, 0.15, 0.20, 0.12, 0.08])[0]

        # Facturación estimada según tamaño
        base_rev: float = {
            "1000+": random.uniform(10_000_000, 50_000_000),
            "201-1000": random.uniform(3_000_000, 10_000_000),
            "51-200": random.uniform(1_000_000, 3_000_000),
            "11-50": random.uniform(300_000, 1_000_000),
            "1-10": random.uniform(50_000, 300_000),
        }[comp_size]

        # Vector 2 (capítulo 24): no todos declaran sus ingresos. La ausencia no es al azar
        # —las empresas pequeñas y los contactos que no rellenaron un formulario la dejan en
        # blanco más a menudo—, que es justo lo que hace falta para que la columna que marca
        # la ausencia tenga algo que aprender. Es una suposición sobre el negocio, no una
        # medida, y la etiqueta sigue sin depender de los ingresos.
        prob_ausente = 0.15
        if comp_size in ("1-10", "11-50"):
            prob_ausente += 0.20
        if channel in ("Outbound Cold Email", "Organic Search"):
            prob_ausente += 0.10
        ingresos_declarados = None if random.random() < prob_ausente else round(base_rev, 2)

        # Comportamiento digital
        page_views = random.randint(1, 20) if title_weight > 0.5 else random.randint(1, 6)
        email_opens = random.randint(0, 12)
        email_clicks = random.randint(0, min(email_opens, 6))
        downloads = random.randint(0, 4)
        attended_webinar = 1 if channel == "Webinar" or (random.random() < 0.25 and title_weight > 0.5) else 0
        requested_demo = 1 if channel == "Demo Request Form" or (random.random() < 0.20 and title_weight > 0.7) else 0

        # Señales de avance comercial. El backend ya las contabilizaba desde las actividades
        # registradas del prospecto, pero no formaban parte del vector que recibía el modelo:
        # una propuesta enviada o una reunión agendada solo movían la mitad heurística del
        # score. Son las señales más informativas de todo el embudo y el modelo estaba ciego
        # a ellas (ML-4).
        #
        # Se generan condicionadas a que haya habido interés previo, que es como ocurren en
        # la realidad: nadie agenda una reunión con quien no ha interactuado nunca.
        interes_previo = requested_demo or attended_webinar or email_clicks >= 3
        meeting_scheduled = 1 if interes_previo and random.random() < 0.35 else 0
        proposal_sent = 1 if meeting_scheduled and random.random() < 0.55 else 0

        # Contacto directo del asesor. Correlaciona con el interés, pero mucho más
        # débilmente: un asesor puede llamar a un prospecto frío por cuota.
        #
        # Vector 2 (capítulo 24): cada llamada tiene resultado. Se generan los intentos y de
        # ellos las que conectan, con más probabilidad cuando hay interés: quien ha pedido
        # una demo contesta el teléfono más que quien no ha abierto un correo.
        intentos = random.randint(0, 5) if interes_previo else random.randint(0, 3)
        prob_conecta = 0.60 if interes_previo else 0.25
        phone_calls_connected = sum(1 for _ in range(intentos) if random.random() < prob_conecta)
        phone_calls_unanswered = intentos - phone_calls_connected

        # Y cada mensaje, su canal. WhatsApp lo abre a menudo el propio prospecto y sigue al
        # interés; LinkedIn lo abre casi siempre el asesor y lo sigue mucho menos.
        whatsapp_messages = random.randint(0, 4) if interes_previo else random.randint(0, 1)
        linkedin_messages = random.randint(0, 3) if interes_previo else random.randint(0, 2)

        # Días de inactividad (recency)
        days_since_last_activity = random.randint(0, 40)

        # Cálculo de probabilidad real latente para simular la etiqueta de conversión
        firmographic_score = (title_weight * 0.45) + (ind_weight * 0.30) + (size_weight * 0.25)

        behavioral_raw = (
            (page_views * 0.04) +
            (email_opens * 0.03) +
            (email_clicks * 0.08) +
            (downloads * 0.12) +
            (attended_webinar * 0.20) +
            (requested_demo * 0.35) +
            # Pesos más altos que el resto: en un embudo B2B, una reunión agendada y una
            # propuesta enviada son los dos hitos que de verdad anticipan el cierre.
            (meeting_scheduled * 0.40) +
            (proposal_sent * 0.50) +
            (phone_calls_connected * 0.05) +
            # Los intentos sin respuesta restan poco: insistir con quien no contesta es una
            # señal débil de desinterés, no de interés.
            (phone_calls_unanswered * -0.02) +
            (whatsapp_messages * 0.04) +
            (linkedin_messages * 0.015)
        )
        behavioral_score = max(0.0, min(1.0, behavioral_raw))

        # Atenuación temporal sobre el comportamiento
        decay_factor = (0.5) ** (days_since_last_activity / 14.0)
        effective_behavior = behavioral_score * decay_factor

        # Probabilidad de conversión latente
        latent_prob = (0.40 * firmographic_score) + (0.50 * effective_behavior) + (0.10 * chan_weight)
        # Añadir ruido realista
        noisy_prob = np.clip(latent_prob + np.random.normal(0, 0.05), 0.01, 0.99)

        # Etiqueta de conversión binaria (1 = Convirtió / SQL Ganado, 0 = No convirtió)
        converted = 1 if noisy_prob >= 0.55 else 0

        data.append({
            "lead_id": f"LEAD-SYNTH-{10000 + i}",
            "job_title": title,
            "industry": industry,
            "company_size": comp_size,
            "annual_revenue": ingresos_declarados,
            "source_channel": channel,
            "page_views": page_views,
            "email_opens": email_opens,
            "email_clicks": email_clicks,
            "content_downloads": downloads,
            "attended_webinar": attended_webinar,
            "requested_demo": requested_demo,
            "meeting_scheduled": meeting_scheduled,
            "proposal_sent": proposal_sent,
            "phone_calls_connected": phone_calls_connected,
            "phone_calls_unanswered": phone_calls_unanswered,
            "whatsapp_messages": whatsapp_messages,
            "linkedin_messages": linkedin_messages,
            "days_since_last_activity": days_since_last_activity,
            "decay_factor": round(decay_factor, 4),
            # `latent_prob` NO se publica: es la probabilidad con la que se fabricó la
            # etiqueta. Incluirla en el CSV dejaba la respuesta dentro del examen; quien
            # reentrenara desde este archivo sin conocer su origen obtendría un modelo con
            # fuga de información y una precisión aparente casi perfecta.
            "converted": converted,
        })

    df = pd.DataFrame(data)
    return df


if __name__ == "__main__":
    df_leads = generate_synthetic_leads_dataset(num_samples=2500)
    print(f"Dataset generado: {len(df_leads)} registros.")
    print(f"Tasa de conversión global: {df_leads['converted'].mean() * 100:.2f}%")
    print(df_leads.head(3))
