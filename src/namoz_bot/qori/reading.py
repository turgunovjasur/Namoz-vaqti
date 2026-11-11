"""A self-contained surah reader with the Amiri Quran Colored typeface."""

from base64 import b64encode
from functools import cache
from html import escape

from namoz_bot.qori.corpus import ASSETS, Surah


@cache
def _embedded_font() -> str:
    return b64encode((ASSETS / "AmiriQuranColored.ttf").read_bytes()).decode("ascii")


@cache
def _notices() -> str:
    source = (ASSETS / "quran-uthmani.txt").read_text("utf-8")
    notice = source[source.index("# PLEASE DO NOT REMOVE") :]
    font_license = (ASSETS / "AmiriQuran-OFL.txt").read_text("utf-8")
    return escape(notice + "\nCopyright 2010-2022 The Amiri Project Authors.\n" + font_license)


_STYLE = """
* { box-sizing: border-box }
body { margin: 0; background: #f4f2e9; color: #1c362d; font-family: system-ui, sans-serif }
main { max-width: 46rem; margin: 2rem auto; background: #fffdf5; border: 1px solid #dcd8c6;
       border-radius: 1rem; overflow: hidden }
header { padding: 1.5rem clamp(1.2rem,5vw,3rem); background: #104e42; color: #fffdf5;
         display:flex; gap: 1rem; flex-wrap:wrap; justify-content: space-between;
         align-items:baseline; border-bottom: .22rem solid #bb9764 }
h1 { font: 600 clamp(1.6rem,5vw,2.3rem)/1.25 Georgia,serif; margin: 0 }
header span { font-size: .95rem }
ol { margin: 0; padding: 0; list-style: none }
li { display: grid; grid-template-columns: 2.2rem minmax(0,1fr); align-items: baseline;
     gap: .85rem; padding: .9rem clamp(1rem,4vw,2.3rem); border-bottom: 1px solid #e1e1d2 }
li:nth-child(even) { background: #f2f6ef }
.number { font: 600 .84rem/2 system-ui,sans-serif; color: #795c32; text-align: center;
          border: 1px solid #d5c7a7; border-radius: 1rem }
.verse { font: clamp(2.15rem,6.5vw,3.1rem)/2.05 Qori,serif; margin: 0;
         text-align: right; color: #18352c; overflow-wrap: break-word }
footer { padding: 1.15rem clamp(1rem,4vw,2.3rem); font-size:.88rem }
a { color: #176254 } details { margin-top:.6rem } summary { cursor:pointer }
pre { white-space:pre-wrap; overflow-wrap:anywhere }
@media (max-width: 48rem) { main { margin:0 auto; border:0; border-radius:0 } }
"""


def reading_html(surah: Surah) -> bytes:
    # The font colors its own marks after shaping. Each ayah stays one intact text run.
    rows = "\n".join(
        f'<li><span class="number">{number}</span>'
        f'<p class="verse" dir="rtl" lang="ar">{escape(verse)}</p></li>'
        for number, verse in enumerate(surah.verses, 1)
    )
    title = f"{escape(surah.name)} surasi"
    return f"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>@font-face {{font-family:Qori;src:url(data:font/ttf;base64,{_embedded_font()})
 format("truetype");}}{_STYLE}</style></head>
<body><main><header><h1>{title}</h1><span>{surah.number}-sura · {len(surah.verses)} oyat</span>
</header><ol>{rows}</ol>
<footer>Matn manbasi · <a href="https://tanzil.net/#{surah.number}:1">Tanzil Project</a>
<details><summary>Matn va shrift litsenziyalari</summary><pre>{_notices()}</pre></details>
</footer></main></body></html>""".encode()
