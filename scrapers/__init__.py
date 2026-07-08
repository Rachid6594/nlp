"""Registre des scrapers indépendants par média."""
from scrapers.rtb import RtbScraper
from scrapers.rss_media import (
    AibScraper,
    Burkina24Scraper,
    FasoActuScraper,
    FasozineScraper,
    LaborpresseScraper,
    LefasoScraper,
    Ouaga24Scraper,
)
from scrapers.zoodomail import ZoodomailScraper

SCRAPERS = {
    "rtb": RtbScraper,
    "aib": AibScraper,
    "lefaso": LefasoScraper,
    "burkina24": Burkina24Scraper,
    "fasoactu": FasoActuScraper,
    "fasozine": FasozineScraper,
    "ouaga24": Ouaga24Scraper,
    "zoodomail": ZoodomailScraper,
    "laborpresse": LaborpresseScraper,
}


def get_scraper(code: str, client=None):
    cls = SCRAPERS[code]
    return cls(client=client) if client is not None else cls()
