
import pandas as pd
from pathlib import Path

ULAZNA_DATOTEKA = "nekretnine_za_obradu.csv"
IZLAZNA_DATOTEKA = "nekretnine_ocisceno.csv"


def obradi_podatke():
    if not Path(ULAZNA_DATOTEKA).exists():
        print(f"Greška: datoteka {ULAZNA_DATOTEKA} nije pronađena.")
        return

    df = pd.read_csv(ULAZNA_DATOTEKA)

    print("Učitavanje podataka uspješno.")
    print(f"Broj učitanih oglasa: {len(df)}")

    # Uklanjanje duplikata prema URL-u oglasa
    df = df.drop_duplicates(subset=["url"])

    # Pretvaranje numeričkih stupaca u brojeve
    numericki_stupci = [
        "cijena_eur",
        "povrsina_m2",
        "cijena_eur_m2",
        "broj_soba",
        "kat"
    ]

    for stupac in numericki_stupci:
        if stupac in df.columns:
            df[stupac] = pd.to_numeric(
                df[stupac],
                errors="coerce"
            )

    # Uklanjanje oglasa bez cijene ili površine
    df = df.dropna(
        subset=["cijena_eur", "povrsina_m2"]
    )

    # Zadržavanje smislenih vrijednosti
    df = df[
        (df["cijena_eur"] > 0)
        & (df["povrsina_m2"] >= 10)
        & (df["povrsina_m2"] <= 1000)
    ].copy()

    # Ponovni izračun cijene po kvadratnom metru
    df["cijena_eur_m2"] = (
        df["cijena_eur"] / df["povrsina_m2"]
    ).round(2)

    # Spremanje očišćenih podataka
    df.to_csv(
        IZLAZNA_DATOTEKA,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nOBRADA ZAVRŠENA")
    print(f"Broj oglasa nakon čišćenja: {len(df)}")
    print(f"Spremljena datoteka: {IZLAZNA_DATOTEKA}")

    print("\nPrimjer obrađenih podataka:")
    print(
        df[
            ["naslov", "lokacija", "cijena_eur",
             "povrsina_m2", "cijena_eur_m2"]
        ].head().to_string(index=False)
    )


if __name__ == "__main__":
    obradi_podatke()
