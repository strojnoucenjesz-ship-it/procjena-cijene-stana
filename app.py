
import streamlit as st
import pandas as pd
import joblib
from pathlib import Path

st.set_page_config(
    page_title="Procjena cijene stana",
    page_icon="🏠",
    layout="centered"
)

st.title("🏠 Procjena cijene stana")
st.write(
    "Aplikacija koristi model strojnog učenja "
    "za procjenu tražene cijene stana."
)

PUTANJA_MODELA = Path("model_stana.pkl")

if not PUTANJA_MODELA.exists():
    st.error(
        "Model nije pronađen. Najprije pokreni naredbu: "
        "python model.py"
    )
    st.stop()

model = joblib.load(PUTANJA_MODELA)

st.subheader("Unesi podatke o stanu")

povrsina = st.number_input(
    "Površina stana (m²)",
    min_value=10.0,
    max_value=500.0,
    value=60.0,
    step=1.0
)

broj_soba = st.number_input(
    "Broj soba",
    min_value=1,
    max_value=10,
    value=2,
    step=1
)

if st.button("Procijeni cijenu", type="primary"):
    podaci = pd.DataFrame({
        "povrsina_m2": [povrsina],
        "broj_soba": [broj_soba]
    })

    procjena = float(model.predict(podaci)[0])

    if procjena <= 0:
        st.warning(
            "Model je izračunao nelogičnu cijenu. "
            "Podaci i model trebaju dodatnu provjeru."
        )
    else:
        st.success(
            f"Procijenjena tražena cijena: {procjena:,.0f} €"
        )

        cijena_po_m2 = procjena / povrsina

        st.metric(
            "Procijenjena cijena po m²",
            f"{cijena_po_m2:,.0f} €/m²"
        )

st.divider()

st.caption(
    "Napomena: model je treniran na samo 16 oglasa. "
    "Rezultat je informativan i nije službena procjena "
    "vrijednosti nekretnine."
)
