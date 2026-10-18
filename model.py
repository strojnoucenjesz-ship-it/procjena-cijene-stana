
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


DATOTEKA = "nekretnine_ocisceno.csv"


def treniraj_model():
    if not Path(DATOTEKA).exists():
        print(f"Greška: nije pronađena datoteka {DATOTEKA}.")
        print("Prvo pokreni: python obrada.py")
        return

    df = pd.read_csv(DATOTEKA)

    # Značajke koje model koristi za procjenu cijene
    znacajke = ["povrsina_m2", "broj_soba"]
    cilj = "cijena_eur"

    # Provjera potrebnih stupaca
    potrebni_stupci = znacajke + [cilj]
    nedostaju = [
        stupac for stupac in potrebni_stupci
        if stupac not in df.columns
    ]

    if nedostaju:
        print("Nedostaju stupci:", nedostaju)
        print("Dostupni stupci:", list(df.columns))
        return

    # Pretvaranje podataka u brojeve
    for stupac in potrebni_stupci:
        df[stupac] = pd.to_numeric(df[stupac], errors="coerce")

    df = df.dropna(subset=potrebni_stupci)

    if len(df) < 5:
        print("Premalo valjanih oglasa za treniranje i testiranje.")
        return

    X = df[znacajke]
    y = df[cilj]

    # Razdvajanje podataka za učenje i testiranje
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42
    )

    # Treniranje modela linearne regresije
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Procjena na izdvojenim testnim podacima
    predikcije = model.predict(X_test)

    mae = mean_absolute_error(y_test, predikcije)
    rmse = mean_squared_error(y_test, predikcije) ** 0.5
    r2 = r2_score(y_test, predikcije)

    print("\nTRENIRANJE MODELA ZAVRŠENO")
    print(f"Broj oglasa korištenih za analizu: {len(df)}")
    print(f"Broj oglasa za treniranje: {len(X_train)}")
    print(f"Broj oglasa za testiranje: {len(X_test)}")
    print(f"MAE: {mae:.2f} EUR")
    print(f"RMSE: {rmse:.2f} EUR")
    print(f"R²: {r2:.3f}")

    print("\nPrimjer procjene za stan od 60 m² s 2 sobe:")
    primjer = pd.DataFrame({
        "povrsina_m2": [60],
        "broj_soba": [2]
    })

    procjena = model.predict(primjer)[0]
    print(f"Procijenjena cijena: {procjena:,.2f} EUR")

    # Spremanje modela za kasniju upotrebu u aplikaciji
    import joblib
    joblib.dump(model, "model_stana.pkl")
    print("\nModel je spremljen u model_stana.pkl")


if __name__ == "__main__":
    treniraj_model()
