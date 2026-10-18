"""
PRIKUPLJANJE OGLASA STANOVA ZA PRODAJU — RIJEKA I PRIMORSKO-GORANSKA ŽUPANIJA

Izvor: Manor (DOGMA i DUX su namjerno izostavljeni).
Pokretanje u terminalu: py prikupljanje.py

Izlaz: nekretnine_za_obradu.csv
Napomena: prikupljaju se oglašene cijene, a ne realizirane kupoprodajne cijene.
Skripta poštuje robots.txt i ne pokušava zaobići CAPTCHA-u ili blokade.
"""

import csv
import html
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


# ------------------------- POSTAVKE -------------------------

IZLAZ = "nekretnine_za_obradu.csv"
POCETNA = "https://manor.hr/nekretnine/stanovi"
PAUZA = 1.5
TIMEOUT = 20
MAKS_KATALOGA = 12
MAKS_OGLASA = 400

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SkolskiProjektNekretnine/1.0)"
}

STUPCI = [
    "agencija", "naslov", "url", "lokacija", "transakcija",
    "vrsta_nekretnine", "cijena_eur", "povrsina_m2",
    "cijena_eur_m2", "broj_soba", "kat"
]

# Lokacije koje pripadaju Rijeci / Primorsko-goranskoj županiji.
LOKACIJE_PGZ = [
    "rijeka", "opatija", "matulji", "viškovo", "viskovo", "kastav",
    "čavle", "cavle", "jelenje", "kostrena", "bakar", "kraljevica",
    "crikvenica", "novi vinodolski", "krk", "malinska", "njivice",
    "dobrinj", "punat", "baška", "baska", "rab", "lopar", "cres",
    "lošinj", "losinj", "delnice", "fužine", "fuzine", "čabar", "cabar",
    "mrkopalj", "ravna gora", "lokve", "omišalj", "omisalj", "klana",
    "perman", "lovran", "mošćenička draga", "moscenicka draga"
]

ZABRANJENI_NAJAM = (
    "najam", "najmiti", "iznajmlj", "za rent", "rentiranje",
    "mjesečna najamnina", "mjesecna najamnina", "dugoročni najam",
    "dugorocni najam", "kratkoročni najam", "kratkorocni najam"
)

session = requests.Session()
session.headers.update(HEADERS)
robots_cache = {}


# ------------------------- PRISTUP STRANICAMA -------------------------

def robots_dopusta(url):
    """Provjerava robots.txt po domeni; ako provjera ne uspije, preskače stranicu."""
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    if root not in robots_cache:
        robots_url = root + "/robots.txt"
        try:
            odgovor = session.get(robots_url, timeout=TIMEOUT)
            if odgovor.status_code == 404:
                # HTTP 404 znači da robots.txt ne postoji, pa nema pravila za čitanje.
                robots_cache[root] = "nema_datoteke"
            elif 200 <= odgovor.status_code < 300:
                parser = RobotFileParser()
                parser.parse(odgovor.text.splitlines())
                robots_cache[root] = parser
            else:
                print(f"Ne mogu potvrditi pravila robots.txt ({odgovor.status_code}); preskačem domenu.")
                robots_cache[root] = None
        except requests.RequestException as e:
            print(f"Ne mogu provjeriti robots.txt za {root}: {e}")
            robots_cache[root] = None

    pravila = robots_cache[root]
    if pravila == "nema_datoteke":
        return True
    if pravila is None:
        return False
    return pravila.can_fetch(HEADERS["User-Agent"], url)


def dohvati_soup(url):
    if not robots_dopusta(url):
        print("Preskačem: pristup nije dopušten ili nije moguće provjeriti pravila:", url)
        return None

    try:
        odgovor = session.get(url, timeout=TIMEOUT)
        if odgovor.status_code in (401, 403, 429):
            print(f"Stranica odbila ili ograničila pristup (HTTP {odgovor.status_code}): {url}")
            return None
        odgovor.raise_for_status()
        odgovor.encoding = odgovor.apparent_encoding
        soup = BeautifulSoup(odgovor.text, "html.parser")
        vidljivi_tekst = soup.get_text(" ", strip=True).lower()

        if any(izraz in vidljivi_tekst for izraz in (
            "captcha", "shieldsquare", "verify you are human", "access denied"
        )):
            print("Pronađena zaštitna stranica; ne pokušavam je zaobići:", url)
            return None

        time.sleep(PAUZA)
        return soup
    except requests.RequestException as e:
        print(f"Greška pri dohvaćanju {url}: {e}")
        return None


# ------------------------- POMOĆNE FUNKCIJE -------------------------

def tekst_ocisti(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normaliziraj_url(url):
    url, _ = urldefrag(url)
    p = urlparse(url)
    # Odbacujemo parametre za praćenje i fragment.
    return p._replace(query="", fragment="").geturl().rstrip("/")


def broj(tekst):
    """Pretvara zapise poput 73,5 ili 73.5 u float."""
    if tekst is None:
        return None
    s = tekst_ocisti(tekst).replace("\xa0", " ")
    s = re.sub(r"[^\d,.]", "", s)
    if not s:
        return None

    # U površini je decimalni zarez čest; točka između tisućica se uklanja.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")

    try:
        return float(s)
    except ValueError:
        return None


def cijena_u_eur(tekst):
    """Vraća cijenu u eurima; ne prihvaća male iznose koji su tipični za najam."""
    t = tekst_ocisti(tekst)
    uzorci = [
        r"(?:cijena|prodajna cijena)\s*:?\s*([\d][\d.\s]*(?:,\d+)?)\s*(?:€|EUR)(?![A-Z])",
        r"([\d][\d.\s]*(?:,\d+)?)\s*(?:€|EUR)(?![A-Z])",
        r"€\s*([\d][\d.\s]*(?:,\d+)?)"
    ]
    for uzorak in uzorci:
        m = re.search(uzorak, t, re.IGNORECASE)
        if not m:
            continue
        s = m.group(1).replace(" ", "")
        # Oglasi koriste točku kao razdjelnik tisućica (npr. 159.000 €).
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(".", "")
        try:
            vrijednost = float(s)
        except ValueError:
            continue
        if 10000 <= vrijednost <= 100_000_000:
            return vrijednost
    return None


def polje_iz_teksta(tekst, naziv, sljedeca_polja):
    """Čita vrijednost između jednog označenog polja i sljedeće oznake."""
    sljedeca = "|".join(re.escape(x) for x in sljedeca_polja)
    uzorak = rf"{re.escape(naziv)}\s*:\s*(.*?)(?=\s+(?:{sljedeca})\s*:|$)"
    m = re.search(uzorak, tekst, re.IGNORECASE)
    return tekst_ocisti(m.group(1)) if m else ""


def izvuci_naslov(soup):
    h1 = soup.find("h1")
    if h1:
        naslov = tekst_ocisti(h1.get_text(" ", strip=True))
        if naslov:
            return naslov

    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return tekst_ocisti(og["content"])

    if soup.title:
        return tekst_ocisti(soup.title.get_text(" ", strip=True))
    return ""


def je_link_istog_web_mjesta(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "manor.hr" or host.endswith(".manor.hr")


def linkovi_iz_kataloga(soup, bazni_url):
    """Prikuplja moguće detalje i linkove na iduće stranice kataloga."""
    oglasi = set()
    katalozi = set()

    for a in soup.select("a[href]"):
        url = normaliziraj_url(urljoin(bazni_url, a.get("href", "")))
        if not je_link_istog_web_mjesta(url):
            continue

        path = urlparse(url).path.lower()
        label = tekst_ocisti(a.get_text(" ", strip=True)).lower()

        if url == normaliziraj_url(POCETNA):
            continue

        # Poveznice na stranice kataloga/paginaciju.
        if "/nekretnine/stanovi" in path or any(x in label for x in (
            "sljedeća", "sljedeca", "next", "dalje", "»"
        )):
            katalozi.add(url)
            continue

        # Ne oslanjamo se na jedan točan URL obrazac: neke stranice imaju različite putanje.
        if any(x in path for x in ("/nekretnina/", "/nekretnine/", "/stan/", "/oglas/")):
            if not any(x in path for x in (
                "/kategorija/", "/tag/", "/autor/", "/page/", "/projekti"
            )):
                oglasi.add(url)

    return oglasi, katalozi


# ------------------------- ČITANJE DETALJA OGLASA -------------------------

def izvuci_oglas(soup, url):
    naslov = izvuci_naslov(soup)
    if not naslov or len(naslov) < 5:
        return None

    tekst = tekst_ocisti(soup.get_text(" ", strip=True))
    naslov_mali = naslov.lower()
    puni_tekst_mali = tekst.lower()

    # Mora biti oglas stana/apartmana i ne smije biti oglas za najam.
    if not re.search(r"\b(stan|apartman|penthouse)\b", naslov_mali):
        return None
    if any(rijec in naslov_mali for rijec in ZABRANJENI_NAJAM):
        return None

    cijena = cijena_u_eur(tekst)
    if cijena is None:
        return None

    # Čitamo Manorova polja kad su dostupna.
    povrsina_txt = polje_iz_teksta(
        tekst, "Površina",
        ["Lokacija", "Transakcija", "Vrsta nekretnine", "Ukupan broj soba", "Broj soba", "Kat", "Cijena"]
    )
    povrsina = broj(re.search(r"\d+(?:[.,]\d+)?", povrsina_txt).group(0)) if re.search(
        r"\d+(?:[.,]\d+)?", povrsina_txt
    ) else None

    if povrsina is None:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*m\s*(?:²|2)(?!\w)", naslov, re.IGNORECASE)
        if m:
            povrsina = broj(m.group(1))
    if povrsina is None or not 10 <= povrsina <= 1000:
        return None

    transakcija = polje_iz_teksta(
        tekst, "Transakcija",
        ["Vrsta nekretnine", "Površina", "Ukupan broj soba", "Broj soba", "Kat", "Lokacija", "Cijena"]
    )
    # Izričit podatak "Za najam" uvijek odbacujemo.
    if "najam" in transakcija.lower() or "rent" in transakcija.lower():
        return None
    # Ako je transakcija eksplicitno navedena, mora označavati prodaju.
    if transakcija and not any(x in transakcija.lower() for x in ("prodaj", "sale")):
        return None

    lokacija = polje_iz_teksta(
        tekst, "Lokacija",
        ["Transakcija", "Vrsta nekretnine", "Površina", "Ukupan broj soba", "Broj soba", "Kat", "Cijena"]
    )
    if not lokacija:
        # Fallback samo na lokaciju prepoznatljivu u naslovu.
        mjesta = "|".join(re.escape(x) for x in sorted(LOKACIJE_PGZ, key=len, reverse=True))
        m = re.search(rf"\b({mjesta})\b", naslov, re.IGNORECASE)
        lokacija = m.group(1) if m else ""

    podrucje = f"{lokacija} {naslov}".lower()
    if not any(mjesto in podrucje for mjesto in LOKACIJE_PGZ):
        return None

    # Broj soba.
    sobe = ""
    m_sobe = re.search(
        r"(?:Ukupan broj soba|Broj soba|Sobe)\s*:?\s*(\d+(?:[.,]\d+)?)",
        tekst, re.IGNORECASE
    )
    if m_sobe:
        sobe_vrijednost = broj(m_sobe.group(1))
        sobe = sobe_vrijednost if sobe_vrijednost is not None else ""

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
