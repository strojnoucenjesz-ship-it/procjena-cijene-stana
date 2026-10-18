    kat = polje_iz_teksta(
        tekst, "Kat",
        ["Lokacija", "Transakcija", "Vrsta nekretnine", "Površina", "Ukupan broj soba", "Broj soba", "Cijena", "Stanje"]
    )

    vrsta = "apartman" if "apartman" in naslov_mali else (
        "penthouse" if "penthouse" in naslov_mali else "stan"
    )

    # Dodatna provjera da stranica izgleda kao stvarni oglas, a ne katalog.
    if not any(oznaka in puni_tekst_mali for oznaka in (
        "površina", "povrsina", "lokacija", "transakcija"
    )):
        return None

    return {
        "agencija": "Manor",
        "naslov": naslov,
        "url": url,
        "lokacija": lokacija,
        "transakcija": transakcija or "prodaja (provjerena cijena i bez oznaka najma)",
        "vrsta_nekretnine": vrsta,
        "cijena_eur": round(cijena, 2),
        "povrsina_m2": round(povrsina, 2),
        "cijena_eur_m2": round(cijena / povrsina, 2),
        "broj_soba": sobe,
        "kat": kat
    }


# ------------------------- CSV I GLAVNI PROGRAM -------------------------

def spremi_csv(podaci):
    with open(IZLAZ, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STUPCI)
        writer.writeheader()
        writer.writerows(podaci.values())


def main():
    print("=" * 65)
    print("PRIKUPLJANJE STANOVA ZA PRODAJU — RIJEKA I PGŽ")
    print("Izvor: Manor. DOGMA i DUX su izostavljeni.")
    print("=" * 65)

    prva = dohvati_soup(POCETNA)
    if prva is None:
        print("\nPočetna stranica Manor nije dostupna ili se ne može čitati.")
        print("Nije zaobiđena nikakva zaštita. Provjeri ručno može li se stranica otvoriti.")
        return

    red_kataloga = deque([POCETNA])
    posjeceni_katalozi = set()
    oglasi_url = set()

    while red_kataloga and len(posjeceni_katalozi) < MAKS_KATALOGA:
        katalog = normaliziraj_url(red_kataloga.popleft())
        if katalog in posjeceni_katalozi:
            continue
        posjeceni_katalozi.add(katalog)
        soup = prva if katalog == normaliziraj_url(POCETNA) else dohvati_soup(katalog)
        if soup is None:
            continue

        novi_oglasi, novi_katalozi = linkovi_iz_kataloga(soup, katalog)
        oglasi_url.update(novi_oglasi)

        for link in novi_katalozi:
            if link not in posjeceni_katalozi and link not in red_kataloga:
                red_kataloga.append(link)

        print(f"Katalog obrađen: {katalog}")
        print(f"  Poveznica na moguće oglase ukupno: {len(oglasi_url)}")

    if not oglasi_url:
        print("\nNisu pronađene poveznice na pojedinačne oglase.")
        print("Moguće je da se katalog učitava JavaScriptom ili je promijenio strukturu.")
        return

    podaci = {}
    lista = sorted(oglasi_url)[:MAKS_OGLASA]
    for i, url in enumerate(lista, start=1):
        print(f"\n[{i}/{len(lista)}] {url}")
        soup = dohvati_soup(url)
        if soup is None:
            continue

        red = izvuci_oglas(soup, url)
        if red is None:
            print("  Preskočeno: nije potvrđen stan za prodaju u ciljanoj regiji.")
            continue

        podaci[red["url"]] = red
        spremi_csv(podaci)
        print(
            f"  OK: {red['naslov']} | {red['cijena_eur']:.0f} € | "
            f"{red['povrsina_m2']} m² | {red['lokacija']}"
        )

    spremi_csv(podaci)

    print("\n" + "=" * 65)
    print("PRIKUPLJANJE ZAVRŠENO")
    print(f"Broj jedinstvenih valjanih oglasa: {len(podaci)}")
    print(f"CSV datoteka: {IZLAZ}")
    print("Provjeri uzorak CSV-a prije treniranja modela.")
    if len(podaci) < 30:
        print("Napomena: manje od 30 oglasa nije dovoljno za pouzdan model.")
    if len(podaci) == 0:
        print("Nije pronađen valjan oglas. Ne treniraj model na praznoj datoteci.")


if __name__ == "__main__":
    main()
